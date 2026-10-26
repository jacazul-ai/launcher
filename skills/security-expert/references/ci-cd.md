# GitHub Actions Cache Poisoning

Catalog for reviewing GitHub Actions cache poisoning, also known as Actions Cache Blasting.

Reference: https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions

## Risk Summary

GitHub Actions caches are not a security boundary. A low-privilege workflow that can write a predictable cache may poison dependencies, binaries, or generated files later restored by a privileged workflow with secrets, release permissions, or cloud credentials.

## High-Risk Patterns

- `actions/cache` used in workflows triggered by `pull_request` from forks.
- `pull_request_target` workflows that check out or execute untrusted PR code.
- Privileged workflows (`push`, `release`, deploy, publish) restoring caches that untrusted workflows can write.
- Broad or predictable cache keys, such as:
  - `node-${{ runner.os }}`
  - `${{ runner.os }}-node-`
  - `pip-cache`
  - `cargo-${{ runner.os }}`
- Broad `restore-keys` that allow cache squatting.
- Caching executable or dependency directories restored by privileged jobs:
  - `node_modules/`
  - `.venv/`
  - `vendor/`
  - `target/`
  - downloaded tool binaries
- Cached files that may contain secrets:
  - `.npmrc`
  - package-manager auth config
  - cloud credential files
  - signing keys
  - generated config containing tokens

## Safer Cache Design

Prefer strong, context-specific keys:

```yaml
key: ${{ github.workflow }}-${{ github.job }}-${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}
```

Use PR-specific prefixes for untrusted workflows:

```yaml
key: pr-${{ github.event.pull_request.number }}-${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}
```

Avoid broad restore keys. If restore keys are necessary, keep them constrained to the same trust context:

```yaml
restore-keys: |
  ci-${{ github.ref_name }}-${{ runner.os }}-node-
```

Do not let deploy/release workflows restore caches written by PR workflows.

## `pull_request_target` Rules

`pull_request_target` runs with the target repository context and can access elevated permissions/secrets depending on workflow configuration. Treat it as dangerous when combined with untrusted checkout or execution.

Avoid:

```yaml
on: pull_request_target
steps:
  - uses: actions/checkout@v4
    with:
      ref: ${{ github.event.pull_request.head.sha }}
  - run: npm install && npm test
```

Safer patterns:
- Do not check out untrusted PR code in `pull_request_target`.
- Keep permissions minimal.
- Use `persist-credentials: false` when checkout is necessary.
- Avoid secrets and cache writes in workflows touching untrusted code.
- Pin third-party actions to a full commit SHA
  (`uses: owner/action@<full-sha> # vX`) so a moved tag cannot rotate
  code into a privileged workflow.

## Permission Baseline

Default to minimal permissions:

```yaml
permissions:
  contents: read
```

Grant additional scopes only per job and only when needed.

## Review Checklist

Inspect each workflow for:

1. Triggers: `pull_request`, `pull_request_target`, `workflow_run`, `push`, `release`.
2. Workflow/job `permissions:` blocks.
3. `actions/checkout` usage, especially `ref:` and `persist-credentials:`.
4. `actions/cache` paths, keys, and `restore-keys`.
5. Jobs that receive secrets, cloud credentials, package tokens, or signing keys.
6. Artifact upload/download between untrusted and privileged jobs.
7. Dependency install steps that execute lifecycle scripts.
8. Generated files persisted across jobs or workflows.
9. Release/deploy jobs restoring dependencies or binaries from cache.
10. Third-party actions pinned to full commit SHAs instead of mutable
    tags.

## Finding Template

```text
Finding: Privileged release workflow restores a cache writable by PR workflows.
Impact: A fork PR can poison dependencies restored during release and execute code in a secrets-bearing job.
Evidence: .github/workflows/release.yml restores key `${{ runner.os }}-node-`; .github/workflows/ci.yml writes same prefix on pull_request.
Fix: Split cache namespaces by trust context and remove broad restore-keys from release.
Validation: Confirm release only restores keys prefixed with release/push context and PR workflows cannot write matching keys.
Priority: High
```
