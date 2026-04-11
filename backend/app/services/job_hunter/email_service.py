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
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import EmailEvent, JobHunterCampaign
from app.core.config import settings

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EmailService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    def _fernet(self) -> Fernet:
        if not settings.job_hunter_encryption_key:
            raise ValueError("JOB_HUNTER_ENCRYPTION_KEY is not configured")
        return Fernet(settings.job_hunter_encryption_key.encode())

    def encrypt_credentials(self, creds: dict) -> str:
        return self._fernet().encrypt(json.dumps(creds).encode()).decode()

    def decrypt_credentials(self, encrypted: str) -> dict:
        return json.loads(self._fernet().decrypt(encrypted.encode()).decode())

    async def _call_haiku(self, prompt: str, max_tokens: int = 100) -> str:
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            timeout=10.0,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip() if msg.content else ""

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
            event = EmailEvent(
                id=str(uuid.uuid4()),
                campaign_id=campaign_id,
                type=email_type,
                subject=raw["subject"],
                sender=raw["sender"],
                received_at=_utcnow(),
                raw_snippet=raw["snippet"],
            )
            self.db.add(event)
            await self.db.commit()
            if email_type == "rejection":
                # Extract best-effort company name from sender domain (e.g. hr@google.com → google.com)
                sender_addr = raw["sender"]
                company_hint = sender_addr.split("@")[-1].split(">")[0].strip() if "@" in sender_addr else sender_addr
                role_hint = raw["subject"][:150]
                reply_body = await self.generate_rejection_reply(company_hint, role_hint)
                sent = await asyncio.to_thread(self.send_reply, creds, raw["sender"], raw["subject"], reply_body)
                if sent:
                    event.ai_reply_sent = True
                    event.ai_reply_body = reply_body
                    event.ai_reply_sent_at = _utcnow()
                    await self.db.commit()
            # Publish activity to Redis pub/sub
            try:
                from app.core.cache import get_redis
                r = await get_redis()
                await r.publish(
                    f"campaign:{campaign_id}:activity",
                    f"Email detected: {email_type} from {raw['sender'][:100]}"
                )
            except Exception:
                logger.warning("Redis publish failed for campaign %s", campaign_id)
