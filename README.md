# PR Review Bot

AI-powered code review bot that automatically reviews GitHub pull requests and posts inline comments with actionable findings. Notifies PR authors via Slack DM.

## Features

- **Automated code review** on every PR using Claude (Anthropic or OpenRouter)
- **Inline GitHub review comments** with severity, category, and actionable suggestions
- **8-dimension review**: correctness, security, performance, error handling, design, maintainability, testing, API contracts
- **Slack notifications** — DM to PR author + channel broadcast
- **Per-repo context** via `CONTEXT.md` for project-aware reviews
- **Large diff handling** — automatic chunking for PRs over 2000 lines
- **Debounced incremental reviews** on push events (30s debounce)
- **Configurable review rules** — skip patterns, checklists, severity thresholds
- **Smart Slack user resolution** — static mapping, email lookup, or workspace search
- **Optional: OpenClaw agent mode** for enhanced agentic reviews with session memory

## How It Works

```
GitHub Webhook (PR opened/pushed/reopened)
  │
  ▼
PR Review Bot (FastAPI)
  ├── Validates webhook signature (HMAC-SHA256)
  ├── Skips draft PRs, bot's own PRs
  ├── Fetches PR diff from GitHub API
  ├── Filters out non-reviewable files (lockfiles, dist/, etc.)
  ├── Sends diff to Claude for review (direct API or OpenClaw agent)
  ├── Posts inline review comments on GitHub PR
  └── Sends Slack notification to PR author + team channel
```

## Prerequisites

- Python 3.11+
- An **Anthropic API key** or **OpenRouter API key**
- A **GitHub Personal Access Token** (with `repo` scope)
- A **Slack Bot Token** (see [Slack Bot Setup](#slack-bot-setup))
- A publicly accessible server (for GitHub webhooks) or a tunnel like ngrok

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-org/pr-review-bot.git
cd pr-review-bot

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys (see Configuration Reference below)

# 5. Run the bot
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then [set up the GitHub webhook](#github-webhook-setup) to point at your server.

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes* | — | Anthropic API key for Claude |
| `OPENROUTER_API_KEY` | Yes* | — | OpenRouter API key (alternative to Anthropic) |
| `LLM_PROVIDER` | No | Auto-detected | `anthropic` or `openrouter` |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Claude model to use |
| `GITHUB_PAT` | Yes | — | GitHub Personal Access Token (`repo` scope) |
| `WEBHOOK_SECRET` | Yes | — | Secret for validating GitHub webhooks |
| `SLACK_BOT_TOKEN` | Yes | — | Slack Bot User OAuth Token |
| `SLACK_PR_REVIEWS_CHANNEL` | No | — | Channel for all review notifications |
| `SLACK_FALLBACK_CHANNEL` | No | — | Fallback channel for unresolved users |
| `BOT_GITHUB_USERNAME` | No | — | Bot's GitHub username (to skip self-reviews) |
| `OPENCLAW_ENABLED` | No | `false` | Enable OpenClaw agent mode |
| `OPENCLAW_BASE_URL` | No | `http://127.0.0.1:18789` | OpenClaw gateway URL |
| `OPENCLAW_WEBHOOK_TOKEN` | No | — | OpenClaw webhook auth token |

*At least one of `ANTHROPIC_API_KEY` or `OPENROUTER_API_KEY` is required.

### Review Rules (`review_rules/default.yml`)

```yaml
checklist:
  - has_tests
  - no_secrets
  - pr_description_complete
  - no_console_logs

severity_threshold: suggestion

skip_files:
  - "*.lock"
  - "*.min.js"
  - "*.min.css"
  - "dist/**"
  - "build/**"
  - "node_modules/**"
  - "*.pyc"
  - "__pycache__/**"

skip_options:
  draft_prs: true
```

Customize this file to match your team's review checklist and file patterns.

### User Mapping (`user_mapping.yml`)

Map GitHub usernames to Slack user IDs for reliable DM delivery:

```yaml
octocat: U0123456789
developer: U9876543210
```

The bot also auto-resolves users via email lookup and workspace search, but static mappings are fastest and most reliable.

### CONTEXT.md

Add a `CONTEXT.md` file to your repository root to give the bot project-specific context:

```markdown
# Project Context

## Tech Stack
- Python 3.11, FastAPI, PostgreSQL
- React 18, TypeScript

## Architecture
- Monorepo with `api/` and `web/` directories
- API follows REST conventions with JSON responses

## Conventions
- All database access via SQLAlchemy ORM
- Tests in `tests/` mirror the `app/` directory structure
```

The bot fetches this file automatically and includes it in the review prompt.

## GitHub Webhook Setup

1. Go to your repo (or org) → **Settings** → **Webhooks** → **Add webhook**
2. **Payload URL**: `https://your-server:8000/webhook/github`
3. **Content type**: `application/json`
4. **Secret**: Same value as `WEBHOOK_SECRET` in your `.env`
5. **Events**: Select **Pull requests** only
6. Click **Add webhook**

For org-wide webhooks, configure at the organization level to cover all repos.

## Slack Bot Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App**
2. Choose **From scratch**, name it (e.g., "PR Review Bot")
3. Go to **OAuth & Permissions** → Add these **Bot Token Scopes**:
   - `chat:write` — Send messages
   - `users:read` — Look up users
   - `users:read.email` — Look up users by email
4. **Install to Workspace** and copy the **Bot User OAuth Token**
5. Set `SLACK_BOT_TOKEN` in your `.env`
6. Invite the bot to your PR reviews channel: `/invite @PR Review Bot`

## Docker Deployment

### Build and Run

```bash
docker build -t pr-review-bot .
docker run -d \
  --name pr-review-bot \
  --env-file .env \
  -p 8000:8000 \
  --restart unless-stopped \
  pr-review-bot
```

### Docker Compose

```yaml
version: "3.8"
services:
  pr-review-bot:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    restart: unless-stopped
```

```bash
docker compose up -d
```

## OpenClaw Agent Mode (Optional)

For enhanced reviews with session memory and agentic capabilities, you can route reviews through an [OpenClaw](https://openclaw.ai) agent instead of direct API calls.

The bot falls back to direct API automatically if OpenClaw is unreachable.

See [`openclaw-agent/README.md`](openclaw-agent/README.md) for setup instructions.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns status, uptime, provider, model |
| `POST` | `/webhook/github` | GitHub webhook receiver |

## Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/ -v
```

## Project Structure

```
pr-review-bot/
├── app/
│   ├── main.py              # FastAPI app, webhook handler, review orchestration
│   ├── config.py            # Environment and file-based configuration
│   ├── review_engine.py     # Direct LLM review (Anthropic/OpenRouter)
│   ├── openclaw_client.py   # OpenClaw agent integration (optional)
│   ├── github_client.py     # GitHub API client
│   ├── slack_notifier.py    # Slack notifications and user resolution
│   ├── models.py            # Pydantic data models
│   └── diff_utils.py        # Diff parsing, filtering, chunking
├── openclaw-agent/          # Portable OpenClaw agent package
├── review_rules/            # Review configuration
│   └── default.yml
├── tests/                   # Unit tests
├── user_mapping.yml         # GitHub → Slack user mapping
├── Dockerfile
├── requirements.txt
└── requirements-dev.txt
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.
