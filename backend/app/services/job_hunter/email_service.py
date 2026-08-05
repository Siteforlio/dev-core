# backend/app/services/job_hunter/email_service.py
import imaplib
import smtplib
import email
import uuid
import json
import logging
from email.mime.text import MIMEText
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.job_hunter import EmailEvent, JobHunterCampaign, Application, JobListing
from app.core.config import settings
from app.services.job_hunter.llm import call_llm

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EmailService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _fernet(self) -> Fernet:
        if not settings.job_hunter_encryption_key:
            raise ValueError("JOB_HUNTER_ENCRYPTION_KEY is not configured")
        return Fernet(settings.job_hunter_encryption_key.encode())

    def encrypt_credentials(self, creds: dict) -> str:
        return self._fernet().encrypt(json.dumps(creds).encode()).decode()

    def decrypt_credentials(self, encrypted: str) -> dict:
        return json.loads(self._fernet().decrypt(encrypted.encode()).decode())

    async def _call_haiku(self, prompt: str, max_tokens: int = 100) -> str:
        return (await call_llm(prompt, max_tokens)).strip()

    async def classify_email(self, subject: str, snippet: str) -> str:
        result = await self._call_haiku(
            f"Classify this email as exactly one word: interview, rejection, or other.\n"
            f"Subject: {subject[:200]}\nSnippet: {snippet[:300]}"
        )
        for label in ["interview", "rejection"]:
            if label in result.lower():
                return label
        return "other"

    async def generate_rejection_reply(self, company: str, role: str) -> str:
        return await self._call_haiku(
            f"Write a brief, professional reply to a rejection email from {company[:100]} for the {role[:150]} role. "
            f"Thank them, ask for specific feedback on what would make a stronger candidate in the future. "
            f"Tone: gracious, curious, forward-looking. Return only the email body.",
            max_tokens=300,
        )

    def fetch_new_emails(self, creds: dict, since: datetime) -> list[dict]:
        """Fetch emails received after `since` via IMAP. Returns [] on any error."""
        try:
            mail = imaplib.IMAP4_SSL(creds["host"], creds.get("port", 993))
            mail.login(creds["username"], creds["password"])
            mail.select("INBOX")
            since_str = since.strftime("%d-%b-%Y")
            _, data = mail.search(None, f'(SINCE "{since_str}")')
            emails = []
            for num in (data[0].split() if data[0] else [])[:50]:  # max 50 per poll
                _, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")[:500]
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")[:500]
                emails.append({
                    "subject": str(msg["Subject"] or ""),
                    "sender": str(msg["From"] or ""),
                    "date": str(msg["Date"] or ""),
                    "snippet": body,
                })
            mail.logout()
            return emails
        except Exception:
            logger.exception("fetch_new_emails failed for host %s", creds.get("host"))
            return []

    def send_reply(self, creds: dict, to: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEText(body)
            msg["Subject"] = f"Re: {subject}"
            msg["From"] = creds["username"]
            msg["To"] = to
            with smtplib.SMTP_SSL(creds.get("smtp_host", creds["host"]), creds.get("smtp_port", 465)) as server:
                server.login(creds["username"], creds["password"])
                server.sendmail(creds["username"], [to], msg.as_string())
            return True
        except Exception:
            logger.exception("send_reply failed to %s", to)
            return False

    def _extract_domain(self, sender: str) -> str:
        """Extract domain from email address like 'HR <hr@google.com>' → 'google'."""
        addr = sender.split("@")[-1].split(">")[0].strip() if "@" in sender else sender
        return addr.split(".")[0].lower()

    async def _resolve_application(self, campaign_id: str, sender_domain: str) -> tuple[Application | None, JobListing | None]:
        """Fuzzy-match sender domain against active applications in the campaign."""
        apps_result = await self.db.execute(
            select(Application).where(
                Application.campaign_id == campaign_id,
                Application.status == "applied",
            )
        )
        applications = apps_result.scalars().all()
        for app in applications:
            listing_result = await self.db.execute(select(JobListing).where(JobListing.id == app.job_listing_id))
            listing = listing_result.scalar_one_or_none()
            if listing and sender_domain in (listing.company or "").lower():
                return app, listing
        return None, None

    async def process_campaign_emails(self, campaign_id: str) -> None:
        result = await self.db.execute(select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign or not campaign.email_account_encrypted:
            return
        creds = self.decrypt_credentials(campaign.email_account_encrypted)
        since = campaign.email_monitor_since or _utcnow()

        import asyncio
        raw_emails = await asyncio.to_thread(self.fetch_new_emails, creds, since)
        for raw in raw_emails:
            email_type = await self.classify_email(raw["subject"], raw["snippet"])
            if email_type == "other":
                continue

            sender_domain = self._extract_domain(raw["sender"])
            matched_app, matched_listing = await self._resolve_application(campaign_id, sender_domain)

            event = EmailEvent(
                id=str(uuid.uuid4()),
                campaign_id=campaign_id,
                application_id=matched_app.id if matched_app else None,
                type=email_type,
                subject=raw["subject"],
                sender=raw["sender"],
                received_at=_utcnow(),
                raw_snippet=raw["snippet"],
            )
            self.db.add(event)
            await self.db.commit()

            if email_type == "rejection":
                company_hint = sender_domain
                role_hint = (matched_listing.title if matched_listing else raw["subject"])[:150]
                reply_body = await self.generate_rejection_reply(company_hint, role_hint)
                sent = await asyncio.to_thread(self.send_reply, creds, raw["sender"], raw["subject"], reply_body)
                if sent:
                    event.ai_reply_sent = True
                    event.ai_reply_body = reply_body
                    event.ai_reply_sent_at = _utcnow()
                if matched_app:
                    matched_app.status = "rejected"
                await self.db.commit()

            elif email_type == "interview":
                if matched_app:
                    matched_app.status = "interview"
                    await self.db.commit()
                # Extract date/time and book calendar if credentials available
                if campaign.caldav_account_encrypted and matched_app and matched_listing:
                    try:
                        from app.services.job_hunter.calendar_service import CalendarService
                        cal_service = CalendarService(self.db)
                        caldav_creds = self.decrypt_credentials(campaign.caldav_account_encrypted)
                        dt_info = await cal_service.extract_interview_datetime(raw["snippet"])
                        if dt_info.get("date") and dt_info.get("time"):
                            from datetime import datetime as dt
                            scheduled_at = dt.strptime(
                                f"{dt_info['date']} {dt_info['time']}", "%Y-%m-%d %H:%M"
                            ).replace(tzinfo=timezone.utc)
                            await cal_service.create_interview_event(
                                application_id=matched_app.id,
                                email_event_id=event.id,
                                company=matched_listing.company or "",
                                role=matched_listing.title or "",
                                scheduled_at=scheduled_at,
                                duration_minutes=dt_info.get("duration_minutes", 60),
                                caldav_creds=caldav_creds,
                            )
                    except Exception:
                        logger.exception("Calendar booking failed for campaign %s", campaign_id)

            # Publish activity to in-process event bus
            try:
                from app.core.event_bus import publish
                company_label = matched_listing.company if matched_listing else sender_domain
                publish(
                    f"campaign:{campaign_id}:activity",
                    f"{'📅' if email_type == 'interview' else '❌'} {email_type.capitalize()} email from {company_label} — {raw['subject'][:80]}"
                )
            except Exception:
                logger.warning("event_bus publish failed for campaign %s", campaign_id)
