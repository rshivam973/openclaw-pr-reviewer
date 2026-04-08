# Contributing

Thanks for your interest in contributing to PR Review Bot!

## Development Setup

```bash
# Clone the repo
git clone https://github.com/your-org/pr-review-bot.git
cd pr-review-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install all dependencies (runtime + dev)
pip install -r requirements-dev.txt

# Copy environment config
cp .env.example .env
# Fill in at least ANTHROPIC_API_KEY, GITHUB_PAT, WEBHOOK_SECRET, SLACK_BOT_TOKEN
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## Code Style

- Follow existing patterns in the codebase
- Use type hints for function signatures
- Use `async/await` for all I/O operations
- Keep functions focused and single-purpose

## Pull Request Guidelines

1. Create a branch from `main`
2. Make your changes with clear, descriptive commits
3. Ensure all tests pass
4. Update documentation if you've changed behavior
5. Open a PR with a clear description of what and why

## Adding Review Dimensions

To add a new review dimension or modify the review prompt:
- For direct API mode: edit `app/review_engine.py` (`build_system_prompt`)
- For OpenClaw agent mode: edit `openclaw-agent/workspace/skills/pr-review/SKILL.md`

## Reporting Issues

Open an issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Relevant logs (with secrets redacted)
