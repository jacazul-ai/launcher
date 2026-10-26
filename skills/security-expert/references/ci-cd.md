# CI/CD

CI configuration is authorization code: it decides whose code runs,
with which secrets, and what it may publish. Review each workflow by
asking which event started it, whose code it executes, and what
authority that code holds. Examples use GitHub Actions; the questions
apply to any CI.

Reference: https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions

## Triggers and Trust

| Trigger | Runs whose code | Holds |
|---|---|---|
| `pull_request` from a fork | The contributor's | Read token, no secrets |
| `pull_request_target` | The base branch's, unless it checks out the PR | Base context: secrets and a write-capable token |
| `workflow_run` | The base branch's, fed by artifacts of the triggering run | Base context |
| `issue_comment`, `issues` | The base branch's, with attacker-written text in the event | Base context |
| `push`, `release`, `workflow_dispatch` | Trusted branch or maintainer | Full configured authority |

The dangerous combination is a privileged trigger that checks out,
builds, tests or installs contributor code, or that consumes an
artifact the contributor's run produced.

```yaml
# Avoid: privileged context running the PR head
on: pull_request_target
steps:
  - uses: actions/checkout@v4
    with:
      ref: ${{ github.event.pull_request.head.sha }}
  - run: npm install && npm test
```

Safer: run untrusted code under `pull_request`; when a privileged step
is needed, split it into a separate job that never executes the PR's
code and treats its artifacts as data.

## Expression Injection

Branch names, PR titles, issue bodies, commit messages and artifact
names are attacker-written. Interpolating them with `${{ }}` straight
into `run:` makes them shell code. Pass them through `env:` and quote
the variable instead.

## Permissions

- Set `permissions: contents: read` at the workflow level and grant
  more per job, only where used.
- Use `persist-credentials: false` on checkout unless a later step
  pushes.
- Prefer OIDC federation to cloud providers over stored long-lived
  keys, and scope the trust policy to repository, branch and
  environment.
- Gate release and deploy jobs behind protected environments.

## Third-Party Actions

Pin every third-party action to a full commit SHA with the version in a
comment (`uses: owner/action@<full-sha> # v4`). A tag can be moved to
new code after review; a SHA cannot.

## Self-Hosted Runners

A self-hosted runner that accepts fork PRs runs attacker code on your
machine, and a persistent runner keeps what one job leaves for the
next. Use ephemeral runners, never attach them to public-repository PR
workflows, and keep them off networks with internal access.

## Cache Poisoning

Caches are not a security boundary. A low-trust job that can write a
predictable key poisons whatever a privileged job later restores.

High-risk patterns:

- `actions/cache` in fork-PR workflows writing keys that `push`,
  release or deploy jobs restore.
- Broad keys (`node-${{ runner.os }}`, `pip-cache`) and broad
  `restore-keys` prefixes that let one context squat on another's key.
- Caching executables or dependency trees (`node_modules/`, `.venv/`,
  `vendor/`, `target/`, downloaded tool binaries) that privileged jobs
  then run.
- Caching files that can hold credentials (`.npmrc`, package-manager
  auth, cloud credential files, signing keys).

Safer shape: namespace keys by trust context and lockfile hash, keep
`restore-keys` within the same context, and never let a release or
deploy job restore a cache a PR job can write.

```yaml
key: ${{ github.workflow }}-${{ github.job }}-${{ runner.os }}-${{ hashFiles('**/package-lock.json') }}
```

## Artifacts and Workspaces

An artifact produced by an untrusted run is untrusted data. Bind it by
digest, never re-resolve it by name in a privileged job, and never
execute it there.

## Review Checklist

1. Triggers, and whose code each one runs.
2. Workflow and job `permissions:` blocks.
3. `actions/checkout` `ref:` and `persist-credentials:`.
4. Attacker-written values inside `run:` expressions.
5. Jobs that receive secrets, cloud credentials, package tokens or
   signing keys.
6. Cache paths, keys and `restore-keys` across trust contexts.
7. Artifacts passed from untrusted to privileged jobs.
8. Install steps that run lifecycle scripts.
9. Third-party actions pinned to full SHAs.
10. Runner type for every job that sees untrusted code.

## Example Finding

```text
[BLOCKER] [FIX-NOW] [SECURITY] [TRACE]

Finding: the release workflow restores a cache PR workflows can write.
Impact: a fork PR poisons dependencies that run in a job holding
publish credentials.
Evidence: release.yml restores `${{ runner.os }}-node-`; ci.yml writes
the same prefix on pull_request.
Fix: separate cache namespaces per trust context; drop broad
restore-keys from release.
Validation: release restores only keys written by push-context jobs.
```
