# Developer Core

> Stop practicing interviews alone. Stop applying to jobs manually.

Developer Core is an open-source AI desktop app that runs entirely on your machine. It gives you a realistic AI interview simulator with live feedback, and an automated job hunter that finds, tailors, and applies to jobs for you.

[![GitHub stars](https://img.shields.io/github/stars/Statosco/developer-core?style=social)](https://github.com/Statosco/developer-core)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## Features

**Interview Prep**
- AI interviewer with configurable persona (startup CTO, big tech senior engineer, etc.)
- Structured multi-round interviews: behavioral, technical, coding
- Real-time feedback on your answers
- Post-session debrief with scoring and improvement suggestions
- Code editor round with execution sandbox

**Job Hunter**
- Scrapes 100+ jobs/day from LinkedIn, ATS portals, startup job boards
- AI resume tailoring per job description
- Automated applications with campaign management
- Cross-campaign duplicate detection

**AI Screen Overlay** *(inspired by [Cluely](https://cluely.com))*
- Real-time AI overlay that listens to your screen and microphone during live interviews
- Surfaces relevant talking points, technical definitions, and context on the fly
- Runs locally — nothing leaves your machine

> **On cheating:** We don't condone it, and frankly it doesn't work. Interviewers notice when answers sound scripted, and a role you got by cheating puts you in a job you can't do. This feature exists for people who genuinely know their stuff but sometimes blank under pressure — it's a confidence aid, not a shortcut. Use it to remind yourself of things you already know.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Required — runs all backend services |
| [DeepSeek API key](https://platform.deepseek.com/api_keys) | Free tier available — main LLM |
| [Deepgram API key](https://console.deepgram.com) | Free tier: 200hrs/month — speech transcription |
| [ngrok](https://ngrok.com/) | Required for Job Hunter OAuth callbacks — run separately (see below) |

### ngrok setup (Job Hunter only)

The Job Hunter needs a public URL so LinkedIn and ATS portals can redirect back after OAuth. Run ngrok in a separate terminal before starting the Job Hunter:

```bash
ngrok http 8000
```

Then paste the `https://...ngrok-free.app` URL into `.env` as `NGROK_PUBLIC_URL`.

> **Note:** Free ngrok assigns a random URL on every restart, which breaks OAuth callbacks after a restart. For stable use: upgrade to ngrok's paid static domain tier, or use [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (free alternative).

---

## Quickstart

```bash
# 1. Clone the repo
git clone https://github.com/Statosco/developer-core.git
cd developer-core

# 2. Copy the environment template
cp .env.example .env

# 3. Fill in your API keys (open .env in your editor)
#    Required: DEEPSEEK_API_KEY, DEEPGRAM_API_KEY, JWT_SECRET, JOB_HUNTER_ENCRYPTION_KEY
#    Job Hunter also needs: NGROK_AUTHTOKEN (run ngrok separately — see Prerequisites)

# 4. Start all services
docker compose up --build

# 5. Open the app
#    The Electron app will open automatically once services are ready
#    (~90 seconds on first run while Docker pulls images)
```

---

## Supported Platforms

| Platform | Status |
|---|---|
| Windows 11 | Pending verification |
| macOS (Apple Silicon) | Pending verification |
| Ubuntu 22.04 | Pending verification |

*Platform status updated after fresh-clone testing. See [Issues](https://github.com/Statosco/developer-core/issues) for known platform-specific problems.*

---

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron |
| Frontend | React + TypeScript + Tailwind CSS |
| Backend | FastAPI (Python 3.11+) |
| LLM | DeepSeek (default) / Claude (optional) |
| Transcription | Deepgram |
| Database | PostgreSQL + Neo4j + Redis |
| Task queue | Celery |
| Containerization | Docker Compose |

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

Not sure where to start? Look for issues labelled [`good first issue`](https://github.com/Statosco/developer-core/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

---

## Community

- [GitHub Discussions](https://github.com/Statosco/developer-core/discussions) — Q&A, feature ideas, show & tell
- [Discord](https://discord.gg/placeholder) <!-- TODO: replace with real invite --> — real-time help and chat

---

## License

MIT — see [LICENSE](LICENSE)
