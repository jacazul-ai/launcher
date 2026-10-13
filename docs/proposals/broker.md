# Proposal: The Broker Project

**Status:** Research. No repository, issue or plan exists yet; creating them
waits for the operator.
**Audience:** Contributors planning the Go migration and the broker rewrite.
**Related:** #113, #137, plan `jacazul-home` (DECISION notes on `2b75bf44`),
[`go-launcher.md`](go-launcher.md), `github-expert`, `go-expert`.

## Why it leaves the launcher

The launcher prepares the environment and starts a harness. The broker is a
tool the agent calls during the session to reach a ticket service; it works
the same with any harness and without the launcher. Today it lives here as
Python (`jacazul/cli/broker.py`, `jacazul/cli/github.py`,
`scripts/jacazul-github`) and dies with the Python cutoff, so it is rewritten
once, in Go, in its own project instead of being ported into the launcher.

The only contract between the launcher and the broker is
`JACAZUL_VAULT_DIR`, exported by the launcher (`~/.jacazul/vault` by
default).

## One project, several brokers

One binary, one subcommand per provider:

```text
jacazul-broker github view '#113'
jacazul-broker jira view ORG-123
```

- One vault: `vault.json` already keeps each service under its own key
  (`github` today), and the cryptozoid keys serve every provider.
- One set of rules for every provider: the agent never sees a token,
  parsing fails closed on an unknown argument, and every error carries an
  `ACTION:` hint.
- The ticket format picks the provider (`#123` is GitHub, `ORG-123` is
  Jira), as it does today.

Only GitHub is real today; the Bitbucket/Jira broker in
`jacazul/taskwarrior/core.py` is a stub. The provider abstraction is
introduced when the second provider is real, not before.

## Process model: privilege separation, Postfix style

Postfix runs a small `master` that starts single-purpose processes with the
least privilege each needs; the process that talks to the network never
reads the queue. The broker follows the same split:

```text
jacazul-broker (CLI the agent calls)
   |
   |-- vault ..... the only process that opens vault.json and the keys;
   |               decrypts and signs; never talks to the network
   |
   |-- github .... talks to api.github.com; asks vault to sign a request;
   |               never sees the vault file or a key
   |
   \-- jira ...... same contract, its own process and scope
```

Rules that hold from the first version:

- Only the vault process reads `JACAZUL_VAULT_DIR`.
- A provider receives its own section only, never a file path or a key.
- The provider builds the request (method, URL, body); the vault process
  adds the credential. A decrypted token does not leave the vault process,
  so a provider written by a third party can be added later without
  changing the vault.

## Phases

1. **Pipes, no daemon.** Each call to `jacazul-broker` starts the provider
   as a child process and talks to it over stdin and stdout. A provider
   asks the parent to sign a request over the same pipe. Privilege
   separation exists with no socket to manage.
2. **Vault agent.** The vault process becomes persistent, like `ssh-agent`,
   listening on `$JACAZUL_VAULT_DIR/agent.sock`. It keeps the key unlocked
   between calls, which removes the repeated passphrase prompt and the
   "Token decryption timed out" failure. It ships only when that cache
   justifies running a daemon.

Both phases speak the same protocol; only the transport changes.

## Windows transport

Phase 1 needs nothing per platform: `os/exec` wires anonymous pipes to the
child's stdin and stdout the same way on Linux, macOS and Windows.

Phase 2 needs one listener per platform. Windows has no full Unix socket
equivalent for a process that holds keys; its native transport is the named
pipe, the one OpenSSH for Windows (`\\.\pipe\openssh-ssh-agent`) and Docker
(`npipe:////./pipe/docker_engine`) use.

| Concern | Linux and macOS | Windows |
|---|---|---|
| Transport | Unix socket at `$JACAZUL_VAULT_DIR/agent.sock` | Named pipe `\\.\pipe\jacazul-vault-<user>` |
| Access control | `0700` directory, `0600` socket | Pipe ACL granting only the user's SID (SDDL `D:P(A;;GA;;;<SID>)`) |
| Caller identity | `SO_PEERCRED` peer UID | `GetNamedPipeClientProcessId` or client impersonation |
| Go support | Standard library, `net.Listen("unix", ...)` | `github.com/Microsoft/go-winio`, `winio.ListenPipe` |

Both listeners return a `net.Listener` whose connections are `net.Conn`, so
the protocol and the vault logic are shared and only the listener differs:

```text
agent/
|-- listen_unix.go      //go:build !windows
|-- listen_windows.go   //go:build windows
\-- agent.go            serves net.Conn on every platform
```

Windows 10 1803 and later also accept `AF_UNIX`, and `net.Listen("unix")`
works there, but without peer credentials and with access left to the file
ACL; it is not used for the vault agent. Postfix-style FIFO triggers have no
direct Windows equivalent and are not needed, since every broker exchange is
request and response.

## Plugin mechanisms considered

| Mechanism | Verdict |
|---|---|
| Standard library `plugin` (`.so`) | Rejected: no Windows, needs cgo and identical Go and dependency versions, cannot unload. |
| Compile-time registration (`init()` + blank import, as `database/sql`) | Fits first-party providers compiled into one binary. |
| External binary on `PATH` (as `git` and `gh` extensions) | Fits third-party providers only behind the signing contract above. |
| `hashicorp/go-plugin` (subprocess plus gRPC) | Too heavy until there is a third-party ecosystem. |

## Open decisions

- Who starts and stops the vault agent in phase 2: the launcher, systemd
  socket activation, or the CLI on first use.
- How a caller is authenticated on the socket: `0600` socket plus peer UID
  (`SO_PEERCRED`), and the named-pipe equivalent on Windows.
- Whether phase 2 takes the `go-winio` dependency, built only on Windows,
  or ships the vault agent on Linux and macOS first.
- Wire protocol and its versioning (JSON lines is the default candidate).
- Whether `github-expert` moves with the broker or stays here as usage
  documentation.
- Repository name (`jacazul-ai/broker` is the working name).

## References

- [Postfix architecture overview](https://www.postfix.org/OVERVIEW.html).
- [Go `plugin` package](https://pkg.go.dev/plugin) and its warnings.
- [`database/sql` driver registration](https://pkg.go.dev/database/sql#Register).
- [hashicorp/go-plugin](https://github.com/hashicorp/go-plugin).
- [Microsoft/go-winio](https://github.com/microsoft/go-winio) named pipes.
- [AF_UNIX on Windows](https://devblogs.microsoft.com/commandline/af_unix-comes-to-windows/).
