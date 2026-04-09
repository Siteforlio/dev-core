# Developer Core — Architecture & Engineering Standards

> This document is the single source of truth for how this codebase is built.
> Every developer — human or AI — must read and follow this before touching any code.
> When starting a new chat, load this file first.

---

## 1. Project Overview

Developer Core is a cross-platform desktop application (Windows, macOS, Linux) built with Electron + FastAPI. It consists of three modules:

1. **Interview Prep** — AI-powered interview simulator with photorealistic avatar, emotion detection, and community knowledge graph
2. **Job Hunter** — AI job matching, auto-apply, resume tailoring *(planned)*
3. **Cluely** — Real-time AI screen overlay assistant *(planned)*

Each module is designed as an independently deployable unit that shares the same shell and infrastructure.

---

## 2. Tech Stack

| Layer | Technology | Version Policy |
|---|---|---|
| Desktop shell | Electron | Latest LTS |
| Frontend | React + TypeScript | Latest stable |
| Styling | Tailwind CSS | Latest stable |
| Backend | FastAPI (Python) | 3.11+ |
| Knowledge graph | Neo4j | 5.x |
| Relational DB | PostgreSQL | 15+ |
| Cache / pub-sub | Redis | 7.x |
| Speech | OpenAI Whisper | Latest |
| Avatar | HeyGen / Simli API | Per provider |
| Emotion detection | MediaPipe | Latest |
| LLM | Anthropic Claude API | claude-sonnet-4-6 (default) |
| Containerization | Docker + Docker Compose | Latest stable |
| CI | GitHub Actions | — |

---

## 3. Repository Structure

```
developer-core/
├── electron/                  # Electron main process
│   ├── main.ts                # App entry point
│   ├── preload.ts             # IPC bridge (contextBridge)
│   └── ipc/                   # IPC handler definitions
├── frontend/                  # React frontend (Electron renderer)
│   ├── src/
│   │   ├── components/        # Reusable UI components
│   │   ├── pages/             # Page-level components
│   │   ├── hooks/             # Custom React hooks
│   │   ├── store/             # State management (Zustand)
│   │   └── types/             # Shared TypeScript types
│   └── public/
├── backend/                   # FastAPI backend
│   ├── app/
│   │   ├── main.py            # FastAPI app entry
│   │   ├── api/               # Route handlers (one file per module)
│   │   ├── services/          # Business logic (one file per service)
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas (request/response)
│   │   ├── graph/             # Neo4j query layer
│   │   ├── core/              # Config, security, middleware
│   │   └── workers/           # Background tasks (Celery or asyncio)
│   ├── migrations/            # Alembic migrations
│   └── tests/                 # Backend tests
├── docs/
│   └── superpowers/
│       └── specs/             # Design specs per feature
├── docker/                    # Dockerfiles per service
├── docker-compose.yml         # Local dev environment
├── ARCHITECTURE.md            # This file
└── .github/
    └── workflows/             # CI pipelines
```

---

## 4. Backend Code Rules

### 4.1 Module Boundaries

Each backend module (interview, job-hunter, cluely) is a self-contained package:
- Its own router in `api/`
- Its own service in `services/`
- Its own models in `models/`
- Modules communicate only through defined service interfaces — never by importing each other's internals directly

### 4.2 Layering (strict, no exceptions)

```
Route Handler (api/)
  → Service (services/)       ← all business logic lives here
    → Repository / Graph (models/ or graph/)   ← all DB access lives here
      → Database
```

- Route handlers do: validate input, call service, return response. Nothing else.
- Services do: orchestrate logic, call repositories. No raw SQL or Cypher here.
- Repositories do: database queries only. No business logic.

### 4.3 Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Files | snake_case | `interview_engine.py` |
| Classes | PascalCase | `InterviewEngine` |
| Functions / methods | snake_case | `get_session_by_id` |
| Constants | UPPER_SNAKE_CASE | `MAX_ROUNDS` |
| Pydantic schemas | PascalCase + suffix | `SessionCreateRequest`, `SessionResponse` |
| API routes | kebab-case | `/interview-sessions/{id}` |
| Frontend components | PascalCase | `InterviewPanel.tsx` |
| Frontend hooks | camelCase + `use` prefix | `useInterviewSession` |
| Frontend files | PascalCase for components, camelCase for hooks/utils | |

### 4.4 API Design

- RESTful by default. Use WebSockets only for real-time streams (emotion data, avatar sync).
- All endpoints return consistent response envelopes:
  ```json
  { "data": {}, "error": null, "meta": {} }
  ```
- Errors always include a machine-readable `code` and human-readable `message`:
  ```json
  { "data": null, "error": { "code": "SESSION_NOT_FOUND", "message": "..." } }
  ```
- Version all API routes: `/api/v1/...`

### 4.5 Async

- All FastAPI route handlers must be `async def`
- All database calls must use async drivers (asyncpg for PostgreSQL, neo4j async driver)
- Never block the event loop — use `asyncio.to_thread()` for CPU-bound operations

### 4.6 Configuration

- All config via environment variables — never hardcoded
- Use Pydantic `BaseSettings` for typed config
- `.env.example` always kept up to date
- Secrets never committed to git

---

## 5. Frontend Code Rules

### 5.1 Component Rules

- One component per file
- Components are pure where possible — side effects only in hooks
- No business logic in components — extract to custom hooks
- Props interfaces always explicitly typed (no `any`)

### 5.2 State Management

- Local UI state: `useState` / `useReducer`
- Shared app state: Zustand stores (one store per module)
- Server state: React Query (caching, refetching, optimistic updates)
- No prop drilling beyond 2 levels — use context or store

### 5.3 IPC (Electron ↔ Frontend)

- All IPC channels defined in `electron/ipc/` with explicit TypeScript types
- Frontend never calls `ipcRenderer` directly — always through typed wrapper functions
- IPC handlers in main process are thin — delegate to backend via HTTP/WebSocket

---

## 6. Database Rules

### 6.1 PostgreSQL

- All schema changes via Alembic migrations — never manual
- Migrations are reversible (always define `downgrade()`)
- Foreign keys enforced at DB level
- Indexes on all foreign keys and frequently queried columns
- Soft deletes where data has audit value (`deleted_at` timestamp)

### 6.2 Neo4j

- Node labels: PascalCase (`HiringManager`, `Company`, `Round`)
- Relationship types: UPPER_SNAKE_CASE (`WORKS_AT`, `CONDUCTED`, `HAS_QUESTION`)
- All graph queries in `backend/app/graph/` — never inline Cypher in services
- Parameterized queries always — never string-interpolated Cypher

### 6.3 Redis

- Key naming convention: `{module}:{entity}:{id}:{field}` e.g. `interview:session:abc123:state`
- TTLs always set — never store without expiry unless explicitly intentional
- Used for: session state, rate limiting, WebSocket pub/sub, short-term caching

---

## 7. Security Rules

- **Authentication:** JWT (short-lived access token + refresh token). Tokens stored in memory (not localStorage).
- **Authorization:** Role-based. Every route checks permissions explicitly.
- **Input validation:** All user input validated via Pydantic schemas before processing.
- **SQL injection:** Impossible by rule — ORM only (SQLAlchemy). Raw queries only in migrations.
- **Cypher injection:** Impossible by rule — parameterized queries only.
- **Secrets:** Managed via environment variables. Rotate regularly. Never log secrets.
- **CORS:** Locked down to known origins. No wildcard in production.
- **Rate limiting:** Applied at API gateway level and per-user via Redis.
- **Data anonymization:** PII stripped before any data enters Neo4j community pool.
- **Encryption:** All data encrypted at rest (DB-level) and in transit (TLS 1.3 minimum).

---

## 8. Testing Standards

- **Unit tests:** All service-layer functions. Mock repositories.
- **Integration tests:** All API routes. Use real test databases (no mocks for DB).
- **E2E tests:** Critical user flows (interview session, onboarding, auth).
- **Coverage target:** 80% minimum for backend services.
- **Test file location:** Mirror source structure. `tests/services/test_interview_engine.py` tests `services/interview_engine.py`.
- **Naming:** `test_<function>_<scenario>_<expected_outcome>`

---

## 9. Error Handling

- All exceptions caught at the service layer — never let raw exceptions reach route handlers
- Use custom exception classes per domain (`InterviewNotFoundError`, `RoundFailedError`)
- FastAPI exception handlers in `core/exceptions.py` map domain exceptions to HTTP responses
- Unhandled exceptions → 500 with generic message (never expose stack traces in production)
- All errors logged with correlation ID for tracing

---

## 10. Logging & Observability

- Structured JSON logs (not plain text) — use `structlog`
- Every request gets a `correlation_id` (UUID) — passed through all layers
- Log levels: DEBUG (dev only), INFO (request lifecycle), WARNING (recoverable issues), ERROR (failures)
- Never log PII or secrets
- Performance: log slow queries (>100ms) and slow API responses (>500ms)

---

## 11. Scaling Principles

The system must handle **5,000 concurrent users** with <200ms API response.

- **Stateless backend:** No in-process state. All state in Redis or DB.
- **Horizontal scaling:** Multiple FastAPI worker instances behind a load balancer.
- **WebSocket scaling:** Redis pub/sub coordinates messages across instances.
- **Database connection pooling:** asyncpg pool for PostgreSQL, connection pool for Neo4j.
- **Avatar/AI calls:** Async, non-blocking. Long-running avatar renders go to a task queue.
- **Heavy workloads:** Emotion analysis, LLM calls, PDF generation → background workers, not request thread.

---

## 12. Git Workflow

- `main` — always deployable. Protected branch.
- `dev` — integration branch. PRs merge here first.
- Feature branches: `feat/<step-number>-<short-description>` e.g. `feat/06-text-interview-session`
- Commit messages: imperative, present tense. `Add interview round pass/fail logic`
- Every PR references a build step number from the spec
- No force pushes to `main` or `dev`

---

## 13. Build Steps Reference

See full detail in [docs/superpowers/specs/2026-04-09-interview-prep-design.md](docs/superpowers/specs/2026-04-09-interview-prep-design.md)

| Step | Summary |
|---|---|
| 1 | Project setup & scaffolding |
| 2 | Database foundation |
| 3 | Auth & onboarding |
| 4 | Job & company selection UI |
| 5 | LLM orchestrator |
| 6 | Text interview session |
| 7 | Text-to-speech |
| 8 | Speech-to-text (Whisper, 20+ languages) |
| 9 | Static avatar |
| 10 | Photorealistic avatar |
| 11 | Basic emotion detection |
| 12 | Real-time feedback panel |
| 13 | Post-session debrief |
| 14 | Multi-round pipeline |
| 15 | Pass/fail per round |
| 16 | Code editor round |
| 17 | Knowledge graph seeded |
| 18 | Hiring manager persona engine |
| 19 | Community data pipeline |
| 20 | Cross-company manager tracking |
| 21 | Advanced emotion analysis |
| 22 | Interview profile report |
| 23 | Scale hardening |
| 24 | Security & compliance |

---

## 14. Starting a New Chat

When beginning a new Claude Code session on this project:

1. Read `ARCHITECTURE.md` (this file)
2. Read the relevant spec in `docs/superpowers/specs/`
3. Check which build step is currently in progress
4. Follow the layering rules (Section 4.2) without exception
5. Follow naming conventions (Section 4.3) without exception
6. Never introduce a new technology without updating this file first
