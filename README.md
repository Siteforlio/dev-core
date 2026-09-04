<div align="center">

<img src=".github/banner.svg" width="100%" alt="Developer Core"/>

<br/>

[![GitHub stars](https://img.shields.io/github/stars/Siteforlio/dev-core?style=flat-square&color=3ECFEA&labelColor=07080F&logo=github&logoColor=3ECFEA)](https://github.com/Siteforlio/dev-core/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-3EFFA0?style=flat-square&labelColor=07080F)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-9B7FFF?style=flat-square&labelColor=07080F)](CONTRIBUTING.md)
[![Windows 11](https://img.shields.io/badge/Windows%2011-primary-F4A623?style=flat-square&labelColor=07080F)](https://github.com/Siteforlio/dev-core/releases/latest)

**[Download](https://github.com/Siteforlio/dev-core/releases/latest)  ·  [Docs](https://siteforlio.github.io/dev-core)  ·  [Contributing](CONTRIBUTING.md)  ·  [Discussions](https://github.com/Siteforlio/dev-core/discussions)**

</div>

<br/>

| | Module | What it does |
|---|---|---|
| 🎤 | **Interview Prep** | AI mock interviewer across 10 career tracks, 5 seniority levels, 8 interview stages. Voice-first. Pass/fail gates. Scored debrief. |
| 🔍 | **Job Hunter** | Scrapes jobs daily from 6 boards, tailors your resume per listing with AI, manages applications end-to-end, syncs with your inbox and calendar. |
| ✦ | **Screen Overlay** | Real-time AI layer invisible to screen capture and proctoring software. Listens to live audio, surfaces suggestions in under a second. Never leaves your machine. |

<br/>

---

<img src=".github/section-interview.svg" width="100%" alt="Interview Prep"/>

<details>
<summary><b>&nbsp;&nbsp;Expand — tracks, stages, scoring</b></summary>

<br/>

Practice against a realistic AI interviewer calibrated to your exact role and company type — not a generic Q&A bot.

**10 career tracks**

> Backend · Frontend · Fullstack · Mobile · DevOps/Platform · Data Engineering · ML/AI Engineering · QA/SDET · Product Engineering · Security Engineering

**5 seniority levels** — Junior through Staff/Principal, each with calibrated question depth and expected answer frameworks.

**8 interview stages** with enforced time budgets and pass/fail gates:

| Stage | What it simulates |
|---|---|
| Phone Screen | Recruiter call — motivation, role fit, logistics |
| Technical Screen | First engineer call — fundamentals, problem solving |
| HR Interview | Culture fit, compensation, team dynamics |
| Hiring Manager | Vision alignment, leadership signals |
| Skills Assessment | Live coding or take-home equivalent |
| Panel Interview | Multi-stakeholder pressure |
| Case Presentation | Architecture, product, or business case |
| Offer Negotiation | Compensation framing and anchoring |

**Behavioral signal detection** — tracks hesitation timing, answer rewrite count, and response confidence to produce a hire/no-hire recommendation — not just a score average.

**Scored debrief** after every session:

> Communication · Time Management · Pressure Handling · Structure · Depth · track-specific dimensions (Code Reasoning, System Design Clarity, etc.)

**Universal simulation engine** — pitch practice, system design sessions, code review simulations, teaching exercises. Upload your resume, JD, or prep notes and the AI grounds its questions in your actual materials.

<br/>

</details>

<br/>

---

<img src=".github/section-jobhunter.svg" width="100%" alt="Job Hunter"/>

<details>
<summary><b>&nbsp;&nbsp;Expand — scraping, tailoring, applications</b></summary>

<br/>

Describe the job you want in plain English. The AI configures the campaign, sets up the scraper, and runs the first batch — all in one conversation.

**Multi-board scraping** — LinkedIn, RemoteOK, We Work Remotely, Adzuna, Scrapfly-powered boards. Runs daily. Deduplicates across boards and campaigns automatically.

**AI resume tailoring** — each scraped listing triggers automatic resume tailoring. Rewrites bullet points to mirror the JD language and priorities without fabricating experience. Generates a per-job PDF stored locally.

**BERT job scoring** — every listing is scored against your profile before you see it. You only review matches that actually matter.

**Email & calendar integration** — connects to Google and Microsoft accounts via OAuth. Monitors your inbox for interview invitations and recruiter replies. Auto-creates calendar events from scheduling emails.

**Chrome extension auto-fill** — reads your campaign profile and fills application forms on Greenhouse, Lever, Workday, and most ATS platforms. One click per listing from the dashboard.

<br/>

</details>

<br/>

---

<img src=".github/section-overlay.svg" width="100%" alt="Screen Overlay"/>

<details>
<summary><b>&nbsp;&nbsp;Expand — stealth, audio, AI response pipeline</b></summary>

<br/>

An AI layer invisible to screen capture, screen share, and proctoring software. It listens, thinks, and answers — while remaining completely hidden from recordings.

**Invisible by design** — uses `WDA_EXCLUDEFROMCAPTURE` (Win32 API) to exclude the overlay window from all screen capture APIs on Windows 11. Any recording or proctoring tool sees only your desktop behind it.

**Live audio transcription** — captures microphone and system audio simultaneously via WASAPI loopback. Transcribes locally using Whisper — no audio leaves your machine. A BERT classifier pre-triggers the AI the moment a question is detected, before you finish listening.

**Sub-second response pipeline** — audio → transcription → AI response in under 1 second. The overlay shows a thinking state within 30ms of your hotkey press — before the backend even responds.

**Session context & RAG** — upload your resume, JD, prep notes, or code files at session start. Every response greedily pulls relevant chunks from what you uploaded.

**Live code execution** — run Python, Node, Go, Rust, and more directly from the overlay sidebar. The AI sees your output and iterates.

> **On use during interviews:** The overlay is a confidence aid — not a substitute for preparation. It surfaces things you already know when pressure makes you blank. Interviewers notice scripted-sounding answers.

<br/>

</details>

<br/>

---

<img src=".github/section-shortcuts.svg" width="100%" alt="Keyboard Shortcuts"/>

<br/>

| Shortcut | Action |
|---|---|
| <kbd>Ctrl</kbd> + <kbd>Space</kbd> | Show / hide overlay |
| <kbd>Ctrl</kbd> + <kbd>G</kbd> | Trigger AI suggestion |
| <kbd>Ctrl</kbd> + <kbd>Enter</kbd> | Start session |
| <kbd>Ctrl</kbd> + <kbd>/</kbd> | Focus ask input |
| <kbd>Ctrl</kbd> + <kbd>S</kbd> | Capture screenshot and send to AI |
| <kbd>Ctrl</kbd> + <kbd>X</kbd> | Clear screenshot buffer |
| <kbd>Ctrl</kbd> + <kbd>I</kbd> | Toggle interact mode |
| <kbd>Ctrl</kbd> + <kbd>R</kbd> | Re-trigger thinking state |
| <kbd>Ctrl</kbd> + <kbd>→</kbd> | Move overlay right |
| <kbd>Ctrl</kbd> + <kbd>←</kbd> | Move overlay left |
| <kbd>Ctrl</kbd> + <kbd>↓</kbd> | Move overlay down |
| <kbd>Ctrl</kbd> + <kbd>↑</kbd> | Move overlay up |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>↓</kbd> | Scroll suggestion card down |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>↑</kbd> | Scroll suggestion card up |

<br/>

---

## Setup

### Option 1 — Installer *(recommended)*

> No Python or Node installation required. The installer bundles the Python backend, local AI models, and Electron shell.

<div align="center">

[![Download](https://img.shields.io/badge/↓%20Download%20for%20Windows-3ECFEA?style=for-the-badge&labelColor=07080F&logo=windows&logoColor=3ECFEA)](https://github.com/Siteforlio/dev-core/releases/latest)

</div>

<br/>

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

# Environment
cp backend/.env.example backend/.env
```

Generate a strong JWT secret (the app refuses to start without one):

```bash
python -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(32))"
```

**API keys needed:**

| Key | Where | Free tier |
|---|---|---|
| `JWT_SECRET` | Generate locally (above) | — |
| `DEEPSEEK_API_KEY` | [platform.deepseek.com](https://platform.deepseek.com/api_keys) | ✓ |
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com) | 200 hrs/mo |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com/keys) | ✓ |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/app/apikey) | ✓ |
| Google OAuth | [console.cloud.google.com](https://console.cloud.google.com) | ✓ |
| Microsoft OAuth | [portal.azure.com](https://portal.azure.com) | ✓ |
| `ADZUNA_APP_ID` + key | [developer.adzuna.com](https://developer.adzuna.com) | ✓ |

```bash
npm run dev
```

<br/>

---

## Tech Stack

<img src=".github/tech-stack.svg" width="100%" alt="Tech Stack"/>

<br/>

---

<img src=".github/section-contrib.svg" width="100%" alt="Contributing"/>

<br/>

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR — covers branch naming, commit format, code style, and test commands.

Every PR auto-loads a checklist: tests pass · type check passes · ARCHITECTURE.md layering respected · CHANGELOG and docs updated.

[![Good First Issues](https://img.shields.io/github/issues/Siteforlio/dev-core/good%20first%20issue?style=flat-square&color=3EFFA0&labelColor=07080F&label=good%20first%20issue)](https://github.com/Siteforlio/dev-core/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![GitHub Discussions](https://img.shields.io/github/discussions/Siteforlio/dev-core?style=flat-square&color=9B7FFF&labelColor=07080F&logo=github&logoColor=9B7FFF)](https://github.com/Siteforlio/dev-core/discussions)

For large features — open a [Discussion](https://github.com/Siteforlio/dev-core/discussions) before opening a PR.

<br/>

---

<div align="center">

MIT License &nbsp;·&nbsp; [Siteforlio/dev-core](https://github.com/Siteforlio/dev-core)

</div>
