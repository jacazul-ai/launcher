# GitHub Broker & Hierarchical Vault

The GitHub Broker ("The Protocol") provides a bidirectional bridge between Taskwarrior tasks and GitHub Issues/PRs, secured by IdZoid's `cryptozoid` encryption.

## 🔐 Hierarchical Vault (vault.json)

Jacazul manages multiple GitHub tokens using a hierarchical resolution strategy. Tokens are stored in `~/.jacazul-ai/vault.json` and are encrypted using EC P256 keys.

### Resolution Precedence:
1. **Project:** Specific token for a repository (`user|org/project`).
2. **Owner:** Token for an entire organization or user account (`user|org`).
3. **Classic Default:** A fallback classic token used if no granular token is found.
4. **System Default:** The native GitHub CLI login (`gh auth login`).

## 🛠️ Jacazul GitHub Manager (jacazul-github)

Use this tool to manage your encrypted tokens.

### Launcher behavior

When you run `scripts/configure`, Jacazul exposes `jacazul-github` through a project-owned launcher instead of a pip-generated console-script shim. If an older shim exists in `~/.local/bin/jacazul-github`, configure replaces that Jacazul-specific shim with a link to the portable launcher so the command also works when `~/.local/bin` appears before `~/bin` in your `PATH`.

### Common Commands:
```bash
# Show current configured scopes
jacazul-github list

# Setup a token for an organization
jacazul-github auth --org jacazul-ai

# Setup a token for a specific project
jacazul-github auth --org jacazul-ai --project launcher

# Setup a fallback classic token
jacazul-github auth --classic
```

### Fine-grained PAT permissions for private repositories

When using GitHub fine-grained PATs with private repositories, select the target
repository and grant at least:

| Permission | Access |
|---|---|
| Metadata | Read |
| Contents | Read |
| Issues | Read and Write |
| Pull requests | Read and Write, only if PR automation is needed |

`Contents: Read` is required even for issue creation because GitHub CLI's
`gh issue create` queries repository metadata such as `repository.defaultBranchRef`.
Without it, `jacazul-broker open` may fail with:

```text
GraphQL: Resource not accessible by personal access token (repository.defaultBranchRef)
```

## 🚀 GitHub Broker (The Protocol)

The Broker is the engine that performs the actual synchronization.

### Key Features:
- **Git Context Inference:** Automatically detects Org and Project from local `.git` remotes.
- **Hierarchical Decryption:** Resolves and decrypts the best token from the vault.
- **Killer Sync:** Automatically closes Taskwarrior tasks if the corresponding GitHub issue is marked as `CLOSED`, keeping their titles and recording an `OUTCOME:` annotation. It runs on `jacazul-broker sync` and `tw-flow done`; `tw-flow ticket` only links and never syncs, so linking tasks to a closed issue does not close them.
- **Error as Prompt:** The Broker provides `ACTION:` hints and returns non-zero exit codes on failure.

### Provider selection

Broker selection follows this precedence:

1. An explicit pattern in `~/.jacazul-ai/brokers.json`.
2. The ticket identifier format: `#123` selects GitHub and `ORG-123`
   selects Bitbucket/Jira.
3. The current Git remote as a fallback when the ticket does not identify a
   provider.

This allows a project hosted on GitHub to track an external Bitbucket/Jira
ticket without routing the external ticket to `GitHubBroker`.

### CLI Commands (Direct Use)

Every command accepts the repository as `repo="org/name"`. When you omit it,
the Broker infers the repository from the current git remote.

```bash
# Show an issue with its full body
jacazul-broker view '<id>' [repo="org/repo"]

# Sync local tasks with GitHub status
jacazul-broker sync '<id>' [repo="org/repo"]

# List issues
jacazul-broker list [repo="org/repo"] [state="open|closed|all"] \
  [milestone="name"]

# List repository labels and milestones (cached)
jacazul-broker labels [repo="org/repo"]
jacazul-broker milestones [repo="org/repo"]

# Open a new issue
jacazul-broker open title="Issue Title" [body="Description"] \
  [body_file="/path/body.md"] [repo="org/repo"] [assignee="@me"] \
  [labels="bug,ui"]

# Edit an existing issue
jacazul-broker edit '<id>' [title="New Title"] [body="New body"] \
  [body_file="/path/body.md"] [repo="org/repo"] [assignee="@me"] \
  [remove_assignee="login"] [add_labels="enhancement"] \
  [remove_labels="bug"]

# Comment on an existing issue
# Use body_file= for Markdown/multiline comments, same as issue descriptions.
jacazul-broker comment '<id>' [body="Comment"] \
  [body_file="/path/comment.md"] [repo="org/repo"]

# Close an issue
jacazul-broker close '<id>' [repo="org/repo"] [comment="Reason"]
```

Run `jacazul-broker --help` for the same reference in the terminal.

### Argument rules

| Trigger | What happens |
|---|---|
| You want a specific repository | Pass `repo="org/name"` — works on every command |
| You omit the repository | It is inferred from the current git remote |
| You pass the repository positionally to a read command | Accepted, but prints a deprecation warning |
| You pass the repository positionally to `open`, `edit` or `comment` | Rejected with an `ACTION:` hint |
| You misspell a keyword | Rejected with the list of accepted keywords |
| You pass a malformed repository | Rejected before `gh` runs |
| You want to skip a positional argument | Use `-`, e.g. `jacazul-broker list - closed` |
| Your issue id starts with `#` | Quote it: `'#106'` — an unquoted `#` starts a shell comment |

Multi-value options (`labels`, `add_labels`, `remove_labels`, `assignee`,
`remove_assignee`) accept comma-separated values. Assignee logins may be
`@me` or `@copilot`.

Nothing is dropped silently: an unrecognized or misplaced argument always
fails with a non-zero exit code, never a quiet fallback to the inferred
repository.

### Token resolution timeout

Token decryption is bounded. If `cryptozoid` does not answer within 30
seconds, the Broker aborts with an `ACTION:` hint instead of hanging the
caller. Override the bound with `JACAZUL_BROKER_DECRYPT_TIMEOUT` (seconds).

## 🧪 IdZoid Security Integration

All tokens are processed via `cryptozoid`. 
- **Encryption:** `cryptozoid ec encrypt`
- **Decryption:** `cryptozoid ec decrypt`
- **Cleaning:** The Broker automatically strips trailing newlines (`\n`) from decrypted tokens to ensure API compatibility.

---
**Version:** 1.2.0  
**Last Updated:** 2026-09-04
