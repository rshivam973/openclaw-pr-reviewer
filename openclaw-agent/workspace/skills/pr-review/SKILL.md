---
name: pr-review
description: Analyzes pull request diffs across 8 quality dimensions (correctness, security, performance, error handling, design, maintainability, testing, API contracts) and produces structured JSON review findings
version: 1.0.0
metadata:
  openclaw:
    requires:
      env: [ANTHROPIC_API_KEY]
      bins: [gh]
    primaryEnv: ANTHROPIC_API_KEY
    emoji: "🔍"
user-invocable: true
---

# PR Review Skill

Perform a thorough code review of a pull request diff following this structured process.

## Step 1: Understand the Change

Before analyzing code, read the PR title, description, and any project context. Determine:
- What is the author trying to accomplish?
- Is this a feature, bugfix, refactor, or chore?
- What's the risk level based on what's being changed? (auth, payments, data migrations = high risk; docs, tests, config = low risk)

## Step 2: Analyze Through 8 Dimensions

Review the diff through each lens, in priority order:

### 1. Correctness & Logic
- Does the code do what the PR claims?
- Off-by-one errors, null/undefined access, unhandled edge cases
- Race conditions in concurrent code
- Return values and error states handled at every call site
- Algorithm correctness for boundary values (empty, zero, negative, max)

### 2. Security (OWASP Top 10 + CWE)
- SQL/command/template injection, XSS, path traversal
- Missing auth checks, privilege escalation, insecure token handling
- Secrets in code or logs, PII leakage, verbose production errors
- Untrusted input reaching sensitive operations without sanitization
- Weak cryptography, hardcoded keys, bad RNG

### 3. Performance
- N+1 database queries, missing indexes
- Unbounded data loading (no pagination, full table scans into memory)
- Inefficient algorithms at the project's actual scale
- Missing caching for expensive repeated computations
- Blocking operations in async contexts
- Memory leaks (unclosed resources, growing collections)

### 4. Error Handling & Resilience
- Errors caught at appropriate levels (not too broad, not too granular)
- Helpful error messages for debugging
- Cleanup in failure paths (finally, context managers, defer)
- Timeouts and retry logic for external calls
- Errors logged with sufficient context

### 5. Design & Architecture
- Follows existing codebase patterns or deviates with good reason
- Single Responsibility Principle
- Abstractions at the right level — not leaky, not over-engineered
- Clean interfaces that are hard to misuse
- Change is in the right architectural layer

### 6. Maintainability & Readability
- Descriptive, consistent naming
- Complex logic has comments explaining WHY (not WHAT)
- Magic numbers/strings extracted to named constants
- Would a new team member understand this in 6 months?

### 7. Testing
- Tests exist for new/changed behavior
- Happy path, error path, and edge cases covered
- Tests are isolated and deterministic
- Test names clearly describe what they verify
- Coverage proportional to risk

### 8. API & Contract
- Public interfaces backward-compatible (or break is intentional + documented)
- API responses consistent with existing patterns
- New endpoints documented
- Request/response schemas validate properly

## Step 3: Produce the Output

Respond with ONLY valid JSON in this format:

```json
{
  "summary": "Brief overall assessment (1-3 sentences)",
  "risk_level": "low | medium | high",
  "findings": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "severity": "error | warning | suggestion",
      "category": "security | bug | style | performance",
      "comment": "Clear, actionable description with the WHY and a suggested fix"
    }
  ],
  "checklist": {
    "has_tests": true,
    "no_secrets": true,
    "pr_description_complete": true,
    "no_console_logs": true
  },
  "positive_observations": [
    "Good use of context managers for resource cleanup",
    "Thorough input validation on the API boundary"
  ]
}
```

## Calibration Rules

- **0 critical issues, minor suggestions only** → risk_level: "low"
- **1-2 warnings, no errors** → risk_level: "low" or "medium" depending on blast radius
- **Any security or data-loss issue** → risk_level: "high" regardless of count
- **Incremental reviews** (action=synchronize): Only review the new changes, not the full PR

## Language-Specific Awareness

Adapt your review to the detected stack:
- **Python**: Type hints, context managers, async/await, PEP 8
- **JavaScript/TypeScript**: Strict mode, type safety, promise handling, prototype pollution
- **Go**: Error propagation, goroutine leaks, defer ordering
- **Rust**: Ownership/borrowing, unsafe blocks, Result/Option
- **SQL**: Injection, indexes, transactions, migration safety
- **Terraform/Docker/K8s**: Security groups, least privilege, resource limits, secrets

## What NOT to Review

- Generated files (lockfiles, compiled output, vendor directories)
- Files matching skip patterns: `*.lock`, `*.min.js`, `*.min.css`, `dist/**`, `build/**`, `node_modules/**`, `*.pyc`, `__pycache__/**`
- Don't manufacture feedback to fill a template — if the code is clean, say so briefly
