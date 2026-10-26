# Dependency Security Scanning

Catalog for dependency vulnerability analysis, SBOM generation, license risk review, and supply-chain remediation.

References:
- OSV vulnerability database: https://osv.dev/
- OpenSSF Scorecard: https://securityscorecards.dev/
- CycloneDX SBOM standard: https://cyclonedx.org/
- Adapted in part from PocketCmds/Snyk dependency workflows (attribution in SKILL.md).

## Use When

- Auditing dependencies for CVEs, malicious package risk, or license exposure.
- Reviewing package-manager lockfiles or dependency update PRs.
- Generating SBOMs for compliance or supply-chain visibility.
- Planning remediation for vulnerable direct or transitive dependencies.
- Reviewing automated security fix PRs.

## Do Not Use When

- There is no dependency manifest or lockfile.
- The user only needs runtime security testing.
- The environment forbids running or uploading scanner data.
- Auto-fix would be unsafe without release/test approval.

## Baseline Workflow

1. Detect ecosystems and manifests:
   - npm/yarn/pnpm: `package.json`, lockfiles
   - Python: `requirements.txt`, `pyproject.toml`, lockfiles
   - Go: `go.mod`, `go.sum`
   - Rust: `Cargo.toml`, `Cargo.lock`
   - Java: `pom.xml`, `build.gradle`
2. Prefer lockfile-aware scanning.
3. Include transitive dependencies, not only direct dependencies.
4. Generate or request SBOM when supply-chain visibility is in scope.
5. Triage by severity, exploitability, exposure, and fix availability.
6. Remediate with minimal safe upgrades where possible.
7. Verify by re-running relevant checks and tests.

## Tooling Examples

Use approved tooling available in the environment. Examples include:

- Snyk Open Source: `snyk test`, `snyk monitor`, `snyk test --json`, `snyk test --sarif`
- Trivy: dependency and container vulnerability scans
- OSV Scanner: open-source vulnerability database checks
- npm audit / pip-audit / cargo audit / govulncheck
- Syft/CycloneDX tooling for SBOM generation

Do not require Snyk specifically unless the project already uses it.

## Automated Fix PR Review

When reviewing automated dependency fix PRs:

- Confirm the CVE/security advisory and affected path.
- Identify whether the fix is direct, transitive, override-based, or patch-based.
- Review release notes and breaking-change risk.
- Run the relevant test suite before merge.
- Prefer upgrades over temporary patches.
- Require expiration dates and rationale for ignored/deferred vulnerabilities.
- Verify the vulnerability is gone after merge.

## Risk Acceptance Rules

If a vulnerability is deferred:

- Record the reason.
- Record affected packages and paths.
- Add an expiration date.
- Identify compensating controls.
- Revisit the decision before expiration.

Permanent ignores without evidence are not acceptable.

## Common Mistakes

- Scanning only direct dependencies.
- Ignoring transitive dependency paths.
- Running scans without lockfiles.
- Auto-merging fix PRs without tests.
- Keeping ignores forever.
- Failing to monitor main/default branch after initial scan.
- Treating scanner severity as the only priority signal.

## Output Template

```text
Finding: Vulnerable transitive dependency remains in runtime dependency graph.
Impact: Attackers may exploit CVE-XXXX when the affected code path is reachable.
Evidence: package-lock.json includes vulnerable package through dependency path A > B > C.
Fix: Upgrade parent dependency or apply package-manager override to a patched version.
Validation: Re-run dependency scan and project test suite; confirm CVE no longer appears.
Priority: High
```
