<div align="center">

# Developer Core

**Self-hosted AI for your entire career — interview prep, job hunting, and a real-time screen overlay. Runs 100% on your machine.**

[![GitHub stars](https://img.shields.io/github/stars/Siteforlio/dev-core?style=flat-square&color=3ECFEA&labelColor=07080F)](https://github.com/Siteforlio/dev-core/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-3EFFA0?style=flat-square&labelColor=07080F)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-9B7FFF?style=flat-square&labelColor=07080F)](CONTRIBUTING.md)
[![Platform](https://img.shields.io/badge/Platform-Windows%2011-F4A623?style=flat-square&labelColor=07080F)](https://github.com/Siteforlio/dev-core/releases/latest)

[**Download**](https://github.com/Siteforlio/dev-core/releases/latest) · [**Docs**](https://siteforlio.github.io/dev-core) · [**Contributing**](CONTRIBUTING.md) · [**Discussions**](https://github.com/Siteforlio/dev-core/discussions)

</div>

---

## What it does

Developer Core is an open-source desktop app that gives software engineers an unfair advantage at every stage of the job search — without sending your data anywhere.

| Module | What it does |
|---|---|
| 🎤 **Interview Prep** | AI mock interviewer with 10 career tracks, 5 seniority levels, 8 interview stages. Voice-first, pass/fail gates, scored debrief. |
| 🔍 **Job Hunter** | Scrapes jobs from 6 boards daily, auto-tailors your resume per listing, manages applications, integrates with your calendar and inbox. |
| ✦ **Screen Overlay** | A real-time AI layer invisible to screen capture and proctoring tools. Listens to live audio, surfaces suggestions in under a second. |

Everything runs locally. No usage data sent to servers. No subscription.

---

## Interview Prep

Practice against a realistic AI interviewer calibrated to your exact role and company type — not a generic Q&A bot.

<details>
<summary><strong>What's included</strong></summary>

<br>

**10 career tracks** — Backend, Frontend, Fullstack, Mobile, DevOps/Platform, Data Engineering, ML/AI Engineering, QA/SDET, Product Engineering, Security Engineering

**5 seniority levels** — Junior through Staff/Principal

**8 interview stages** with enforced time budgets and pass/fail gates:
- Phone Screen → Technical Screen → HR Interview → Hiring Manager
- Skills Assessment → Panel Interview → Case Presentation → Offer Negotiation

**Behavioral signal detection** — tracks hesitation timing, answer rewrite count, and response confidence to produce a hire/no-hire recommendation, not just a score average.

**Scored debrief** after every session — Communication, Time Management, Pressure Handling, Structure, Depth, plus track-specific dimensions (Code Reasoning, System Design Clarity, etc.)

**Universal simulation engine** — pitch practice, system design sessions, code review simulations, teaching exercises. Upload your resume, JD, or prep notes and the AI grounds its questions in your actual materials.

</details>

---

## Job Hunter

Describe the job you want in plain English. The AI sets up the campaign, configures the scraper, and runs the first batch — all in one conversation.

<details>
<summary><strong>What's included</strong></summary>

<br>

**Multi-board scraping** — LinkedIn, RemoteOK, We Work Remotely, Adzuna, Scrapfly-powered boards. Runs daily. Deduplicates across boards and campaigns.

**AI resume tailoring** — each scraped listing triggers automatic resume tailoring. Rewrites bullet points to mirror the JD language without fabricating experience. Generates a per-job PDF stored locally.

**Email & calendar integration** — connects to Google and Microsoft accounts via OAuth. Monitors your inbox for interview invitations, auto-creates calendar events from scheduling emails.

**Chrome extension auto-fill** — reads your campaign profile and fills application forms on Greenhouse, Lever, Workday, and most ATS platforms. One click per listing from the dashboard.

**BERT job scoring** — scores each listing against your profile before you see it. You only review the jobs that actually match.

</details>

---

## Screen Overlay

An AI layer invisible to screen capture, screen share, and proctoring software. It listens, thinks, and answers — while remaining completely hidden from recordings.

<details>
<summary><strong>How it works</strong></summary>

<br>

**Invisible by design** — uses `WDA_EXCLUDEFROMCAPTURE` (Win32 API) to exclude the overlay window from all screen capture APIs on Windows 11. Any recording or proctoring tool sees only your desktop behind it.

**Live audio transcription** — captures microphone and system audio (WASAPI loopback). Transcribes locally using Whisper — no audio leaves your machine. A BERT classifier pre-triggers the AI when a question is detected, before you finish listening.

**Sub-second suggestions** — audio → transcription → AI response in under 1 second. The overlay shows a thinking state within 30ms of your hotkey press.

**Session context & RAG** — upload your resume, JD, prep notes, or code files at session start. Every AI response pulls relevant chunks from what you uploaded.

**Live code execution** — run Python, Node, Go, Rust, and more directly in the overlay sidebar. The AI sees your output and iterates.

> **On use during interviews:** The overlay is a confidence aid for people who know their material but sometimes blank under pressure. It surfaces things you already know. Using it as a substitute for preparation doesn't work — experienced interviewers notice scripted-sounding answers.

</details>

---

## Keyboard Shortcuts

All overlay controls use a polled key state approach — no registered hotkeys, no `SetWindowsHookEx`, invisible to keyboard monitors and proctoring software.

| Shortcut | Action |
|---|---|
| <kbd>Ctrl</kbd> + <kbd>Space</kbd> | Show / hide overlay |
| <kbd>Ctrl</kbd> + <kbd>G</kbd> | Trigger AI suggestion (immediate thinking feedback) |
| <kbd>Ctrl</kbd> + <kbd>Enter</kbd> | Start session |
| <kbd>Ctrl</kbd> + <kbd>/</kbd> | Focus ask input |
| <kbd>Ctrl</kbd> + <kbd>S</kbd> | Capture screenshot and send to AI |
| <kbd>Ctrl</kbd> + <kbd>X</kbd> | Clear screenshot buffer |
| <kbd>Ctrl</kbd> + <kbd>I</kbd> | Toggle interact mode (enable/disable mouse input) |
| <kbd>Ctrl</kbd> + <kbd>R</kbd> | Re-trigger thinking state |
| <kbd>Ctrl</kbd> + <kbd>→</kbd> | Move overlay right |
| <kbd>Ctrl</kbd> + <kbd>←</kbd> | Move overlay left |
| <kbd>Ctrl</kbd> + <kbd>↓</kbd> | Move overlay down |
| <kbd>Ctrl</kbd> + <kbd>↑</kbd> | Move overlay up |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>↓</kbd> | Scroll suggestion card down |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>↑</kbd> | Scroll suggestion card up |

---

## Setup

### Option 1 — Download the installer (recommended)

```
1. Download the latest release from GitHub Releases
2. Run the installer — it bundles Python, local AI models, and the Electron shell
3. Launch Developer Core and follow the first-run setup wizard
```

[→ Download for Windows](https://github.com/Siteforlio/dev-core/releases/latest)

---

### Option 2 — Run from source

**Requirements:** Node 20+, Python 3.11+

```bash
git clone https://github.com/Siteforlio/dev-core.git
cd dev-core

# Frontend + Electron
npm install

# Backend
cd backend
python -m venv venv
source venv/Scripts/activate    # Windows
pip install -r requirements.txt
cd ..

# Copy and fill in env
cp backend/.env.example backend/.env
```

**Generate a JWT secret** (required — the app refuses to start without one):

```bash
python -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(32))"
```

**API keys needed:**

| Key | Where to get it | Free tier |
|---|---|---|
| `JWT_SECRET` | Generate locally (command above) | — |
| `DEEPSEEK_API_KEY` | [platform.deepseek.com](https://platform.deepseek.com/api_keys) | ✓ |
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com) | 200hrs/month |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com/keys) | ✓ |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/app/apikey) | ✓ |
| Google OAuth | [console.cloud.google.com](https://console.cloud.google.com) | ✓ |
| Microsoft OAuth | [portal.azure.com](https://portal.azure.com) | ✓ |
| `ADZUNA_APP_ID` + `ADZUNA_API_KEY` | [developer.adzuna.com](https://developer.adzuna.com) | ✓ |

**Start the app:**

```bash
npm run dev
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron 28+ |
| Frontend | React 18 + TypeScript + Tailwind CSS + Vite |
| Backend | FastAPI (Python 3.11+) |
| LLM | DeepSeek (primary), Gemini Flash |
| Transcription | Deepgram (cloud) + Whisper via Groq (local fallback) |
| Job scoring | BERT (runs locally, no API needed) |
| Audio capture | WASAPI loopback (Windows), PyAudioWPatch |
| Database | SQLite (app data), aiosqlite |
| Auth | JWT (python-jose) + refresh token rotation |
| Stealth overlay | Win32 `WDA_EXCLUDEFROMCAPTURE` via koffi |

---

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR — it covers branch naming, commit message format, code style rules, and test commands.

Every PR goes through the template checklist:
- Tests pass
- ARCHITECTURE.md layering rules followed
- `CHANGELOG.md` updated for user-facing changes
- `docs/index.html` updated if features or shortcuts changed

New to the codebase? Issues labelled [`good first issue`](https://github.com/Siteforlio/dev-core/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) are scoped to be achievable without deep system knowledge.

For large features — open a [Discussion](https://github.com/Siteforlio/dev-core/discussions) first.

---

## Community

- [GitHub Discussions](https://github.com/Siteforlio/dev-core/discussions) — Q&A, ideas, show & tell
- [Issues](https://github.com/Siteforlio/dev-core/issues) — bugs and feature requests

---

## License

MIT — see [LICENSE](LICENSE)
