# Supply Chain

Follow integrity from source to the artifact a user runs: who chose each
input, what resolved it, which worker built it, and what proves the
released thing is the reviewed thing. A vulnerable or mutable
dependency matters when someone can influence it and a trusted build
consumes it.

References:
- OSV vulnerability database: https://osv.dev/
- OpenSSF Scorecard: https://securityscorecards.dev/
- SLSA: https://slsa.dev/
- CycloneDX: https://cyclonedx.org/

## Adding a Dependency

1. **Need:** does the standard library or an existing dependency cover
   it?
2. **Name:** check for typosquatting and lookalike names.
3. **Source:** confirm the official registry entry and repository.
4. **Health:** maintenance, maintainers, recent ownership changes.
5. **Install behavior:** does it run lifecycle scripts on install?
6. **Pinning:** record it in the lockfile; commit the lockfile.

Let non-security updates age a few days before adopting them; most
malicious releases are caught and pulled within that window.

## Resolution Risks

- **Namespace confusion:** a resolver can pick a public package over a
  private one of the same name, or fall back to another registry.
- **Mutable inputs:** branches, tags, unpinned submodules, remote
  includes, floating container tags and downloaded tools change without
  review.
- **Lifecycle scripts:** install hooks run arbitrary code on developer
  and CI machines; disable them where the ecosystem allows and the
  project does not need them.
- **Generated content:** generated clients, vendored archives and
  binary blobs enter the build without the review source gets; check
  who controls the generator and its input.
- **Build context:** local config, secrets or fixtures slip into a
  package or image through broad build context and ignore rules.

## Vulnerability Triage

1. Detect the ecosystems from their manifests and lockfiles.
2. Scan with the lockfile; include transitive dependencies.
3. Triage by reachability, exposure and fix availability, not by the
   scanner's severity alone.
4. Prefer the smallest safe upgrade; patches and overrides are
   temporary.
5. Re-run the check and the test suite after the fix.

## Automated Fix PRs

- Confirm the advisory and that the affected path is used.
- Identify whether the fix is direct, transitive, an override or a
  patch.
- Read the release notes for breaking changes.
- Run the test suite before merging; never auto-merge untested.

## Deferring a Vulnerability

Record the reason, the affected packages and paths, compensating
controls and an expiry date; revisit before it expires. A permanent
ignore without evidence is not a disposition.

## Release and Provenance

- Tests, review, signing and publication refer to the same immutable
  digest, not a mutable tag or file name.
- Sign important releases and verify signatures against the expected
  workflow, repository and branch, not only "a valid signature".
- Generate an SBOM (SPDX or CycloneDX) when consumers need inventory.
- An updater authenticates version, channel and target as well as
  payload bytes, and fails closed on missing or revoked metadata.
- A checksum fetched from the same place as the artifact proves
  nothing about the source.

## Common Mistakes

- Scanning only direct dependencies, or scanning without a lockfile.
- Treating scanner severity as the only priority signal.
- Auto-merging fix PRs without tests.
- Keeping ignores forever.
