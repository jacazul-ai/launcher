# SAST Security Scanning

Catalog for Static Application Security Testing (SAST), secure code review, and framework-specific vulnerability patterns.

References:
- OWASP Top 10: https://owasp.org/Top10/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/
- Adapted in part from PocketCmds/Snyk SAST guidance (attribution in SKILL.md).

## Use When

- Reviewing source code for security vulnerabilities.
- Adding security checks to CI/CD.
- Investigating injection, XSS, command execution, path traversal, deserialization, weak crypto, or hardcoded secrets.
- Auditing framework configuration for Django, Flask, Express, Rails, Spring, Laravel, or similar stacks.
- Creating custom security rules for organization-specific patterns.

## Do Not Use When

- The user only needs runtime/pentest validation.
- Source code is unavailable.
- The environment forbids third-party scanning or code upload.
- The target requires invasive testing without approval.

## Tool Selection

Use available approved tooling. Examples:

- Multi-language: Semgrep, CodeQL, SonarQube
- Python: Bandit, Ruff rules, framework-specific review
- JavaScript/TypeScript: ESLint security plugins, no-secret rules
- Java: SpotBugs, PMD, CodeQL
- Ruby: Brakeman
- Go: gosec, govulncheck
- Rust: cargo clippy, cargo audit

Do not require Snyk specifically unless the project already uses it.

## Baseline Workflow

1. Identify languages, frameworks, and security-relevant surfaces.
2. Select scanner/rulesets appropriate to the codebase.
3. Exclude generated/vendor/test directories carefully; do not hide real runtime code.
4. Run scans with reproducible commands.
5. Triage findings by severity, confidence, reachability, and exposure.
6. Propose safe code-level fixes.
7. Add regression tests or validation steps where practical.
8. Document residual risk and false-positive rationale.

## Vulnerability Patterns

### SQL/Query Injection

Red flags:
- String concatenation or formatting in queries.
- User input passed directly into query builders.

Preferred fixes:
- Parameterized queries.
- ORM filters with bound parameters.
- Allowlisted query fields for dynamic sorting/filtering.

### Cross-Site Scripting (XSS)

Red flags:
- `innerHTML`, `outerHTML`, `document.write` with unsanitized input.
- Template escaping disabled.

Preferred fixes:
- Text rendering APIs for plain text.
- Framework auto-escaping.
- Sanitization such as DOMPurify only when HTML is required.
- CSP where appropriate.

### Hardcoded Secrets

Red flags:
- API keys, cloud keys, tokens, passwords, private keys in source or config.

Preferred fixes:
- Environment or vault-backed secret lookup.
- Rotation of exposed credentials.
- Secret scanning in CI and pre-commit where appropriate.

### Path Traversal

Red flags:
- File paths derived from request/user input.

Preferred fixes:
- Canonicalize paths.
- Enforce allowlisted base directories.
- Reject paths escaping the allowed root.

### Insecure Deserialization

Red flags:
- `pickle.loads`, unsafe YAML load, native object deserialization from untrusted input.

Preferred fixes:
- JSON or safe parsers.
- `yaml.safe_load` where YAML is required.
- Schema validation.

### Command Injection

Red flags:
- `shell=True`, `os.system`, shell string interpolation.

Preferred fixes:
- Argument arrays.
- Avoid shell invocation.
- Validate/allowlist user-controlled arguments.

### Insecure Randomness

Red flags:
- Non-cryptographic RNG for tokens, sessions, reset links, or secrets.

Preferred fixes:
- Cryptographic random APIs such as Python `secrets`.

## Framework Checks

### Django

Check for:
- `DEBUG=False` in production.
- Strong secret key loaded from a safe secret source.
- CSRF and security middleware enabled.
- Secure cookies and HTTPS settings.
- `X_FRAME_OPTIONS` and host validation.

### Flask

Check for:
- No `debug=True` in production.
- Strong secret key from safe config.
- CORS not wildcard unless truly public.
- Security headers via approved middleware where appropriate.

### Express.js

Check for:
- Security headers (e.g. Helmet or equivalent).
- CORS allowlists.
- Rate limiting for sensitive endpoints.
- Secure cookies and session config.

## CI/CD Integration Rules

When adding SAST to CI:

- Use minimal workflow permissions.
- Avoid uploading proprietary code to external services without approval.
- Keep report artifacts free of secrets.
- Prefer SARIF/security-tab upload where appropriate.
- Avoid blocking releases on noisy untuned rules without a rollout plan.
- Track baseline debt separately from new findings.

## Output Template

```text
Finding: User input reaches shell command construction.
Impact: An attacker may execute arbitrary commands in the application runtime.
Evidence: app/tasks.py builds a shell string with request parameter `name` and calls subprocess with shell=True.
Fix: Use subprocess argument arrays and validate `name` against an allowlist.
Validation: Add regression test with shell metacharacters and run SAST rule again.
Priority: Critical
```
