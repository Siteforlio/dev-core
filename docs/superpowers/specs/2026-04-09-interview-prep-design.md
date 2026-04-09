# Developer Core — Interview Prep Module: Design Spec
**Date:** 2026-04-09  
**Status:** Approved  
**Platform:** Cross-platform Desktop (Windows, macOS, Linux)

---

## 1. Vision

A photorealistic AI-powered interview simulator that knows the company, knows the hiring manager, reads your face, understands your accent, and tells you exactly why you passed or failed — before you ever walk into the real thing.

Every practice session contributes to a growing community knowledge graph of companies, hiring managers, interview styles, and round patterns — so the more people use it, the smarter it gets for everyone.

---

## 2. Core Principles

- **Walking Skeleton:** Every phase ships a complete, working experience — just at increasing fidelity. You never have a broken product between steps.
- **Data is the moat:** The community knowledge graph is the core differentiator. Every interview session makes it smarter.
- **Privacy by design:** Users consent at onboarding. All contributed data is anonymized. Users own their data.
- **Language-first:** The system understands the user — their accent, their language, their code-switching. The user never has to adapt to the tool.

---

## 3. Architecture

### 3.1 High-Level

```
[Electron Shell]
  ├── Camera / Mic capture
  ├── Interview UI (video call view, code editor, feedback panel)
  ├── Onboarding & Auth UI
  └── IPC bridge → FastAPI backend

[FastAPI Backend — modular]
  ├── Interview Engine       — round management, pass/fail logic, session state
  ├── Avatar Service         — HeyGen/Simli real-time photorealistic avatar
  ├── Emotion Service        — MediaPipe face analysis (real-time + post-session)
  ├── Speech Service         — Whisper (20+ languages, code-switching aware)
  ├── Knowledge Graph API    — Neo4j (managers, companies, round nodes)
  ├── LLM Orchestrator       — Claude/GPT, builds interviewer persona from context
  └── Job/Company Context    — ingests job description, company research, JD tailoring

[Databases]
  ├── Neo4j        — hiring managers, companies, interview patterns, round nodes
  └── PostgreSQL   — users, sessions, round grades, interview profiles, reports

[Cache & Scale]
  └── Redis        — session state, rate limiting, WebSocket pub/sub
```

### 3.2 Key Technology Choices

| Concern | Technology | Reason |
|---|---|---|
| Desktop shell | Electron | Mature ecosystem, best cross-platform camera/mic/screen access |
| Backend | FastAPI (Python) | Ideal for AI/ML integrations, async, fast to develop |
| Knowledge graph | Neo4j | Purpose-built for manager→company→round relationship traversal |
| Relational data | PostgreSQL | Users, sessions, grades, reports |
| Speech recognition | OpenAI Whisper | 99-language support, code-switching capable |
| Avatar | HeyGen / Simli | Photorealistic, real-time lip-sync |
| Emotion detection | MediaPipe | Real-time face landmarks, emotion inference |
| LLM | Claude (Anthropic) | Persona generation, question synthesis, debrief analysis |
| Cache | Redis | Session state at scale, WebSocket coordination |
| Containerization | Docker + Docker Compose | Dev parity, easy deployment |

---

## 4. Data Model

### 4.1 Knowledge Graph (Neo4j)

```
(Company) -[:HAS_ROUND]-> (Round)
(Round) -[:HAS_QUESTION]-> (Question)
(HiringManager) -[:WORKS_AT]-> (Company)
(HiringManager) -[:PREVIOUSLY_AT]-> (Company)
(HiringManager) -[:CONDUCTED]-> (Round)
(Round) -[:RESULTED_IN]-> (Outcome {passed: bool, notes: str})
(Outcome) -[:OBSERVED_BEHAVIOR]-> (Behavior {type: str, sentiment: positive|negative})
```

**Key insight:** HiringManager nodes persist across company changes. When a manager moves from Meta to Google, their personality profile — what they liked, what they didn't — travels with them.

### 4.2 Relational (PostgreSQL)

```
users               — id, name, email, language_pref, consent_given_at
sessions            — id, user_id, company, role, started_at, ended_at
rounds              — id, session_id, type (HR|behavioral|technical|leetcode|sysdesign), grade, passed
round_moments       — id, round_id, timestamp, question, answer, emotion_state, ai_reaction
interview_profiles  — id, session_id, pdf_url, summary, strengths, weaknesses
community_data      — staging buffer for anonymized session data pending Neo4j write; acts as audit log after write completes
```

**`community_data` clarification:** After a session ends, anonymized data is written to `community_data` first (as a staging buffer and permanent audit trail), then asynchronously flushed to Neo4j. This decouples the session-end write from the graph write, prevents data loss if Neo4j is temporarily unavailable, and provides an audit log of all contributed data.

---

## 5. Core Flows

### 5.1 Interview Session Flow

```
User selects company + role + interview type
  → LLM Orchestrator queries Knowledge Graph for:
      - Known hiring managers at this company
      - Past round structures
      - What managers liked/disliked
      - Past questions asked
  → Builds interviewer persona
  → Avatar renders with that persona
  → Round 1 begins

Per Round:
  → AI asks questions (voice + avatar)
  → User responds (voice, 20+ languages)
  → Emotion service reads face in real-time
  → Subtle feedback panel updates (confidence, eye contact)
  → AI grades answer, updates session state
  → Round ends → Pass/Fail decision
      - FAIL: session stops, debrief shown, user repeats round
      - PASS: move to next round

Session ends → Full debrief report generated → PDF profile saved
```

### 5.2 Community Data Flow

```
Session ends
  → User data anonymized (names stripped, IDs hashed)
  → Round structure, questions, manager reactions written to Neo4j
  → HiringManager node updated (if new signals observed)
  → Community pool grows
```

### 5.3 Hiring Manager Cross-Company Tracking

```
Manager "Job" previously at Meta → now at Google
  → Neo4j query: MATCH (m:HiringManager {name: "Job"})-[:PREVIOUSLY_AT]->(c)
  → Retrieve all behavioral signals from Meta rounds
  → Merge with Google context
  → Persona engine: "Job values confidence, dislikes vague answers, asks follow-up on system design details"
```

---

## 6. Interview Round Types

| Round | What Happens |
|---|---|
| HR Screen | Conversational, avatar in natural mode, behavioral questions |
| Behavioral | STAR-format questions, emotion tracking active |
| Technical | Verbal technical questions, whiteboard-style explanation |
| LeetCode / Coding | Split screen: avatar left, live code editor right. AI reacts as you code. |
| System Design | Open-ended architecture discussion, AI probes depth |

---

## 7. Emotion & Face Analysis

**Real-time (during session):**
- Eye contact score
- Confidence indicator
- Nervousness signal
- Minimal, non-distracting UI — a subtle sidebar strip

**Post-session debrief:**
- Timeline of emotional state across the interview
- Specific moments flagged: "At 4:23 you looked away when asked about conflict resolution"
- Correlation: "When you seemed nervous, the interviewer's questions became harder"
- Scores per dimension: confidence, clarity, composure, engagement

---

## 8. Language & Accent Support

- **Whisper** handles 99 languages out of the box
- **Code-switching aware:** if a user mixes Swahili and English mid-sentence, system uses conversation context to infer meaning
- **Response language:** AI always responds in the user's selected preferred language (set at onboarding)
- **Launch:** English primary, all 20+ Whisper-supported languages available for understanding from day one
- **Accent adaptation:** Whisper's multilingual model handles regional accents without special configuration

---

## 9. Build Steps (Walking Skeleton)

Each step produces a shippable increment. Every step extends the whole product — not just one layer.

**Testing rule (applies to every step):** No step is complete until the code it introduces has unit tests for all service-layer functions and integration tests for all new API routes. 80% coverage minimum on new code. Steps introducing E2E-testable user flows (Steps 3, 6, 14, 15) must include an E2E test. See ARCHITECTURE.md Section 8 for full testing standards.

| Step | What Gets Built | Success Gate |
|---|---|---|
| 1 | Project setup — Electron + FastAPI scaffold, Docker, CI, linting, ARCHITECTURE.md | Dev environment runs on all 3 platforms |
| 2 | Database foundation — PostgreSQL schema, Neo4j setup, migrations | Both DBs connect, migrations run cleanly |
| 3 | Auth & onboarding — signup, login, language pref, consent flow | User can create account and set preferences |
| 4 | Job & company selection UI — pick company, role, interview type | Selection screen feeds context downstream |
| 5 | LLM orchestrator — generates interview questions from company + role. When no graph data exists, falls back to LLM general knowledge for that company/role. Graph-powered persona activates in Step 18. | AI returns relevant questions for any company/role combo |
| 6 | Text interview session — full loop: AI asks → user types → AI responds → saved | Complete interview session runs start to finish in text |
| 7 | Text-to-speech — AI interviewer speaks | AI voice heard during session |
| 8 | Speech-to-text — user speaks, Whisper transcribes (20+ languages) | User speaks in any supported language, transcript is accurate |
| 9 | Static avatar — visible AI interviewer, basic lip-sync | Interview feels like a video call |
| 10 | Photorealistic avatar — HeyGen/Simli real-time rendering | Avatar is indistinguishable from a real video call |
| 11 | Basic emotion detection — MediaPipe reads face, stores data | Smile, neutral, eye contact detected and stored |
| 12 | Real-time feedback panel — subtle in-session nudges | Confidence/eye contact indicator visible during session |
| 13 | Post-session debrief — scored report with emotion moments flagged | User receives full breakdown after every session |
| 14 | Multi-round pipeline — HR, behavioral, technical rounds in sequence | User moves through multiple rounds in one session |
| 15 | Pass/fail per round — AI grades, failed round stops session | Session stops at failed round, debrief explains why |
| 16 | Code editor round — split screen using Monaco Editor (VS Code's editor, supports 40+ languages), live coding, AI observes code changes via WebSocket keystroke stream and reacts verbally | Full LeetCode-style round works end-to-end |
| 17 | Knowledge graph seeded — 10 companies, manager nodes, round patterns | Querying graph returns useful prep context |
| 18 | Hiring manager persona engine — LLM builds persona from graph | Avatar takes on hiring manager's known style |
| 19 | Community data pipeline — anonymized session data feeds graph | Post-session data writes to Neo4j community pool |
| 20 | Cross-company manager tracking — manager moves, profile follows | Prep reflects manager's history across companies |
| 21 | Advanced emotion analysis — confidence scoring, code-switching, accent-aware | Debrief includes nuanced emotional timeline |
| 22 | Interview profile report — shareable PDF with full session breakdown | PDF generated after every session |
| 23 | Scale hardening — Redis, WebSockets, horizontal scaling, 5k load test | 5k concurrent sessions, <200ms API response |
| 24 | Security hardening & compliance audit — pen test, anonymization audit, GDPR review. Note: baseline security (JWT auth, input validation, parameterized queries, CORS lockdown, TLS) is enforced from Step 3 onwards per ARCHITECTURE.md. Step 24 is a formal audit pass, not the first time security is applied. | Zero data leaks confirmed by external audit, GDPR compliant |

---

## 10. Scale Target

- **5,000 concurrent users** with no degradation
- **<200ms API response** for all non-avatar endpoints
- **WebSocket** for real-time emotion feedback and avatar sync
- **Redis** for session state, rate limiting, pub/sub
- **Horizontal scaling** via stateless FastAPI workers behind a load balancer
- **Neo4j cluster** for graph read scaling

---

## 11. Privacy & Data Policy

- Consent given at onboarding — users agree data improves the platform
- All community-contributed data is anonymized before writing to graph
- User names, emails, and PII never enter Neo4j
- Interview recordings stored locally by default; cloud sync is opt-in
- Users can delete their data at any time
- GDPR compliance built into Step 24

---

## 12. Success Definition

The Interview Prep module succeeds when:
1. A user can run a complete multi-round interview for any major tech company
2. The AI interviewer adapts its persona based on known hiring manager data
3. The debrief report tells the user exactly what they need to fix
4. Community data makes every subsequent user's prep smarter
5. The system handles 5,000 concurrent sessions without degradation
