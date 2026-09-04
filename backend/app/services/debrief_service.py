import io
import json
import re
from collections import Counter
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import openai
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from app.models.pg.session import InterviewSession, Round, RoundMoment
from app.core.exceptions import SessionNotFoundError
from app.services.community_pipeline import CommunityPipeline


def _extract_dimension_scores(analysis: dict) -> dict[str, float]:
    """Derive per-dimension scores from analysis + round grades."""
    overall = float(analysis.get("overall_score", 5.0))
    dims = {
        "domain_knowledge": overall,
        "communication_clarity": overall,
        "quantified_impact": overall * 0.9 if not analysis.get("improvements") else overall * 0.7,
        "leadership_narrative": overall,
        "culture_alignment": overall,
        "executive_presence": overall,
        "problem_solving": overall,
    }
    for s in analysis.get("strengths", []):
        s_lower = s.lower()
        for dim in dims:
            if dim.replace("_", " ") in s_lower:
                dims[dim] = min(10.0, dims[dim] + 1.0)
    for imp in analysis.get("improvements", []):
        i_lower = imp.lower()
        for dim in dims:
            if dim.replace("_", " ") in i_lower:
                dims[dim] = max(0.0, dims[dim] - 1.5)
    return {k: round(v, 2) for k, v in dims.items()}


class DebriefService:
    def __init__(self, db: AsyncSession, api_key: str):
        self.db = db
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

    async def _call_llm(self, prompt: str) -> dict:
        response = await self._client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        raw = response.choices[0].message.content
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
            return {"overall_score": 5.0, "strengths": [], "improvements": [], "recommendation": raw[:200]}

    async def _get_moments(self, round_id: str) -> list:
        result = await self.db.execute(
            select(RoundMoment).where(RoundMoment.round_id == round_id)
        )
        return result.scalars().all()

    async def generate(self, session_id: str) -> dict:
        sess_result = await self.db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        session = sess_result.scalar_one_or_none()
        if not session:
            raise SessionNotFoundError()

        rounds_result = await self.db.execute(
            select(Round).where(Round.session_id == session_id)
        )
        rounds = rounds_result.scalars().all()

        all_moments = []
        for r in rounds:
            moments = await self._get_moments(r.id)
            all_moments.extend(moments)

        # Emotion summary
        emotions = [m.emotion_state for m in all_moments if m.emotion_state]
        emotion_summary = dict(Counter(emotions)) if emotions else {}

        # Build transcript for Claude
        transcript_lines = []
        for r in rounds:
            moments = [m for m in all_moments if m.round_id == r.id]
            for m in moments:
                transcript_lines.append(f"[{r.type}] Q: {m.question}\nA: {m.answer}")

        transcript = "\n\n".join(transcript_lines) or "No answers recorded."
        avg_score = sum(r.grade for r in rounds if r.grade) / max(len(rounds), 1)

        prompt = (
            f"You are reviewing an interview for {session.company}, role: {session.role}.\n\n"
            f"Transcript:\n{transcript}\n\nAverage score: {avg_score:.1f}/10\n\n"
            "Return a JSON debrief with improvement plan:\n"
            '{"overall_score": 7.5, "strengths": ["..."], "improvements": ["..."], '
            '"recommendation": "...", "top_3_focus_areas": ["area 1", "area 2", "area 3"], '
            '"recommended_next_session": "e.g. Practice Hiring Manager stage at Senior level"}'
        )
        analysis = await self._call_llm(prompt)

        # Write skill dimension scores to user_progress
        try:
            from app.services.progress_service import ProgressService
            progress_svc = ProgressService(db=self.db)
            dimension_scores = _extract_dimension_scores(analysis)
            career_track = getattr(session, 'career_track', None) or 'technology'
            level = getattr(session, 'level', None) or 'mid_level'
            stage = getattr(session, 'interview_stage', None) or 'hr_interview'
            await progress_svc.write_scores(
                user_id=session.user_id,
                session_id=session_id,
                career_track=career_track,
                level=level,
                stage=stage,
                scores=dimension_scores,
            )
        except Exception:
            pass  # best-effort

        # Stage anonymized data for community pipeline (fire-and-forget)
        try:
            pipeline = CommunityPipeline(db=self.db)
            rounds_for_pipeline = []
            for r in rounds:
                moments_for_round = [m for m in all_moments if m.round_id == r.id]
                rounds_for_pipeline.append({
                    "type": r.type,
                    "grade": r.grade,
                    "passed": r.passed,
                    "moments": [
                        {"question": m.question, "answer": m.answer, "emotion": m.emotion_state}
                        for m in moments_for_round
                    ],
                })
            await pipeline.stage(
                session_id=session_id,
                user_id=session.user_id,
                company=session.company,
                role=session.role,
                rounds=rounds_for_pipeline,
            )
        except Exception:  # nosec B110 — intentional: staging is best-effort
            pass

        return {
            "session_id": session_id,
            "company": session.company,
            "user_id": session.user_id,
            "role": session.role,
            "overall_score": analysis.get("overall_score", avg_score),
            "strengths": analysis.get("strengths", []),
            "improvements": analysis.get("improvements", []),
            "recommendation": analysis.get("recommendation", ""),
            "top_3_focus_areas": analysis.get("top_3_focus_areas", []),
            "recommended_next_session": analysis.get("recommended_next_session", ""),
            "emotion_summary": emotion_summary,
            "rounds": [
                {
                    "type": r.type,
                    "grade": r.grade,
                    "passed": r.passed,
                }
                for r in rounds
            ],
        }

    async def generate_pdf(self, session_id: str) -> bytes:
        """Generate a PDF interview profile report and return raw bytes."""
        data = await self.generate(session_id)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=20, spaceAfter=6)
        h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=4)
        body_style = styles["BodyText"]
        small_style = ParagraphStyle("Small", parent=body_style, fontSize=9, textColor=colors.grey)

        score = data["overall_score"]
        score_color = colors.green if score >= 7 else (colors.orange if score >= 5 else colors.red)

        story = [
            Paragraph("Interview Performance Report", title_style),
            Paragraph(
                f"{data['company']} &bull; {data['role']}",
                ParagraphStyle("Sub", parent=body_style, textColor=colors.grey, spaceAfter=2),
            ),
            Paragraph(
                datetime.now(timezone.utc).strftime("Generated %B %d, %Y"),
                small_style,
            ),
            HRFlowable(width="100%", thickness=1, color=colors.lightgrey, spaceAfter=12),

            # Score
            Paragraph("Overall Score", h2_style),
            Paragraph(
                f'<font size="28" color="{score_color.hexval()}">{score:.1f}</font>'
                f'<font size="14" color="grey"> / 10</font>',
                body_style,
            ),
            Spacer(1, 6),
            Paragraph(data["recommendation"], body_style),

            # Rounds table
            Paragraph("Round Results", h2_style),
        ]

        round_rows = [["Round", "Grade", "Result"]]
        for r in data["rounds"]:
            round_rows.append([
                r["type"].capitalize(),
                f"{r['grade']:.1f}" if r["grade"] else "—",
                "Pass" if r["passed"] else "Fail",
            ])
        t = Table(round_rows, colWidths=[8 * cm, 4 * cm, 4 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

        # Strengths
        if data["strengths"]:
            story.append(Paragraph("Strengths", h2_style))
            for s in data["strengths"]:
                story.append(Paragraph(f"+ {s}", body_style))

        # Improvements
        if data["improvements"]:
            story.append(Paragraph("Areas to Improve", h2_style))
            for s in data["improvements"]:
                story.append(Paragraph(f"&rarr; {s}", body_style))

        # Emotion breakdown
        if data.get("emotion_summary"):
            story.append(Paragraph("Emotion Breakdown", h2_style))
            emotion_text = "  |  ".join(
                f"{k.capitalize()}: {v}" for k, v in data["emotion_summary"].items()
            )
            story.append(Paragraph(emotion_text, body_style))

        doc.build(story)
        return buf.getvalue()
