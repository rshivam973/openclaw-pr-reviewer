# Code Reviewer — Tool Configuration

## Allowed Tools

You have access to these tools for performing code reviews:

### read
Read files from the workspace. Use this to examine source files referenced in the diff for additional context (e.g., understanding the full class/function when only part is in the diff).

### exec
Execute shell commands. Permitted uses:
- `git log` — check recent commit history for context
- `git show` — inspect specific commits
- `git diff` — compare branches or commits
- `gh pr diff` — fetch PR diff from GitHub
- `gh pr review` — post review comments to GitHub
- `curl` — fetch PR metadata or CONTEXT.md from GitHub API
- `jq` — parse JSON responses

### write
Write files to the workspace. Used for:
- Saving review results to `reviews/` directory
- Writing structured review output as JSON

## Denied Tools

The following tools are NOT available to this agent:
- `browser` — No web browsing needed for code review
- `canvas` — No visual output needed
- `apply_patch` — This agent reads code, it does not modify it
- `edit` — Same as above, read-only agent
- `process` — No long-running processes
- `gateway` — No messaging channel access

## Usage Guidelines

- Always respond with structured JSON output as defined in AGENTS.md
- Do not attempt to modify any repository code
- Focus exclusively on analyzing the diff and producing actionable findings
