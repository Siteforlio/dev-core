# Developer Core — Job Hunter Revamp: Design Spec

**Date:** 2026-06-26  
**Status:** Approved  
**Supersedes:** `2026-04-11-job-hunter-design.md` (UI + campaign creation sections only — backend pipeline, email, calendar, and auto-apply remain unchanged)

---

## 1. Vision

Replace the form-based campaign creation wizard and per-campaign dashboard with a unified, AI-first job hunt experience. The AI becomes the primary interface for setting up campaigns, probing the job market, and managing ongoing searches. The unified dashboard surfaces all applied jobs across every campaign in one place.

The user talks to the AI. The AI does the work.

---

## 2. Core Principles

- **Speed first:** Every AI response streams. Every tool call is async and non-blocking. The UI never waits — it renders progress as it arrives.
- **Stateless workers, stateful UI:** All heavy work (scrapes, tailoring, email scans) runs through the existing Celery queue. The AI chat initiates — it never blocks on task completion.
- **Scalable by default:** Chat session state lives in Redis (hot path). Postgres stores durable summaries. No new infrastructure — uses what is already in the stack.
- **Cost discipline:** DeepSeek Flash for all chat turns and tool orchestration. DeepSeek Pro only for career plan generation. Target: < $0.01 per campaign creation session.
- **AI initiates, systems run:** The AI triggers scrapes, tailoring, and email scans via tool calls. It does not run them. Background workers handle execution. The AI surfaces results when they arrive.
- **Persistent AI, focused dashboard:** The AI chat is always available. The dashboard is always the primary surface. Neither competes with the other.

---

## 3. Layout Architecture

### 3.1 Three-Panel Shell

```
┌─────────────────────────────────────────────────────────┐
│  [«] Campaign Sidebar  │  Center Panel  │  AI Chat (✦)  │
│  ─────────────────────  ────────────────  ─────────────  │
│  ✦ New Campaign         Summary Strip    Campaign Brief  │
│                         Tabs             (collapsible)   │
│  ● Remote Frontend  ←   Jobs List /      Chat messages  │
│  ● Kenya Startups       Job Detail /     Tool calls     │
│  ◐ Senior Backend       (mode-dependent) Input bar      │
│  ○ Product Design                                        │
└─────────────────────────────────────────────────────────┘
```

**Left sidebar (160px):**
- Campaign list with status dots (active = cyan glow, paused = amber, idle = dim)
- `✦ New Campaign` button — star icon signals AI-powered creation
- `«` / `»` double-chevron toggle — collapses/expands sidebar with CSS transition
- When collapsed: active campaign name + `▾` dropdown moves into topbar

**Center panel (flex: 1):**
- Topbar: `«»` collapse button + active campaign name/mode label
- Two modes: **All Applications** (global, default on load) and **Campaign View** (per-campaign, activated by clicking a campaign in sidebar)
- Topbar always shows which mode is active so the user is never disoriented
- Content: Summary Strip → Tabs → Jobs List (default) or Job Detail (on row click)

**Right AI chat panel (240px):**
- Always visible, always scrollable
- Header: `✦ Career AI`
- Campaign Brief card pinned at top (collapsible, default collapsed)
- Universal chat messages below
- Below chat: Activity Feed tab toggle (see Section 3.3)
- Input: text only, no file attachment — analysis + tool access only

### 3.2 Center Panel Modes

| Mode | Triggered by | Shows |
|---|---|---|
| All Applications | Default on load | All applied jobs across all campaigns, filterable by tab |
| Campaign View | Clicking a campaign in sidebar | That campaign's applied jobs only, same tab structure |
| Job Detail | Clicking a job row | Job detail fills center — sidebar + AI chat stay unchanged |
| New Campaign | `✦ New Campaign` button | Full-screen AI creation chat overlays center — sidebar hidden |

### 3.3 Summary Strip

Always visible at top of center panel (both modes). Reuses existing `SummaryStrip.tsx` component with the full `CampaignSummary` shape it already expects:

```ts
interface CampaignSummary {
  totalApplications: number
  todayApplications: number
  weekApplications: number
  responses: number
  interviews: number
  offers: number
  rejectionRate: number
}
```

The new `GET /api/v1/job-hunter/dashboard/summary` endpoint (all-campaigns mode) and the existing `GET /api/v1/job-hunter/campaigns/{id}/dashboard` (campaign view mode) must both return all seven fields. No "All Campaigns" filter chip — mode switching is via sidebar selection only.

### 3.4 Activity Feed Placement

The existing `ActivityFeed.tsx` component is preserved and placed in the **right AI chat panel** as a togglable second tab. The chat panel header has two tabs: `✦ AI` and `⟳ Activity`. Selecting Activity replaces the chat messages area with the `ActivityFeed` component. The Campaign Brief card remains pinned above both tabs.

This keeps the activity feed accessible per-campaign without competing with the AI chat or cluttering the center panel.

`CampaignSettings.tsx` moves to a gear icon in the Campaign View topbar — it opens as a slide-over or replaces the center panel content temporarily (same approach as Job Detail center takeover).

---

## 4. Campaign Creation — AI Chat Flow

### 4.1 Overview

Clicking `✦ New Campaign` overlays the center panel with a full-screen streaming AI chat. The sidebar hides. The right AI chat panel is also hidden — this is a focused creation experience.

The AI does two things in one conversation:
1. **Builds the campaign profile** — asks questions, requests files, extracts structured data
2. **Produces the career plan** — probes the live job market, recommends roles, generates a week-by-week plan

When the user confirms, the AI creates the campaign and triggers the first scrape. The screen auto-transitions to the three-panel shell in Campaign View mode for the newly created campaign, with the Activity Feed tab active showing the scrape running live.

### 4.2 Backend: Unified Streaming Endpoint

Campaign creation uses a two-step pattern: create session first, then stream.

**Step 1 — Create session:**
```
POST /api/v1/job-hunter/campaigns/create-session
Body: {}
Response: { session_id: string }  (immediate, no stream)
```

**Step 2 — Open SSE stream:**
```
GET /api/v1/job-hunter/campaigns/create-session/{session_id}/stream
Response: text/event-stream
Events:
  data: { type: "token", content: "..." }       ← AI text token
  data: { type: "tool_start", tool: "...", label: "...", process: "..." }
  data: { type: "tool_result", tool: "...", result: {...} }
  data: { type: "campaign_created", campaign_id: "...", redirect: true }
  data: { type: "error", message: "..." }
```

**Step 3 — Send user messages:**
```
POST /api/v1/job-hunter/campaigns/create-session/{session_id}/message
Body: { content: string }
Response: 200 OK  (triggers AI response on the open SSE stream)
```

**Step 4 — Upload files during creation:**
```
POST /api/v1/job-hunter/campaigns/create-session/{session_id}/upload
Body: multipart/form-data (file)
Response: { file_id: string }
```
The AI references `file_id` in its `parse_file` tool call. Same extraction logic as existing `processContextFile` — reused, not rebuilt.

**Step 5 — Cancel creation:**
```
DELETE /api/v1/job-hunter/campaigns/create-session/{session_id}
```

**AI tool sequence during creation:**
```
Client opens SSE stream → backend starts DeepSeek streaming session
→ AI sends greeting + first question
→ User POSTs message → AI processes, optionally calls tools:
    parse_file(file_id)           → extracted profile fields
    analyze_gaps(profile_data)    → missing fields list
    market_probe(keywords, country, work_types) → job count + salary data
→ AI streams career plan (DeepSeek Pro call, one-time)
→ User confirms → AI calls:
    create_campaign(name, categories, work_types, country) → campaign_id
    create_campaign_profile(campaign_id, profile_data)     → profile_id (atomic upsert)
    trigger_scrape(campaign_id)                            → Celery task dispatched
→ SSE emits: { type: "campaign_created", campaign_id, redirect: true }
→ Frontend transitions to three-panel shell, Campaign View, Activity tab active
```

**Campaign + profile creation atomicity:**
`create_campaign` and `create_campaign_profile` are wrapped in a single Postgres transaction inside the AI tool handler. If profile creation fails after campaign creation, the campaign row is rolled back. If `trigger_scrape` fails (Celery unavailable), the campaign and profile are committed — the user lands on the dashboard and can manually trigger a scrape from the Activity Feed. This is the only failure mode that does not roll back.

**Why SSE not WebSocket for creation:**  
Creation is a one-directional stream from server to client. User messages are short POSTs. SSE is simpler, cheaper to maintain, and scales better under load — no persistent bidirectional connection during idle typing time.

### 4.3 AI Conversation Structure

The AI follows this loose sequence, adapting based on what context the user provides:

```
1. Goal collection
   "What's your goal? (timeline, company type, location, salary range)"

2. Resume / context request
   "Drop your CV or paste your experience — I'll read it directly."
   [User uploads file → file_id returned → AI calls parse_file]

3. Gap fill (if needed)
   AI asks only for fields it couldn't extract — never redundant questions

4. Market probe (transparent tool call)
   "Checking the live market for you…"
   → market_probe() → returns job counts, top boards, salary range

5. Career plan presentation (DeepSeek Pro)
   AI streams the plan: role recommendation, boards, timeline, salary

6. Confirmation + creation
   "Create this campaign →" CTA rendered in chat
   → user clicks → AI calls create_campaign, create_campaign_profile, trigger_scrape
   → SSE emits redirect event
```

### 4.4 Market Probe

**`POST /api/v1/job-hunter/campaigns/market-probe`** (internal, called by the AI backend only — not exposed to frontend directly)

Lightweight read — does NOT trigger a full scrape:
- Queries `job_listings` table for recent matching listings (last 7 days, same category)
- If insufficient recent data (< 20 listings): fires a single quick JobSpy call via Celery (`market_probe_task.delay()`) with a 10-second `AsyncResult.get(timeout=10)` — routes through the task queue to avoid saturating FastAPI thread pool
- Returns: `{ total_active, top_boards[], salary_range: { min, max }, top_companies[] }`
- Cached in Redis: key `market_probe:{category}:{country}`, TTL 1 hour
- Rate limited: max 5 concurrent market probe Celery tasks (separate Celery queue `probe`, concurrency=5)

### 4.5 Career Plan Output Format

The plan is a structured block streamed at the end of the creation conversation:

```
✦ Career Plan — Remote Frontend · 2 months

Market: 312 senior roles active this week. DevTools + Fintech dominate.
Boards: Greenhouse, Lever, Arc, Remotive
Salary: $110–145k (remote, senior)

Wk 1–2   Tailor resume for DevTools + Fintech vocabulary
Wk 3–6   Apply 15/day via Greenhouse + Lever auto-apply
Wk 7–8   Interview prep + follow-ups · Target 3–5 offers

→ Create this campaign
```

The plan is stored as `campaign_profile.career_plan` (JSONB) and `campaign_profile.creation_chat_summary` (TEXT compressed summary). Both are written atomically with the profile in Section 4.2.

---

## 5. Universal AI Chat — Persistent Panel

### 5.1 Scope

The right-panel AI chat is available in all center panel modes except campaign creation (where the panel is hidden). It maintains one conversation thread per user session. Campaign-specific context is injected dynamically per turn — the chat itself is not campaign-scoped.

### 5.2 Streaming Transport

```
POST /api/v1/job-hunter/chat/message
Body: { content: string, campaign_id?: string }
Response: text/event-stream (SSE)
Events:
  data: { type: "token", content: "..." }
  data: { type: "tool_start", tool: "...", label: "...", process: "..." }
  data: { type: "tool_result", tool: "...", result: {...} }
  data: { type: "done" }
  data: { type: "error", message: "..." }
```

The frontend opens a new SSE stream per message (fetch with `ReadableStream`). The stream closes on `done` or `error`. Session continuity is maintained via `session_id` stored in Zustand, sent as a query parameter: `POST /chat/message?session_id={id}`.

### 5.3 Tool Set

Every tool call is rendered in the chat as: **bold action** on one line, *italic process description* below, no background color, left border line only. Results in monospace green.

| Tool | Action label | What it does | Backend method |
|---|---|---|---|
| `initiate_scrape` | **Initiating scrape** | Dispatches `dispatch_scrape.delay()` | Existing Celery task |
| `lookup_job` | **Looking up job** | Fetches `JobListing` + `Application` detail | Existing `dashboard_service.get_pipeline()` |
| `trigger_tailor` | **Tailoring resume** | Dispatches `tailor_listing.delay()` | Existing Celery task |
| `scan_emails` | **Scanning emails** | Calls `email_service.scan_campaign_emails()` | Existing service method |
| `get_interview_prep` | **Loading interview context** | Calls `bridge_service.get_interview_context()` | Existing service method |
| `update_campaign` | **Updating campaign** | PATCH `status` via `campaign_service.set_status()` (existing). For toggle fields (`email_enabled`, `caldav_enabled`, `linkedin_enabled`): a new `campaign_service.set_toggles(campaign_id, toggles: dict)` method is required — it does a simple column update on `JobHunterCampaign` via the async DB session, matching the pattern of the existing `PATCH /{id}/toggles` route handler. The tool payload: `{ field: "status" \| "email_enabled" \| "caldav_enabled" \| "linkedin_enabled", value: ... }` | `campaign_service.set_status()` (existing) + `campaign_service.set_toggles()` (new, simple column patch) |
| `update_application_status` | **Updating application** | PATCH `application.status` | Existing `PATCH /applications/{aid}/status` |
| `save_career_plan` | **Saving career plan** | Writes `plan` (JSONB) to `campaign_profile.career_plan`, sets `campaign.creation_method='ai'`. Used by legacy CTA flow (Section 6) when AI generates a retroactive plan. Payload: `{ campaign_id, plan: CareerPlan }` | New method `campaign_profile_service.save_career_plan(campaign_id, plan)` — simple JSONB column update + `campaign_service.set_creation_method(campaign_id, 'ai')` |

All tool calls are non-blocking — the AI dispatches and continues the conversation. Results surface via the existing WebSocket activity feed which the AI references on subsequent turns.

### 5.4 Context Management

On every AI turn, the backend assembles a system prompt from four layers:

```
Layer 1 — Structured snapshot (always injected, ~500 tokens, assembled fresh every turn):
  User profile summary (name, skills, years exp)
  All campaigns: id, name, status, applied_count, interview_count
  Active scrape runs (if any, from Redis)
  Scheduled interviews (next 7 days)
  → 3 indexed Postgres queries + 1 Redis read, target < 50ms

Layer 2 — Session history (current session, sliding window 25 turns):
  Full message + tool call history from Redis
  Redis key: chat:session:{user_id}:{session_id}

Layer 3 — Session summaries (previous sessions, last 3, ~300 tokens each):
  Fetched from chat_session_summaries table
  Ordered by session_ended_at DESC, limit 3

Layer 4 — Campaign context (injected only when campaign_id provided in the message):
  That campaign's recent pipeline (last 20 applications, indexed query)
  Recent activity log (last 20 entries)
  Career plan from campaign_profile.career_plan
```

Total context budget: ~4,000 tokens per turn. Fits DeepSeek Flash context window at minimal cost per turn.

### 5.5 Session Persistence

**Session lifecycle:**
- Session starts when the user opens the job hunter module — frontend calls `POST /api/v1/job-hunter/chat/session` → returns `{ session_id }`
- Session ID stored in Zustand as `activeChatSessionId`
- Session ends on **30 minutes of inactivity** (Redis TTL expires — primary path, always works) OR on **explicit close** (best-effort secondary path):
  - `electron/main.ts` adds `app.on('before-quit', (e) => { e.preventDefault(); ... })` handler
  - Handler calls `mainWindow.webContents.send('session-end')` → renderer calls `DELETE /api/v1/job-hunter/chat/session/{session_id}` which triggers synchronous summarization
  - Handler sets a **2500ms hard timeout**: if the backend does not respond within 2500ms (force quit, network error, backend down), the handler calls `app.quit()` regardless — summarization is silently skipped for this session, and the 35-minute Redis TTL + idle timeout path handles eventual cleanup
  - The before-quit path is best-effort. The 30-minute idle summarization path is the reliable path. Implementors must not design features that depend on before-quit summarization being guaranteed

**Storage:**
- Active session history: Redis key `chat:session:{user_id}:{session_id}` (TTL 35 minutes, refreshed on each message)
- Durable summaries: Postgres `chat_session_summaries` table
- Structured snapshot: assembled fresh on every turn from live DB queries — never cached

**Session summarization:**  
On session end (either path), a background summarization call (DeepSeek Flash, < 500 tokens) extracts:
- Key topics discussed
- Decisions made (campaigns created, statuses changed)
- User preferences expressed (company types, salary expectations, etc.)
Written to `chat_session_summaries` with `key_decisions` JSONB.

---

## 6. Campaign Brief Card

Pinned at the top of the AI chat panel above the AI/Activity tab selector. Collapsible (default: collapsed).

**For campaigns created with the new AI flow (`creation_method = 'ai'`):**
- Shows `creation_chat_summary` (compressed narrative)
- Shows `career_plan` (role, boards, timeline, salary rendered from JSONB)
- Date of creation

**For legacy campaigns (`creation_method = 'form'`):**
- Shows campaign settings (categories, work types, country) from the campaign row
- CTA: "This campaign was set up manually. Start a conversation to build a career plan →"
- Clicking CTA: POSTs to `POST /api/v1/job-hunter/chat/message` with a pre-built prompt that includes the campaign's existing profile data and instructs the AI to generate and save a career plan. When the AI's tool call `save_career_plan(campaign_id, plan)` completes (new tool, writes to `campaign_profile.career_plan`), the brief card re-fetches and renders the plan. `creation_method` is updated to `'ai'` at that point.

`creation_method = 'form'` is the canonical signal for legacy detection throughout the codebase.

---

## 7. Job Detail — Center Takeover

Clicking any job row in the jobs list replaces the center panel content with the job detail view. The sidebar and AI chat panel remain unchanged.

**Layout:**
```
Topbar: ← Back | Company · Role | Status pill | Applied date
─────────────────────────────────────────────────────────────
Left (55%):                    Right (45%):
  Job description               Resume strip (tailored PDF)
  (collapsible, stripped HTML)  Cover letter (if generated)
                                Form answers snapshot
                                Apply / Mark as applied button
                                Email events (if applied)
```

The existing `ApplyPanel.tsx` and `TrackingPanel.tsx` are refactored into a single `JobDetailCenter.tsx` component using this two-column layout. The panel mode distinction (apply vs tracking) is determined by `application.status` as before — same data, new container.

---

## 8. Data Model Changes

All additions are additive — no existing columns altered or removed.

```sql
-- New fields on campaign_profiles
ALTER TABLE campaign_profiles
  ADD COLUMN career_plan JSONB,
  ADD COLUMN creation_chat_summary TEXT;

-- New field on job_hunter_campaigns
ALTER TABLE job_hunter_campaigns
  ADD COLUMN creation_method TEXT DEFAULT 'form'
    CHECK (creation_method IN ('form', 'ai'));
-- creation_method = 'form' is the canonical signal for all legacy detection logic

-- New table for AI chat session summaries
CREATE TABLE chat_session_summaries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  campaign_id UUID REFERENCES job_hunter_campaigns(id) ON DELETE SET NULL,
  summary TEXT NOT NULL,
  key_decisions JSONB DEFAULT '{}',
  session_started_at TIMESTAMPTZ NOT NULL,
  session_ended_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_summaries_user ON chat_session_summaries(user_id, session_ended_at DESC);
CREATE INDEX idx_chat_summaries_campaign ON chat_session_summaries(campaign_id, session_ended_at DESC);
```

**Soft-delete note:** `campaign_id` on `chat_session_summaries` uses `ON DELETE SET NULL` (hard FK). Since campaigns use soft deletes (`deleted_at`), all queries joining to `job_hunter_campaigns` must include `AND job_hunter_campaigns.deleted_at IS NULL` or join via the existing `campaign_service` which already applies this filter.

**`campaign_id` population rule:** The `campaign_id` field on a session summary is set to the `campaign_id` that was most recently passed in a `/chat/message` request during that session (i.e., the campaign the user was last actively discussing). If no `campaign_id` was passed in any message during the session, `campaign_id` is `NULL`. This is resolved at summarization time from the session's message history in Redis.

---

## 9. New API Surface

All paths use the existing base `/api/v1/job-hunter/`. All existing endpoints remain unchanged.

| Method | Path | Purpose |
|---|---|---|
| POST | `/campaigns/create-session` | Create creation session, return `{ session_id }` |
| GET | `/campaigns/create-session/{session_id}/stream` | SSE stream for AI creation chat |
| POST | `/campaigns/create-session/{session_id}/message` | Send user message into creation stream |
| POST | `/campaigns/create-session/{session_id}/upload` | Upload file during creation, return `{ file_id }` |
| DELETE | `/campaigns/create-session/{session_id}` | Cancel creation (ESC) |
| POST | `/campaigns/market-probe` | **Server-to-server only** — called by AI backend, not by frontend. No user JWT required; requires internal service header `X-Internal-Token`. Not accessible from the Electron renderer. |
| POST | `/chat/session` | Start universal chat session, return `{ session_id }` |
| DELETE | `/chat/session/{session_id}` | End session, trigger summarization |
| POST | `/chat/message` | Send message to universal AI chat (SSE response, `?session_id=`) |
| GET | `/chat/history` | Current session history from Redis (`?session_id=`). Response: `{ messages: Array<{ role: 'user'\|'assistant', content: string, tool_calls?: ToolCall[], timestamp: number }> }` ordered oldest-first. Tool calls embedded inline on the assistant message that produced them. No pagination — capped at 25 turns by the sliding window. |
| GET | `/dashboard/summary` | All-campaigns aggregated `CampaignSummary` (all 7 fields) |
| GET | `/campaigns/{id}/brief` | Campaign brief card data (plan + summary + settings) |

---

## 10. Frontend Component Map

### New components

| Component | Replaces / extends | Purpose |
|---|---|---|
| `JobHunterShell.tsx` | `Dashboard.tsx` job-hunter routing | Three-panel layout shell, mode routing |
| `CampaignSidebar.tsx` | Campaign list in `CampaignList.tsx` | Left sidebar with collapse, status dots, new campaign button |
| `UnifiedDashboard.tsx` | All-campaigns center content (new) | Global applied jobs view, feeds existing `SummaryStrip` + `ApplicationCard` |
| `CampaignView.tsx` | `CampaignDashboard.tsx` (per-campaign mode) | Per-campaign center content, same SummaryStrip + ApplicationCard |
| `AIChat.tsx` | Right panel (new) | Persistent AI chat panel with AI/Activity tab toggle |
| `CampaignBrief.tsx` | (new) | Collapsible brief card pinned above AI/Activity tabs |
| `CreationChat.tsx` | `CampaignForm.tsx` + `CampaignProfileBuilder.tsx` | Full-screen AI creation flow (SSE client) |
| `ToolCallMessage.tsx` | (new) | Renders tool calls: bold action + italic process + green result, left border only |
| `JobDetailCenter.tsx` | `ApplyPanel.tsx` + `TrackingPanel.tsx` | Center-panel two-column job detail layout |

### Removed after migration (Step 9)
- `CampaignForm.tsx` → replaced by `CreationChat.tsx`
- `CampaignProfileBuilder.tsx` → replaced by `CreationChat.tsx`
- `CampaignList.tsx` → replaced by `CampaignSidebar.tsx`
- `CampaignDashboard.tsx` → split into `CampaignView.tsx` + `UnifiedDashboard.tsx`

### Preserved as-is
- `SummaryStrip.tsx` — used in both `UnifiedDashboard` and `CampaignView`
- `ApplicationCard.tsx` — used in jobs list in both modes
- `ActivityFeed.tsx` — used in AI chat panel Activity tab
- `CampaignSettings.tsx` — accessible via gear icon in Campaign View topbar
- `DidYouApplyPopup.tsx` — unchanged
- `ManualJobModal.tsx` — unchanged
- `StatusBadge.tsx` — unchanged

---

## 11. State Management

The existing `jobHunterStore.ts` is **fully replaced** by a new store with the interface below. The old `ActiveView` union (`'campaigns' | 'profile' | 'create-campaign' | 'build-profile' | 'dashboard'`) and its associated actions (`setActiveView`, `selectCampaign → activeView:'dashboard'`, `reset`) are removed entirely. Migration mapping for reference: `'campaigns' → 'all'`, `'dashboard' → 'campaign'`, `'create-campaign'/'build-profile' → 'creation'`, `'profile'` is dropped (profile building is now inside the creation chat).

```ts
type ActiveView = 'all' | 'campaign' | 'creation' | 'job-detail'

interface JobHunterState {
  // Routing
  activeView: ActiveView
  selectedCampaignId: string | null
  centerJobId: string | null        // which job is open in job-detail mode
  prevView: ActiveView | null       // restored when closeJobDetail() is called

  // UI state
  sidebarCollapsed: boolean
  chatTab: 'ai' | 'activity'       // right panel tab

  // Session
  activeChatSessionId: string | null  // set on module mount via POST /chat/session

  // Actions
  selectCampaign: (id: string) => void       // → activeView='campaign', selectedCampaignId=id
  setAllApplicationsView: () => void          // → activeView='all', selectedCampaignId=null
  openJobDetail: (jobId: string) => void      // → prevView=activeView, activeView='job-detail', centerJobId=jobId
  closeJobDetail: () => void                  // → activeView=prevView, centerJobId=null
  startCampaignCreation: () => void           // → activeView='creation'
  exitCampaignCreation: (campaignId?: string) => void  // → campaignId ? selectCampaign(campaignId) : setAllApplicationsView()
  toggleSidebar: () => void
  setChatTab: (tab: 'ai' | 'activity') => void
  setChatSessionId: (id: string) => void      // called after POST /chat/session resolves on module mount
  reset: () => void                           // → initial state (kept for logout)
}
```

All API data (chat history, pipeline, summary) remains in component-local state or React Query.

---

## 12. Streaming + Real-time Architecture

No new infrastructure. Reuses existing patterns:

| Concern | Mechanism |
|---|---|
| AI creation chat streaming | SSE — GET stream per session, user POSTs messages |
| Universal AI chat streaming | SSE — POST /chat/message returns SSE stream (one stream per message, closes on done) |
| Tool call progress | Existing WebSocket `/ws/campaign/{id}/activity` — AI chat subscribes and surfaces updates |
| Active session history | Redis key `chat:session:{user_id}:{session_id}`, TTL 35min, refreshed per message |
| Market probe cache | Redis key `market_probe:{category}:{country}`, TTL 1hr |
| Market probe execution | Celery `probe` queue, concurrency=5, separate from main worker |

---

## 13. Performance Targets

| Operation | Target | Notes |
|---|---|---|
| Context snapshot assembly | < 50ms | 3 indexed Postgres queries + 1 Redis read |
| AI chat first token (end-to-end) | < 800ms P50 | DeepSeek Flash TTFT is ~400–700ms; not an SLA, dependent on DeepSeek latency |
| Campaign creation full flow (confirm → dashboard) | < 5s | Scrape is async — does not block transition |
| Jobs list load (500 applications, all campaigns) | < 200ms | Single indexed LEFT JOIN query |
| Market probe (cached) | < 10ms | Redis read |
| Market probe (uncached, Celery inline) | < 10s | JobSpy via probe queue, streamed progress shown |
| Session summarization (on close) | < 2.5s | Hard ceiling enforced by 2500ms before-quit timeout; DeepSeek Flash < 500 tokens |

---

## 14. Build Steps

| Step | Piece | Success Gate |
|---|---|---|
| 1 | **DB migrations** — `career_plan` + `creation_chat_summary` on `campaign_profiles`, `creation_method` on `job_hunter_campaigns`, `chat_session_summaries` table with indexes. Celery `probe` queue configured (concurrency=5) | Migrations run cleanly; all indexes created; existing rows backfilled with `creation_method='form'` |
| 2 | **Three-panel shell** — `JobHunterShell`, `CampaignSidebar` with `«»` collapse, topbar mode label, `CampaignView`, `UnifiedDashboard`, Zustand store extension including `activeChatSessionId` + `setChatSessionId`. `POST /chat/session` called on module mount | Sidebar collapses/expands; All Applications and Campaign View modes route correctly; `activeChatSessionId` set in store on mount |
| 3 | **Universal AI chat panel** — `AIChat` with AI/Activity tab toggle, `ToolCallMessage`, `CampaignBrief`, context snapshot assembly, SSE streaming per message, Redis session storage, session summarization on idle + Electron `will-quit` IPC | Chat sends and receives; tool call messages render (bold/italic/left-border/no-bg); activity tab shows `ActivityFeed`; session summary written to Postgres on session end via both paths |
| 4 | **AI tool integrations** — wire all 8 tools (7 from Section 5.3 + `save_career_plan`) to existing services; each tool call emits `tool_start` and `tool_result` SSE events; non-blocking dispatch confirmed | Each tool dispatches correctly; Celery tasks fire; `update_campaign` routes to `set_status` or `set_toggles` correctly; no blocking calls in FastAPI worker |
| 5 | **SummaryStrip + UnifiedDashboard data** — `GET /dashboard/summary` returns all 7 `CampaignSummary` fields aggregated across campaigns; `UnifiedDashboard` passes correct shape to existing `SummaryStrip` | Summary strip renders with all fields in both All Applications and Campaign View modes |
| 6 | **Creation chat + SSE endpoints** — `CreationChat`, two-step SSE (create-session → stream), file upload, market probe via Celery probe queue, career plan via DeepSeek Pro, atomic campaign+profile creation, `trigger_scrape`, redirect SSE event. Electron `will-quit` IPC handler added to `main.ts` | Full creation flow end-to-end: AI asks → file parsed → plan generated → campaign created atomically → scrape triggered → SSE redirect → shell opens in Campaign View with Activity tab live |
| 7 | **Job detail center takeover** — `JobDetailCenter` refactoring `ApplyPanel` + `TrackingPanel` into two-column center layout | Clicking job row opens detail in center; sidebar + AI chat unchanged; back arrow returns to correct previous mode |
| 8 | **Legacy campaign brief CTA** — detect `creation_method='form'`, render upgrade CTA, wire to `POST /chat/message` with pre-built prompt, `save_career_plan` tool updates `career_plan` + sets `creation_method='ai'` | Legacy campaign shows CTA; clicking it generates and saves a career plan; brief card re-renders with plan |
| 9 | **Remove old components** — delete `CampaignForm`, `CampaignProfileBuilder`, `CampaignList`, `CampaignDashboard` after confirming all functionality covered | No broken imports; all routes reachable through new components |

---

## 15. Success Definition

The revamp succeeds when:

1. A user can describe their job search goal in plain conversation and have a campaign created, profiled, and scraping within 5 minutes — without filling a single form
2. The AI can answer "what's happening with my Stripe application?" at any time during a session and the answer reflects live DB state
3. All applied jobs across all campaigns are visible in one list with correct status and campaign labels
4. The campaign sidebar collapses cleanly without disrupting the jobs list or AI chat
5. Tool calls in the AI chat are visually distinct (bold action, italic process, no background) and never confused with AI messages
6. Session context persists across tabs within a session and is summarized across sessions
7. The system handles 5,000 concurrent users with no degradation — Celery + Redis + stateless workers unchanged from existing architecture
8. Career plan is persisted and viewable in the Brief card for the lifetime of the campaign
