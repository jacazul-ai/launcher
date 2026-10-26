# Security Review Directives

`security-expert` joins every code review as a `code-review` extension.
The core owns the scale (levels, advisories, areas, evidence); this file
supplies the security scenarios and the audit procedure. Report every
finding under area `SECURITY` on that scale.

## Depth

Resolve the depth before reading the diff, and state it with its
source:

1. **Request:** an explicit request for this review ("review this one
   in high") raises the depth for this review only.
2. **Project pin:** the `## Security Review` section of `AGENTS.md`.
3. **Default:** `medium`, stated as the default.

```markdown
## Security Review

- depth: medium
```

| Depth | Covers |
|---|---|
| `low` | The changed code only |
| `medium` | The changed code plus the affected context: callers, callees, trust boundaries and side effects it reaches |
| `high` | `medium` plus every surface of the same class in the repository; a workflow change reviews every workflow |

## Procedure

1. **Map the touched surfaces:** entry points, privileged actions,
   credentials, dependencies, workflows and tools the diff changes.
2. **Follow the affected context** to the resolved depth. A side effect
   outside the diff is in scope when the diff causes it.
3. **Walk the scenarios** below for the tracks the diff touches, and
   read the hub's primary reference for each surface.
4. **Add the language surface:** use the language skill in use for the
   diff's language; if none, infer the language from the files and use
   any installed skill for it; if none exists, use general knowledge and
   say that no language skill covered it.
5. **Report** each finding on the core scale, with the body the hub
   defines: Finding, Impact, Evidence, Fix, Validation.

## Blocking

A `BLOCKER` keeps the core's evidence rule: a reproduction, a clear
trace, or strong tool evidence that the boundary is crossed. A concern
that depends on an unverified fact is `HEURISTIC`, at most a `WARNING`
with `FIX-OR-TECH-DEBT`; name the fact that would settle it.

A secret or privileged-context risk the operator accepted while
developing is still reported here. The light checklist's acceptance
does not carry into review.

Validation reads source. Do not execute target-controlled code to prove
a finding; no sandbox exists yet.

## Foundations

### F1. Secret in source, fixture or config

- **Problem:** a token, key or password is committed, even in a test
  fixture or example config.
- **What can happen:** anyone with read access, or any fork, holds the
  credential; after a push it is compromised.
- **Safer shape:** load from the environment or a vault; rotate first if
  it was pushed, then clean history.

### F2. Input concatenated into an interpreter

- **Problem:** request, CLI or file data is formatted into SQL, a shell
  string, a template or a path.
- **What can happen:** injection, command execution, traversal.
- **Safer shape:** bound parameters, argument arrays, auto-escaping,
  canonicalized paths under an allowlisted root.

### F3. Weak randomness for a security value

- **Problem:** a non-cryptographic generator makes tokens, reset links
  or session IDs.
- **What can happen:** predictable values allow takeover.
- **Safer shape:** the platform's cryptographic random source.

## Boundaries

### B1. New or changed dependency

- **Problem:** a package is added or upgraded without checking its name,
  source and lifecycle scripts.
- **What can happen:** typosquatting, namespace confusion or an install
  hook runs attacker code on developer and CI machines.
- **Review questions:** is it needed? Official source? Pinned in the
  lockfile? Does it run scripts on install?
- **Safer shape:** a vetted, pinned, lockfile-bound dependency.

### B2. Untrusted data reaches a parser or fetch

- **Problem:** unsafe deserialization, unsafe YAML loading, or a
  user-controlled URL fetched server-side.
- **What can happen:** code execution, or SSRF into metadata services
  and internal APIs.
- **Safer shape:** safe parsers with schema validation; destination
  allowlists checked at connection time.

### B3. Cache or artifact crosses trust contexts

- **Problem:** a job that runs untrusted code writes a cache or artifact
  that a privileged job restores.
- **What can happen:** poisoned dependencies or binaries execute with
  release or deploy credentials.
- **Safer shape:** cache namespaces per trust context, no broad
  `restore-keys`, artifacts bound by digest.

## Systems

### S1. Untrusted code in a privileged workflow

- **Problem:** `pull_request_target`, `workflow_run` or a comment
  trigger checks out or runs contributor code with secrets or write
  tokens.
- **What can happen:** a fork PR exfiltrates secrets or publishes.
- **Safer shape:** never run untrusted code in the privileged context;
  split the work, keep `permissions` minimal, pin actions to a commit.

### S2. Missing authorization on a new entry point

- **Problem:** a route, handler, command or tool performs an action
  without checking the caller's access to that resource.
- **What can happen:** any authenticated, or anonymous, principal acts
  on another's data.
- **Safer shape:** deny by default; check principal and resource on
  every path, including batch, retry and legacy routes.

### S3. Agent or tool with borrowed authority

- **Problem:** a model-driven tool acts with a broad service credential
  and does not re-check the requester, or treats model output as
  trusted input.
- **What can happen:** content an attacker controls drives an action
  the requester could not perform.
- **Safer shape:** least authority per tool, handler-side validation,
  approval bound to the exact action and arguments.

### S4. Secret leaks through an output channel

- **Problem:** credentials reach logs, error messages, process
  arguments, URLs, client bundles or uploaded artifacts.
- **What can happen:** a lower-trust reader collects the credential.
- **Safer shape:** redact at the source, pass secrets through files or
  masked variables, keep artifacts free of credentials.
