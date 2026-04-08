import asyncio
import hashlib
import hmac
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException

from app.config import get_config
from app.diff_utils import parse_diff_files, filter_skip_files, split_large_diff, reassemble_diff
from app.github_client import GitHubClient
from app.openclaw_client import OpenClawClient
from app.review_engine import ReviewEngine, build_system_prompt, build_user_prompt
from app.slack_notifier import SlackNotifier, format_slack_message

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

_debounce: dict[str, float] = {}
DEBOUNCE_SECONDS = 30
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    logger.info("PR Review Bot starting (provider=%s, model=%s)", cfg.llm_provider, cfg.claude_model)
    yield
    logger.info("PR Review Bot shutting down")


app = FastAPI(title="PR Review Bot", lifespan=lifespan)


def verify_signature(secret: str, payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.get("/health")
async def health():
    cfg = get_config()
    return {"status": "ok", "uptime_seconds": int(time.time() - _start_time), "provider": cfg.llm_provider, "model": cfg.claude_model}


@app.post("/webhook/github")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    cfg = get_config()
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(cfg.webhook_secret, body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    if event != "pull_request":
        return {"action": "ignored", "reason": f"event={event}"}

    payload = await request.json()
    action = payload.get("action", "")
    if action not in ("opened", "synchronize", "reopened"):
        return {"action": "ignored", "reason": f"action={action}"}

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})

    skip_drafts = cfg.review_rules.get("skip_options", {}).get("draft_prs", True)
    if skip_drafts and pr.get("draft", False):
        return {"action": "ignored", "reason": "draft PR"}

    pr_author = pr.get("user", {}).get("login", "")
    if cfg.bot_github_username and pr_author == cfg.bot_github_username:
        return {"action": "ignored", "reason": "bot's own PR"}

    pr_key = f"{repo.get('full_name')}#{payload.get('number')}"
    if action == "synchronize":
        _debounce[pr_key] = time.time()
        background_tasks.add_task(_debounced_review, pr_key=pr_key, payload=payload, action=action)
    else:
        background_tasks.add_task(process_review, payload=payload, action=action)

    return {"action": "processing", "pr": pr_key}


async def _debounced_review(pr_key: str, payload: dict, action: str):
    scheduled_at = _debounce.get(pr_key, 0)
    await asyncio.sleep(DEBOUNCE_SECONDS)
    if _debounce.get(pr_key, 0) != scheduled_at:
        logger.info("Debounced: skipping stale synchronize event for %s", pr_key)
        return
    await process_review(payload=payload, action=action)


async def process_review(payload: dict, action: str):
    cfg = get_config()
    pr = payload["pull_request"]
    repo = payload["repository"]
    owner = repo["owner"]["login"]
    repo_name = repo["name"]
    full_name = repo["full_name"]
    pr_number = payload["number"]
    pr_title = pr["title"]
    pr_description = pr.get("body", "") or ""
    pr_author = pr["user"]["login"]
    head_sha = pr["head"]["sha"]
    head_ref = pr["head"]["ref"]
    pr_url = pr["html_url"]
    is_incremental = action == "synchronize"

    github = GitHubClient(pat=cfg.github_pat)
    slack = SlackNotifier(token=cfg.slack_bot_token, fallback_channel=cfg.slack_fallback_channel, user_mapping=cfg.user_mapping, pr_reviews_channel=cfg.slack_pr_reviews_channel)

    # Review modes:
    #   Default:  Direct API (Anthropic or OpenRouter) — no external dependencies beyond API key
    #   Optional: OpenClaw agent mode — enhanced agentic review with session memory
    #             Set OPENCLAW_ENABLED=true in .env to activate. Falls back to direct API on failure.
    openclaw = None
    engine = None
    if cfg.openclaw_enabled and cfg.openclaw_webhook_token:
        openclaw = OpenClawClient(base_url=cfg.openclaw_base_url, token=cfg.openclaw_webhook_token)
        logger.info("Using OpenClaw agent mode (optional) for review of %s#%d", full_name, pr_number)
    else:
        api_key = cfg.anthropic_api_key if cfg.llm_provider == "anthropic" else cfg.openrouter_api_key
        engine = ReviewEngine(provider=cfg.llm_provider, api_key=api_key, model=cfg.claude_model)
        logger.info("Using direct API mode (default) via %s for review of %s#%d", cfg.llm_provider, full_name, pr_number)

    try:
        if is_incremental:
            before_sha = payload.get("before", "")
            raw_diff = await github.fetch_compare_diff(owner, repo_name, before_sha, head_sha)
        else:
            raw_diff = await github.fetch_pr_diff(owner, repo_name, pr_number)

        skip_patterns = cfg.review_rules.get("skip_files", [])
        diff_files = parse_diff_files(raw_diff)
        diff_files = filter_skip_files(diff_files, skip_patterns)

        if not diff_files:
            logger.info("No reviewable files in %s#%d after filtering", full_name, pr_number)
            return

        context_md = await github.fetch_context_md(owner, repo_name, head_ref)

        all_findings = []
        final_summary = ""
        final_risk = "low"
        final_checklist = {}

        if openclaw:
            # --- OpenClaw path: send full filtered diff to the agent ---
            from app.diff_utils import reassemble_diff
            filtered_diff = reassemble_diff(diff_files)

            try:
                result = await openclaw.trigger_review(
                    repo=full_name,
                    pr_number=pr_number,
                    pr_title=pr_title,
                    pr_description=pr_description,
                    pr_author=pr_author,
                    action=action,
                    diff=filtered_diff,
                    context_md=context_md,
                    is_incremental=is_incremental,
                )
            except Exception as e:
                logger.warning("OpenClaw review failed for %s#%d: %s. Falling back to direct API.", full_name, pr_number, e)
                # Fallback to direct API if OpenClaw fails
                api_key = cfg.anthropic_api_key if cfg.llm_provider == "anthropic" else cfg.openrouter_api_key
                engine = ReviewEngine(provider=cfg.llm_provider, api_key=api_key, model=cfg.claude_model)
                openclaw = None  # Signal to use engine path below

            if openclaw:
                # OpenClaw succeeded
                all_findings = result.findings
                final_summary = result.summary
                final_risk = result.risk_level.value
                final_checklist = result.checklist

        if engine:
            # --- Direct API path (original behavior or OpenClaw fallback) ---
            system_prompt = build_system_prompt(cfg.review_rules)
            chunks = split_large_diff(diff_files, max_lines=2000)

            for chunk in chunks:
                chunk_diff = reassemble_diff(chunk)
                user_prompt = build_user_prompt(pr_title=pr_title, pr_description=pr_description, diff=chunk_diff, context_md=context_md, is_incremental=is_incremental)

                try:
                    result = await engine.review(system_prompt, user_prompt)
                except Exception as e:
                    logger.warning("First review attempt failed for %s#%d: %s. Retrying...", full_name, pr_number, e)
                    await asyncio.sleep(10)
                    try:
                        result = await engine.review(system_prompt, user_prompt)
                    except Exception as e2:
                        logger.error("Second review attempt failed for %s#%d: %s", full_name, pr_number, e2)
                        await github.post_comment(owner, repo_name, pr_number, ":robot_face: Review bot encountered an error — skipping automated review.")
                        return

                all_findings.extend(result.findings)
                final_summary = result.summary
                final_risk = max(final_risk, result.risk_level.value, key=lambda x: ["low", "medium", "high"].index(x))
                final_checklist.update(result.checklist)

            if len(chunks) > 1:
                final_summary = f"Reviewed {len(diff_files)} files across {len(chunks)} chunks. Found {len(all_findings)} issue(s)."

        # --- Post review to GitHub ---
        review_failed = False
        comments = [{"path": f.file, "line": f.line, "side": "RIGHT", "body": f"**{f.severity.value.upper()}** ({f.category.value}): {f.comment}"} for f in all_findings]

        checklist_parts = []
        for key, val in final_checklist.items():
            icon = ":white_check_mark:" if val else ":x:"
            checklist_parts.append(f"{icon} {key.replace('_', ' ').title()}")

        review_source = "OpenClaw Agent" if cfg.openclaw_enabled and not engine else f"Direct API ({cfg.llm_provider.title()})"
        review_body = f"## AI Review Summary\n\n{final_summary}\n\n**Risk Level:** {final_risk}\n\n**Checklist:** {' | '.join(checklist_parts)}\n\n---\n_Reviewed by {review_source}_"

        try:
            await github.post_review(owner=owner, repo=repo_name, pr_number=pr_number, commit_sha=head_sha, body=review_body, comments=comments)
        except Exception as e:
            logger.error("Failed to post GitHub review for %s#%d: %s", full_name, pr_number, e)
            review_failed = True

        # --- Slack notification ---
        pr_info = await github.fetch_pr_info(owner, repo_name, pr_number)
        author_email = pr_info.get("user", {}).get("email")

        # Resolve Slack user ID for @mention in channel message
        slack_user_id = await slack.lookup_user(pr_author, author_email)

        from app.models import ReviewResult as RR, RiskLevel as RL
        aggregated_result = RR(summary=final_summary, risk_level=RL(final_risk), findings=all_findings, checklist=final_checklist)

        slack_message = format_slack_message(repo=full_name, pr_number=pr_number, pr_title=pr_title, pr_url=pr_url, result=aggregated_result, review_failed=review_failed, slack_user_id=slack_user_id)
        try:
            await slack.send_review_notification(github_username=pr_author, github_email=author_email, message=slack_message)
        except Exception as e:
            logger.error("Failed to send Slack notification for %s#%d: %s", full_name, pr_number, e)

    except Exception as e:
        logger.exception("Unexpected error reviewing %s#%d: %s", full_name, pr_number, e)
    finally:
        await github.close()
        if openclaw:
            await openclaw.close()
        if engine:
            await engine.close()
