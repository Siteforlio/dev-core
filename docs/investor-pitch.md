# Developer Core — Investor Memo

**To:** Investment Committee
**From:** Evaluating Partner
**Re:** Developer Core — Pre-Seed Investment Opportunity
**Date:** July 2026

---

## The Recommendation

**Invest.**

I rarely say that this cleanly. Here is why I am saying it now.

---

## The Problem That Nobody Has Actually Solved

Every year, roughly 1.5 billion people globally look for a new job. Of those, a meaningful and growing slice are technical workers — software engineers, data scientists, product managers — who have money, are comfortable with tools, and are actively underserved by what exists.

Here is what the current market forces a serious job seeker to assemble on their own:

| Service | What it does | Monthly cost |
|---|---|---|
| LinkedIn Premium | Job discovery, recruiter signals | $40–$100 |
| Rezi / Kickresume | Resume tailoring | $20–$30 |
| JobScan | ATS keyword matching | $25–$50 |
| Interview.io | Mock technical interviews | $225–$350 |
| Pramp | Peer interview practice | $50–$150 |
| Cluely | Real-time AI overlay during live interviews | $20–$80 |
| Grammarly / copy tools | Communication polish | $12–$30 |

A serious candidate running all of these simultaneously spends **$400–$800/month** — often for months. Most people cannot sustain that. Most people quit one or two of these services early, and their job search suffers for it.

The deeper problem is not even the cost. It is the **fragmentation**. None of these tools talk to each other. The resume tailored in Rezi does not know what you practiced in Interview.io. The rejection signals caught in your email do not feed back into your job scraping strategy. Every tool treats you as a fresh user with no context. You are managing your own career strategy manually, across five dashboards, with no intelligence connecting them.

**The career software industry is 2010-era SaaS applied to a deeply interconnected problem.**

---

## Why AI API Commoditization Changes Everything Right Now

The reason nobody has cracked this is infrastructure cost. Running an AI-powered job scraper, a real-time transcription pipeline, emotion detection, a coding sandbox, and an LLM orchestration layer simultaneously — a year ago, that was a $50,000/month cloud bill for a startup.

That window has closed.

DeepSeek-V3 runs at roughly $0.27 per million input tokens. Gemini Flash is even cheaper, with a free tier. Deepgram speech transcription is $0.0059/minute — and offers 200 hours free per month. Local sentence-transformer models run on CPU in milliseconds with zero API cost.

**The marginal cost of running a full-stack AI career system has dropped to near-zero.** The main bottleneck was never insight or architecture — it was inference cost. That bottleneck is gone.

This means a developer with genuine product conviction can now ship a system that would have required a Series A infrastructure budget twelve months ago. Developer Core has done exactly that.

---

## What Developer Core Actually Is

Developer Core is a self-hosted, open-source desktop application — built on Electron — that replaces every expensive career SaaS product with a single system running on your own machine. The only ongoing cost to the user is an API key from any LLM provider of their choice.

It is not a wrapper around one model. It is a full-stack system with three production-grade modules:

### Phase 1 — Job Hunter

An autonomous job search agent. It scrapes 20+ job boards in parallel — LinkedIn, Indeed, Greenhouse, Lever, Ashby, Wellfound, Remotive, startup boards, and African-market boards including Zindi, BrighterMonday, and Fuzu — and runs every result through a multi-layer filter: keyword pre-screening, work-type matching, then AI match scoring. Matched jobs get a fully tailored resume generated per-role, with immutable credential protection (the AI cannot hallucinate your job titles or education), ATS keyword injection, and domain translation for career-switchers.

It then auto-applies. Greenhouse, Lever, Ashby, Workday, and any generic ATS are filled via Chromium automation. When a CAPTCHA appears, it pings the user for a single click. When an email arrives with an interview invite or rejection, it classifies it, drafts a reply, and creates a calendar event.

A campaign dashboard shows total applications, response rate, interviews, and offers across all active search campaigns.

### Phase 2 — Interview Prep

A realistic AI interview simulator. The user describes what they want to practice in plain English — *"simulate a Google system design round with a senior SWE interviewer"* — and the system parses 18 signal types from that sentence, constructs a named AI interviewer persona grounded in a Neo4j knowledge graph of real company interview patterns, and runs a multi-round structured interview.

During the session: live camera feed with 468-landmark MediaPipe face analysis, real-time emotion detection (confident / nervous / uncertain / engaged), live transcription, and a countdown timer. AI graders score answers 1–10 on seven dimensions. Scores below 3.0 terminate the round immediately. Brutal, honest feedback — not encouragement.

After the session: a full PDF debrief generated by DeepSeek-R1, the reasoning model, covering dimension scores, strengths, areas for improvement, and a focus plan for the next session.

The knowledge graph learns. Every anonymized session (PII stripped) feeds back into Neo4j, making company-specific personas more accurate over time. This is a data flywheel with a moat.

### Phase 3 — Screen Overlay

An invisible AI co-pilot for live interviews and meetings. It captures dual audio (microphone and system loopback simultaneously), runs speaker diarization to know who is talking, transcribes in real time via Deepgram, detects questions using a locally-running BERT classifier, infers what a strong answer must demonstrate, checks whether the user's live response is drifting off target, and streams a first-person AI suggestion — all in real time, displayed in a window that is cryptographically hidden from Zoom, Teams, OBS, and any screen capture tool via the Windows `WDA_EXCLUDEFROMCAPTURE` API.

It also has a full agentic mode: LeetCode problems are solved by reading test cases from screenshots, running code in a local sandbox, iterating until tests pass, and streaming the solution to the overlay. The user's own codebase is indexed with a hybrid RAG engine, meaning in live coding sessions the AI has full context of the candidate's actual work.

---

## The Competitive Landscape Is Built for This to Win

| Competitor | What they offer | What they lack | Monthly cost |
|---|---|---|---|
| Cluely | Screen overlay only | No job hunting, no prep, data sent to their servers, no self-hosting | $20–$80 |
| Interview.io | Human mock interviews | No automation, no emotion detection, no link to your applications | $225–$350 |
| Pramp | Peer practice matching | No AI, no job hunting, no integration | $50–$150 |
| Rezi / JobScan | Resume tailoring | No scraping, no auto-apply, no interview prep | $20–$50 |
| LinkedIn Premium | Job discovery | Passive, expensive, no coaching, apply manually | $40–$100 |

None of them talk to each other. None of them run locally. None of them let you bring your own API key. None of them have a community knowledge graph getting smarter with every user.

Developer Core's positioning is not "better resume tool" or "better mock interview." It is **the end of the career SaaS stack** — one system, self-hosted, zero vendor lock-in.

---

## The Open-Source Strategy Is the Moat

Developer Core is MIT-licensed and open source. Most investors hear "open source" and think "no revenue." That is the wrong frame. The right frame is: **open source is the distribution strategy that makes every other moat compound faster.**

When a developer discovers this project, they trust it immediately — they can read the code. They know nothing is phoning home. They install it, use it seriously during their job search, and tell every engineer they know. GitHub stars, Discussions, and Discord are the growth engine.

Critically: every anonymized session contributed to the Neo4j knowledge graph is only valuable in aggregate. A self-hosted instance contributes to the shared pool, but the shared pool only exists because the network is large. **The more people use it, the better everyone's interview simulations get.** That is a real network effect, running inside an open-source project. That combination is rare.

The business model follows naturally:

| Tier | Offer | Price |
|---|---|---|
| Open Source | Self-hosted, full features, forever free | $0 |
| Cloud Hosted | Managed instance, no Docker required | $20–$40/month |
| Teams | Shared personas, session libraries, panel tooling | B2B |
| API / Ecosystem | Third parties build on the knowledge graph | License |

The open-source launch is not a delay to revenue. It is the fastest path to the network size that makes the knowledge graph defensible.

---

## Engineering Credibility

Most AI career tools are thin GPT wrappers with a pretty UI. Developer Core is not that.

What has been built and committed to production:

- **Dual audio capture** with WebSocket multiplexing and speaker diarization via resemblyzer voice embeddings
- **MediaPipe FaceMesh** at frame rate on local CPU — 468 landmarks, 5 emotion states, nervousness and confidence scores, real-time gaze direction
- **Hybrid RAG engine** (Model2Vec + BM25 + Reciprocal Rank Fusion + definition boosting + file coherence scoring) — not off-the-shelf
- **Win32 `SetWindowDisplayAffinity`** via koffi FFI for capture-proof overlay on Windows; `NSWindowSharingNone` on macOS — invisible to Zoom, Teams, OBS
- **Neo4j knowledge graph** with a community data pipeline that strips PII before contribution
- **Celery task queues** for parallel scraping across 20+ boards with real-time Redis pub/sub activity feeds
- **BERT question classifier** with zero-shot NLI, hot-swappable after download with no restart
- **Full ReAct agentic loop** with terminal, filesystem, browser, screen, and search tools — streaming every step to the overlay UI
- **Production-grade stack**: Alembic migrations, structlog structured logging, slowapi rate limiting, OS-level DPAPI credential encryption

This is a system designed to scale to 5,000 concurrent users with sub-200ms API response. The architecture is enforced, CI is live, and the engineering depth is real.

**The founder has built something that would take a funded team six months to reproduce.**

---

## Market Timing — Three Forces Converging Now

**1. LLM API cost collapse.**
The compute that makes this system possible now costs the user less than $5/month in API credits for moderate use. Gemini Flash is free for millions of tokens per day. This price floor does not go back up.

**2. White-collar job market compression.**
Senior hiring is selective, layoffs in tech continue, and the candidate-to-opening ratio at desirable companies is at decade highs. Job seekers are desperate for leverage. A tool that applies to 100 jobs per day with tailored resumes and then drills them through realistic interview simulations is not a nice-to-have. For many people, it is the difference between landing and not landing.

**3. Privacy backlash against SaaS career tools.**
Cluely and similar tools have faced coverage about what data they collect and where it goes. Developer Core's self-hosted architecture is not a feature — it is the direct answer to the question users are already asking: *"Who can see what I'm saying in this interview?"*

All three of these trends are accelerating. The window for a self-hosted, open-source, all-in-one entrant is open right now. In eighteen months, well-funded competitors will copy this positioning. Today, there is no one here.

---

## What Investment Enables

This is a solo-built project at MIT license, already past the point of concept risk. What stops it from becoming a large company is distribution, not product.

A seed investment funds:

1. **Public launch infrastructure** — managed cloud instance for non-technical users, CI/CD for the hosted version, analytics
2. **Community growth** — developer advocates, a real Discord, sponsored content in job-seeker communities
3. **Data pipeline acceleration** — the faster the knowledge graph accumulates anonymized sessions, the more valuable the interview simulation becomes; marketing spend directly compounds the moat
4. **Platform expansion** — mobile companion app for in-person interview coaching, team / recruiting version, API licensing

The founder does not need to be taught how to build. They need runway to tell people this exists.

---

## The Honest Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Self-hosting friction for non-technical users | Medium | Cloud-hosted managed version is the answer; investment accelerates it |
| API key dependency | Low | Hosted version bundles cost into subscription; free-tier keys cover most users |
| LinkedIn scraping ToS | Medium | Isolated subprocess behind user credentials; 20+ other boards cover majority of volume |
| Open-source fork risk | Low | Knowledge graph moat cannot be forked — only built with real user sessions over time |

None of these are disqualifying. All of them are manageable with capital.

---

## The Bottom Line

The career software market has been stuck in a fragmented, overpriced, privacy-hostile equilibrium for a decade. API cost commoditization has just removed the last structural barrier to disrupting it. Developer Core has already built the system that disrupts it — fully functional, production-grade, open source, and self-hostable with a single command.

The question is not whether this product is real. It is. The question is whether this is the right moment to accelerate it.

**It is.**

The window where a self-hosted, all-in-one career AI with a community knowledge graph has no direct competitor is not large. The time to own this category is now, before well-funded teams realize what the founder has already figured out.

**I am recommending we invest.**

---

*Developer Core — MIT License — github.com/Statosco/developer-core*
