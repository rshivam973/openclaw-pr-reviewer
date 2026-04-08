# OpenClaw Code Reviewer Agent

A portable OpenClaw agent that performs AI-powered code reviews on GitHub pull requests. Can be used standalone or as an enhancement to the [PR Review Bot](../README.md).

## What It Does

When triggered (via webhook or CLI), the agent:
1. Reads the PR diff and context
2. Analyzes the code across **8 quality dimensions**: correctness, security, performance, error handling, design, maintainability, testing, and API contracts
3. Produces structured JSON review findings with severity, category, and actionable comments
4. Optionally posts inline review comments directly to GitHub

## Prerequisites

- **Node.js 22+**
- **OpenClaw** (`npm install -g openclaw@latest`)
- **gh CLI** (GitHub CLI) — for posting reviews directly
- **Anthropic API key** — for the Claude model

## Quick Install

```bash
cd openclaw-agent
./install.sh
```

This will:
- Verify prerequisites
- Install/update OpenClaw
- Copy workspace and skill files to `~/.openclaw/workspace-code-reviewer/`
- Generate `openclaw.json` with a random webhook token
- Print configuration values for your `.env` file

### Install Options

```bash
# Provide your own webhook token
./install.sh --token YOUR_SECRET_TOKEN

# Custom workspace directory
./install.sh --workspace-dir /path/to/workspace

# Also set up systemd service (Linux)
./install.sh --systemd
```

## Manual Install

If you prefer to set things up manually:

### 1. Install OpenClaw

```bash
npm install -g openclaw@latest
```

### 2. Copy Workspace Files

```bash
mkdir -p ~/.openclaw/workspace-code-reviewer/skills
cp workspace/SOUL.md ~/.openclaw/workspace-code-reviewer/
cp workspace/AGENTS.md ~/.openclaw/workspace-code-reviewer/
cp workspace/TOOLS.md ~/.openclaw/workspace-code-reviewer/
cp -r workspace/skills/* ~/.openclaw/workspace-code-reviewer/skills/
```

### 3. Configure OpenClaw

Copy `openclaw.json` to `~/.openclaw/openclaw.json` and replace `YOUR_WEBHOOK_TOKEN_HERE` with a secure token:

```bash
TOKEN=$(openssl rand -hex 32)
sed "s|YOUR_WEBHOOK_TOKEN_HERE|$TOKEN|g" openclaw.json > ~/.openclaw/openclaw.json
echo "Your webhook token: $TOKEN"
```

### 4. Start the Gateway

```bash
openclaw gateway start
```

### 5. Test

```bash
curl -X POST http://127.0.0.1:18789/hooks/pr-review \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "test/repo",
    "pr_number": 1,
    "pr_title": "Test PR",
    "pr_description": "A test pull request",
    "pr_author": "developer",
    "action": "opened",
    "scope": "full",
    "diff": "--- a/hello.py\n+++ b/hello.py\n@@ -1 +1 @@\n-print(\"hello\")\n+print(\"world\")",
    "context_md": ""
  }'
```

## Integration with PR Review Bot

To use this agent with the PR Review Bot, add these to your bot's `.env`:

```env
OPENCLAW_ENABLED=true
OPENCLAW_BASE_URL=http://127.0.0.1:18789
OPENCLAW_WEBHOOK_TOKEN=<your-token>
```

The bot will route reviews through the OpenClaw agent instead of making direct API calls. If the agent is unreachable, the bot falls back to direct API calls automatically.

## Standalone Usage

You can also use the agent directly without the PR Review Bot:

```bash
# Chat with the agent
openclaw chat --agent code-reviewer

# Or trigger via webhook for automation
curl -X POST http://127.0.0.1:18789/hooks/pr-review ...
```

## Skills

The agent includes two skills:

| Skill | Description | User-Invocable |
|-------|-------------|----------------|
| `pr-review` | Core review logic — analyzes diffs across 8 quality dimensions | Yes |
| `github-review-poster` | Posts review findings as GitHub PR comments | No (auto-invoked) |

### Customizing Skills

To customize the review behavior, edit the skill files in your workspace:

```
~/.openclaw/workspace-code-reviewer/skills/
  pr-review/SKILL.md           # Review criteria and output format
  github-review-poster/SKILL.md # GitHub posting format
```

## Configuration Reference

### openclaw.json

| Field | Description |
|-------|-------------|
| `agents.list[0].id` | Agent identifier (`code-reviewer`) |
| `agents.list[0].workspace` | Path to workspace directory |
| `hooks.token` | Webhook authentication token |
| `hooks.mappings[0].timeoutSeconds` | Max time for a review (default: 180s) |
| `model` | Claude model to use |
| `sessions.pruning.maxTurns` | Max conversation turns before summarization |

### Environment Variables

The agent needs these environment variables set in your OpenClaw environment:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude |
| `GITHUB_TOKEN` | Optional | For posting reviews via gh CLI |

## Troubleshooting

**Gateway won't start:**
```bash
openclaw gateway status    # Check status
openclaw gateway logs      # View logs
```

**Agent not responding to webhooks:**
```bash
openclaw agents list --bindings    # Verify agent is registered
curl http://127.0.0.1:18789/health # Check gateway health
```

**Reviews timing out:**
Increase `timeoutSeconds` in `openclaw.json` hooks mapping (default: 180s).
