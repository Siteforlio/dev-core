"""
inspect_sessions.py — Show all saved cluely sessions and their data.

Usage:
    python scripts/inspect_sessions.py
    python scripts/inspect_sessions.py --session <id>   # detailed view of one session
"""
import sys, asyncio, argparse
sys.path.insert(0, 'backend')

# Import after path setup
from sqlalchemy import text  # noqa

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', help='Show full detail for one session ID')
    args = parser.parse_args()

    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        if args.session:
            await show_session(db, args.session)
        else:
            await list_sessions(db)


async def list_sessions(db):
    rows = (await db.execute(text("""
        SELECT s.id, s.title, s.company, s.role,
               s.started_at, s.ended_at, s.duration_seconds,
               COUNT(DISTINCT t.id) AS transcript_lines,
               COUNT(DISTINCT i.id) AS interactions
        FROM cluely_sessions s
        LEFT JOIN cluely_transcript_lines t ON t.session_id = s.id
        LEFT JOIN cluely_interactions     i ON i.session_id = s.id
        GROUP BY s.id
        ORDER BY s.started_at DESC
    """))).fetchall()

    if not rows:
        print("No sessions found.")
        return

    print(f"\n{'-'*90}")
    print(f"  {'TITLE':<30} {'COMPANY/ROLE':<25} {'STARTED':<20} {'DUR':>6}  {'TX':>4}  {'AI':>4}")
    print(f"{'-'*90}")
    for r in rows:
        company_role = f"{r.company or '—'} / {r.role or '—'}"
        started = str(r.started_at)[:16] if r.started_at else '—'
        dur = f"{r.duration_seconds}s" if r.duration_seconds else '—'
        print(f"  {(r.title or '—'):<30} {company_role:<25} {started:<20} {dur:>6}  {r.transcript_lines:>4}  {r.interactions:>4}")
        print(f"  {'ID: ' + r.id:<88}")
        print(f"{'-'*90}")

    print(f"\n  {len(rows)} session(s). TX=transcript lines  AI=AI interactions")
    print(f"  Run with --session <id> for full transcript + interactions.\n")


async def show_session(db, session_id):
    session = (await db.execute(text("""
        SELECT * FROM cluely_sessions WHERE id = :id
    """), {"id": session_id})).fetchone()

    if not session:
        print(f"Session {session_id} not found.")
        return

    print(f"\n{'='*70}")
    print(f"  SESSION: {session.title}")
    print(f"  ID:      {session.id}")
    print(f"  Role:    {session.role or '—'} at {session.company or '—'}")
    print(f"  Started: {session.started_at}  Ended: {session.ended_at or '(open)'}")
    print(f"  Duration:{f' {session.duration_seconds}s' if session.duration_seconds else ' —'}")
    if session.post_summary:
        print(f"\n  SUMMARY: {session.post_summary}")
    print(f"{'='*70}")

    # Transcript
    lines = (await db.execute(text("""
        SELECT speaker, text, seq, spoken_at
        FROM cluely_transcript_lines
        WHERE session_id = :id
        ORDER BY seq
    """), {"id": session_id})).fetchall()

    if lines:
        print(f"\n  TRANSCRIPT ({len(lines)} lines):")
        print(f"  {'-'*66}")
        for l in lines:
            spk = "YOU " if l.speaker == "user" else "INT "
            ts  = str(l.spoken_at)[:19] if l.spoken_at else ""
            print(f"  {spk} [{ts}]  {l.text}")
    else:
        print("\n  No transcript lines.")

    # AI interactions
    interactions = (await db.execute(text("""
        SELECT trigger_type, question_text, inferred_outcome, ai_response, mode, occurred_at
        FROM cluely_interactions
        WHERE session_id = :id
        ORDER BY occurred_at
    """), {"id": session_id})).fetchall()

    if interactions:
        print(f"\n  AI INTERACTIONS ({len(interactions)}):")
        print(f"  {'-'*66}")
        for ix in interactions:
            print(f"\n  [{ix.trigger_type.upper()}] {str(ix.occurred_at)[:19]}  mode={ix.mode or '—'}")
            if ix.question_text:
                print(f"  Q: {ix.question_text[:120]}")
            if ix.inferred_outcome:
                print(f"  Outcome: {ix.inferred_outcome[:100]}")
            print(f"  A: {(ix.ai_response or '')[:300]}")
    else:
        print("\n  No AI interactions.")

    print()


if __name__ == "__main__":
    asyncio.run(main())
