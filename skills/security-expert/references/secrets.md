# Secrets

A secret is anything that grants access when read: tokens, API keys,
passwords, private and signing keys, session cookies, vault files and
the credentials inside connection strings. A public identifier called
a key is not a secret; check the type before reporting.

## Where Secrets Leak

| Channel | Example |
|---|---|
| Source and history | Committed `.env`, example config with a real value, a test fixture |
| Logs and errors | Request dumps, stack traces, debug prints of headers |
| Process surface | Command-line arguments, inherited environments of child processes |
| URLs | Tokens in query strings, which land in proxy and server logs |
| CI | Echoed variables, caches, uploaded artifacts, job summaries |
| Builds | Images and packages built from a broad context |
| Clients | Values bundled into browser or mobile code |
| Agents | Credentials placed in model context or passed to tools |

## Storage and Passing

- Keep secrets in a vault or the platform's secret store; load them at
  runtime.
- Prefer short-lived credentials from OIDC or workload identity over
  long-lived stored keys.
- Pass secrets through files or masked variables, not command-line
  arguments.
- Scope each credential to one purpose, one environment and the least
  permission it needs.
- Never cache, log or upload a file that can contain a credential.

Repository mandates come first: when the project routes credentials
through a broker or vault, use it and never read the raw token.

## When a Secret Is Exposed

1. **Rotate first.** A secret that reached a pushed commit, a public
   log or an artifact is compromised; cleaning history does not undo
   that.
2. **Assess use:** check the provider's access logs for the window it
   was exposed.
3. **Clean up:** remove it from history only with the operator's
   approval; every clone must re-fetch. History rewriting is a Git
   operation; the Git skill in use owns the procedure.
4. **Prevent recurrence:** add secret detection to pre-commit and CI.

## Detection

Run a secret scanner over the working tree and history when the project
configures one; the tools catalog names options. A match is a lead:
confirm the value is live and grants access before calling it exposed.
