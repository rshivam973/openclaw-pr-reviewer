---
name: github-review-poster
description: Posts structured PR review findings as inline GitHub review comments using the gh CLI
version: 1.0.0
metadata:
  openclaw:
    requires:
      env: [GITHUB_TOKEN]
      bins: [gh]
    primaryEnv: GITHUB_TOKEN
    emoji: "📝"
user-invocable: false
disable-model-invocation: false
---

# GitHub Review Poster Skill

Posts review findings from the `pr-review` skill as inline GitHub PR review comments.

## When to Use

After the `pr-review` skill produces a structured JSON review, use this skill to post the findings to GitHub as an inline review with file-level comments.

## How to Post

Use the `gh` CLI to post a review comment:

```bash
gh pr review <PR_NUMBER> --repo <OWNER/REPO> --comment --body "<REVIEW_BODY>"
```

## Formatting the Review Body

Convert the JSON review output into a readable GitHub review comment:

```markdown
## AI Review Summary

<summary from review>

**Risk Level:** <risk_level>

### Findings

| Severity | File | Line | Category | Comment |
|----------|------|------|----------|---------|
| :red_circle: ERROR | path/file.py | 42 | security | Description... |
| :large_yellow_circle: WARNING | path/file.py | 15 | bug | Description... |
| :bulb: SUGGESTION | path/file.py | 8 | style | Description... |

### Checklist

- :white_check_mark: Has Tests
- :white_check_mark: No Secrets
- :x: PR Description Complete

### Positive Observations

- Good use of context managers
- Thorough input validation

---
_Reviewed by PR Review Bot (OpenClaw Agent)_
```

## Rules

- Always include the summary and risk level at the top
- Group findings by severity (errors first, then warnings, then suggestions)
- If there are no findings, post a brief "LGTM" message
- Do NOT post empty reviews — only post when you have actual review content
- Include the checklist results for quick scanning
- Keep the review concise — link to specific lines rather than quoting large blocks
