# SAST and Secure Code Review

Static review of source for vulnerability patterns. A pattern is a
starting point: confirm that attacker-controlled input reaches the sink
before calling it a finding.

References:
- OWASP Top 10: https://owasp.org/Top10/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/
- CWE Top 25: https://cwe.mitre.org/top25/

## Workflow

1. Identify languages, frameworks and security-relevant surfaces.
2. Use the scanners the project already configures; the tools catalog
   names options when none is set.
3. Exclude generated, vendored and test directories with care; never
   hide runtime code.
4. Triage by reachability, exposure and confidence.
5. Propose the code-level fix and a regression test.
6. Record false-positive rationale and residual risk.

## Vulnerability Patterns

### SQL and Query Injection

- **Red flags:** string formatting or concatenation in queries; input
  passed straight into query builders.
- **Fix:** bound parameters; ORM filters; allowlisted fields for dynamic
  sorting and filtering.

### Cross-Site Scripting

- **Red flags:** `innerHTML`, `outerHTML`, `document.write` with
  untrusted data; template auto-escaping turned off.
- **Fix:** text APIs for text; framework escaping; a sanitizer only when
  HTML is required; a content security policy.

### Command Injection

- **Red flags:** `shell=True`, `os.system`, shell strings built from
  input.
- **Fix:** argument arrays without a shell; allowlisted arguments.

### Path Traversal

- **Red flags:** file paths built from request or user input; archive
  extraction without checking entry names.
- **Fix:** canonicalize, then require the result inside an allowlisted
  root; reject `..` and absolute entries.

### Insecure Deserialization

- **Red flags:** `pickle.loads`, unsafe YAML loading, native object
  deserialization of untrusted data.
- **Fix:** JSON or safe loaders with schema validation.

### Server-Side Request Forgery

- **Red flags:** the server fetches a URL or host the caller controls.
- **Fix:** allowlist destinations; check the resolved address at
  connection time, after redirects, and block metadata and internal
  ranges.

### Hardcoded Secrets

- **Red flags:** keys, tokens, passwords or private keys in source or
  config.
- **Fix:** environment or vault lookup; rotate anything exposed.

### Insecure Randomness

- **Red flags:** a non-cryptographic generator for tokens, sessions or
  reset links.
- **Fix:** the platform's cryptographic random source.

## Framework Checks

| Framework | Check |
|---|---|
| Django | `DEBUG` off in production; secret key from a secret store; CSRF and security middleware on; secure cookies; host validation |
| Flask | No `debug=True` in production; secret key from config; CORS not wildcard unless public |
| Express | Security headers; CORS allowlist; rate limits on sensitive routes; secure session cookies |

## Adding SAST to CI

- Minimal workflow permissions.
- No upload of proprietary code to an outside service without approval.
- Reports free of secrets.
- Track baseline debt apart from new findings; do not block on untuned
  noisy rules without a rollout plan.
