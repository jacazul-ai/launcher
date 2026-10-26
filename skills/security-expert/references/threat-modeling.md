# Threat Modeling

Map the system before judging it. A finding exists only when a
lower-trust principal can cross a boundary and reach an outcome it
should not; a missing control with no reachable path is hardening.

## Four Maps

Draw these first, from source, before reading for bugs:

| Map | Question |
|---|---|
| Principals | Who acts on the system, and what may each do by design? Users, tenants, contributors, CI jobs, workloads, agents, plugins. |
| Entry surfaces | Where does outside input arrive? HTTP, RPC, files, CLI, environment, config, dependencies, CI events, model context, IPC. |
| Authority | Which identities hold privilege, and where is it exercised? Tokens, service accounts, write permissions, release keys, tool credentials. |
| Sinks | Where does data cause an effect? Interpreters, filesystem, network fetches, publication, durable state, other users' views. |

Connect them: follow each entry surface to the authority and sink it
reaches, and mark the control on every edge.

## Attacker Paths

- Start at the privileged action and walk backward to every input that
  can influence it; start at each entry surface and walk forward.
- Compare parallel paths to the same effect: direct, queued, retry,
  batch, legacy, error and recovery routes. The effective policy is the
  weakest one.
- Follow copies: caches, artifacts, generated files and stored records
  carry input across time and trust contexts.

## STRIDE as a Prompt

Use it to ask questions, not as a form to fill:

| Threat | Ask |
|---|---|
| Spoofing | Can a principal claim another identity? |
| Tampering | Can lower-trust input change trusted data or code? |
| Repudiation | Can an action happen without a record? |
| Information disclosure | Can data reach a reader without access? |
| Denial of service | Can a bounded request trigger unbounded work? |
| Elevation of privilege | Can a principal gain authority it lacks? |

## What a Finding Must Name

1. The attacker and the position they start from.
2. The input they control.
3. The boundary crossed and the control that failed or is missing.
4. The affected principal or resource.
5. The observable outcome.

If one of these depends on a fact outside the source (deployment
settings, branch protection, provider defaults), the finding is
`HEURISTIC` until that fact is known.

## What Is Not a Finding

- A missing header, flag or rate limit with no reachable effect.
- A vulnerable dependency whose affected code is never reached.
- Behavior a principal already has by design, such as running their own
  code with their own access.
- Text that persuades a model, without a deterministic control failing.
