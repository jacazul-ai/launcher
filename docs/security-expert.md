# Security Expert Skill

Guide for the security-expert skill: a light checklist while you
develop, topic guidance when you touch a security surface, and a full
audit inside every code review.

## Trigger → Action

### When you are about to call a code change done

The agent walks the light checklist of `skills/security-expert/SKILL.md`
over what you touched: secrets, untrusted input, authorization, new
dependencies, secure defaults, least privilege, cryptography, and the
language surface. It flags in plain words and never blocks.

A plaintext secret or untrusted code in a privileged context gets one
warning and a question: continue? Say yes and it stops raising it for
that change. The review still reports it as a `BLOCKER`.

### When the change touches CI, secrets, dependencies or publishing

The skill loads on demand and routes to one primary reference under
`skills/security-expert/references/`:

| Work | Reference |
|---|---|
| Mapping principals, entry points and attacker paths | `threat-modeling.md` |
| Workflows, triggers, permissions, runners, caches, artifacts | `ci-cd.md` |
| Storing, passing, detecting or rotating a credential | `secrets.md` |
| Dependencies, lockfiles, SBOM, release and signing | `supply-chain.md` |
| Injection, XSS, traversal, deserialization, SSRF | `sast.md` |
| Access control, sessions, tokens, OAuth, MFA, API keys | `auth-and-web.md` |
| Cloud IAM, containers, ingress, network exposure | `cloud-and-containers.md` |
| Agent permissions, tool calls, MCP, prompt injection | `agent-tools.md` |
| Which tool exists for a check | `tools.md` |

The guidance is local and works offline. External links are further
reading, never a runtime requirement.

### When you ask for a code review

`code-review` brings `security-expert` into every diff as an extension.
It audits the changed code plus the affected context and reports on the
shared code-review scale under area `SECURITY`. A `BLOCKER` needs a
reproduction, a clear trace or strong tool evidence; a concern that
depends on an unverified fact is `HEURISTIC` and does not block.

### When you want a deeper or lighter security review

Set the depth for the project in the `## Security Review` section of
`AGENTS.md`, or ask for it in one review ("review this one in high"):

| Depth | Covers |
|---|---|
| `low` | The changed code only |
| `medium` | The changed code plus callers, callees, trust boundaries and side effects (the default) |
| `high` | `medium` plus every surface of the same class in the repository |

```markdown
## Security Review

- depth: medium
```

Without the section the default is `medium`, and the agent says so.

### When you use your own language skill

The checklist and the review point to the language skill in use for
that language, not only to the Jacazul experts. With none in use, the
agent infers the language from the files and uses any installed skill
for it; with none installed, it uses general knowledge and says that no
language skill covered it.

### When a scanner reports Critical, High, Medium or Low

The code-review core maps scanner severities: Critical to `BLOCKER`,
High to `WARNING`, Medium to `SUGGESTION`, Low to `NIT`. The consequence
decides promotion: a High that a trace shows reachable from untrusted
input, with no compensating control, becomes a `BLOCKER`. The skill
itself keeps no severity scale.

### When you need a scanner

`references/tools.md` names open tools by purpose (secrets,
dependencies, SBOM and provenance, static analysis, CI and containers).
None is mandatory unless the project configures it, and usage is left
to each tool's documentation.

### When validation would require running untrusted code

It does not run. Security validation reads source, and no sandbox
exists yet; the hub records this as a TODO.

## Provenance

| Source | Role |
| --- | --- |
| [`cloudflare/security-audit-skill`](https://github.com/cloudflare/security-audit-skill) | Architectural baseline |
| [OWASP Top 10 Proactive Controls](https://owasp.org/www-project-proactive-controls/) | Light checklist |
| [OpenSSF Concise Guide for Developing More Secure Software](https://best.openssf.org/Concise-Guide-for-Developing-More-Secure-Software) | Light checklist |
| [CWE Top 25](https://cwe.mitre.org/top25/) | Checklist and scenario priority |
| [OWASP ASVS](https://owasp.org/www-project-asvs/), [GitHub Actions hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions), [SLSA](https://slsa.dev/), [OSV](https://osv.dev/), [CycloneDX](https://cyclonedx.org/) | Further reading in the references |
| PocketCmds/StackSnyk SAST and hardening pages | Historical: earlier catalogs adapted parts of them |

Cloudflare baseline:

| Field | Value |
| --- | --- |
| Reviewed at | `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`, dated 2026-09-14 |
| Reviewed on | 2026-10-22 |
| Licence | MIT, Copyright (c) 2025-2026 Cloudflare, Inc. |

Nothing in the skill is a copy. The hub-plus-references layout, the
source-first trust-boundary method and the domain split come from the
Cloudflare skill; the text was rewritten for this repository. Left out
on purpose: the multi-agent full-audit workflow, the coverage ledger,
the validators and report schema, and the sandbox execution and
artifact-promotion rules, which no harness here can enforce.

The PocketCmds/StackSnyk pages
(`https://pocketcmds.com/skills/snyk/snyk-security-sast`) are third-party
guidance, not official Snyk material. Snyk has no operational role in
the skill: it is not a required tool, dependency or source.
