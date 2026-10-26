# Tools

Names and purposes only. Use what the project already configures; a
tool here is optional unless the repository makes it a gate. All are
open source or free to run locally. Usage, flags and commands are
deliberately absent: read the tool's own documentation when the work
needs it.

## Secrets

| Tool | Purpose |
|---|---|
| gitleaks | Detect secrets in the working tree and Git history |
| trufflehog | Detect and verify live secrets across repositories and history |

## Dependencies and Vulnerabilities

| Tool | Purpose |
|---|---|
| osv-scanner | Match lockfiles against the OSV vulnerability database |
| Trivy | Scan dependencies, container images and IaC for known vulnerabilities |
| npm audit | Audit npm dependency trees |
| pip-audit | Audit Python environments and requirement files |
| cargo audit | Audit Rust lockfiles against the RustSec database |
| govulncheck | Report Go vulnerabilities reachable from the code |

## SBOM and Provenance

| Tool | Purpose |
|---|---|
| Syft | Generate an SBOM from a directory or image |
| CycloneDX tooling | Generate and validate CycloneDX SBOMs per ecosystem |
| cosign | Sign and verify artifacts and container images |
| OpenSSF Scorecard | Score a repository's supply-chain practices |

## Static Analysis

| Tool | Purpose |
|---|---|
| Semgrep | Pattern-based multi-language SAST with custom rules |
| CodeQL | Dataflow-based multi-language SAST |
| Bandit | Python security linter |
| gosec | Go security linter |
| ESLint security plugins | JavaScript and TypeScript security rules |
| Brakeman | Ruby on Rails security scanner |

## CI and Containers

| Tool | Purpose |
|---|---|
| actionlint | Lint GitHub Actions workflows, including expression misuse |
| zizmor | Find security issues in GitHub Actions workflows |
| Hadolint | Lint Dockerfiles for unsafe patterns |
