# Agent Tools

Covers code where a language model takes part in a trust decision:
agents with tools, MCP servers and clients, retrieval pipelines,
persistent memory, and code that acts on model output. The data flow
to follow is untrusted content, into the model or memory, out to a
capability or sink.

## Core Rules

- **Prompt injection alone is not a finding.** Report a deterministic
  control that fails: content reaches another principal's context,
  invokes authority the requester lacks, discloses data they cannot
  read, or drives a sink they cannot reach.
- **Model output is untrusted input.** So are tool descriptions,
  memory records and MCP responses.
- **A guardrail prompt is not a boundary.** Only deterministic checks,
  per-resource authorization, isolation and constrained credentials
  count.

## Tools and Actions

- **Arguments into sinks:** model-produced tool arguments reaching SQL,
  shell, filesystem, URL fetches or privileged APIs need the same
  validation as any user input. A schema narrows shape; it does not
  authorize.
- **Borrowed authority:** a tool running with a broad service credential
  must re-check that the requester may perform that exact operation on
  that resource.
- **Approval binding:** an approval covers the exact tool, arguments,
  target and requester shown. A retried, resumed or edited call needs a
  new approval.
- **Unbounded loops:** a single request must not queue unlimited spend,
  sends or mutations; budget and cancel per request.

## Context and Memory

- Retrieved documents, issues, emails and tool results that another
  principal can write are indirect injection channels; check what the
  consuming session can do with them.
- Retrieval, history and caches must carry tenant scope in the query
  and the cache key.
- Memory writers decide what later sessions trust; low-trust
  observations must not become durable instructions.
- Untrusted text must not be able to pose as a system message, tool
  result or policy through string assembly.

## MCP and Delegation

- Route results by the authenticated connection and pending request,
  not by a server or tool name the peer chooses.
- Tool metadata and schemas from a peer guide the model; they never
  grant capability.
- A sub-agent receives the least authority its task needs, and its
  results are untrusted on return.

## Permissions and Allowlists

- Agent tool allowlists name the commands and paths needed, not
  wildcards.
- Credentials stay out of model context; when the repository provides a
  broker or vault for them, agents use it and never handle the raw
  value.
- Skills, plugins and MCP servers installed from outside are third-party
  code: review what they can run and reach before enabling them.
