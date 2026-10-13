# Package and API Design

Owner of: package boundaries, public API surface, compatibility contracts, and
the standard library as a design reference.

## Before writing code

1. Read the module's `go` directive and identify the supported toolchain.
2. Read the target package and its tests before introducing an abstraction.
3. Define the API contract: valid input, absence, errors, timeouts, retries,
   partial success, ownership, and shutdown behavior.
4. Identify trust boundaries: users, network payloads, files, subprocesses,
   databases, dependencies, generated data, and logs — see
   [security](security.md).
5. Decide who owns every mutable value, resource, goroutine, channel, lock,
   transaction, and cancellation signal — see [values](values.md).

## Size the structure to the project

Architecture complexity should match project scope. Splitting a small program
into layers costs clarity and buys nothing.

| Project size | Shape |
| --- | --- |
| Script or small CLI, under ~500 lines | Flat `main.go` plus a few files, no layers |
| Medium service, ~500 to 5K lines | Simple layered split by behavior |
| Large service, 5K+ lines | Ask the team which boundary discipline it wants |

A 100-line CLI does not need a domain layer, ports and adapters, or a
dependency-injection container. Start simple and restructure when complexity
demands it, not when a diagram suggests it.

This skill does not prescribe a named architecture. Clean, hexagonal, and DDD
are team choices with real trade-offs, not Go defaults, and adopting one is a
project decision rather than a style correction.

## Keep the dependency direction honest

Domain logic should not import infrastructure. Database access, HTTP clients,
and message queues live in packages that depend on the domain — never the
reverse. This holds whatever the team calls its layering, and it is the part
of "clean architecture" that survives without the ceremony.

## Validate at the boundary, then trust

Validate input where it enters the system: HTTP handlers, CLI argument
parsing, message consumers, file and subprocess reads. Once data has passed
the boundary, internal code should trust it.

Do not re-validate the same value at every layer. It clutters the happy path
and produces the same error from several places, so the caller cannot tell
which check actually fired. This is the same rule that keeps error context
from being restated at every level — see [errors](errors.md), and
[security](security.md) for what boundary validation must cover.

## Package design

- Package names: short, lowercase, named by the behavior or domain they
  provide — not artificial layers.
- Avoid grab-bag packages (`util`, `common`, `helpers`) unless the repository
  already uses that convention and the package has a clear boundary.
- Prefer a small public API; keep unexported details inside the owning
  package.
- Prefer concrete types and package functions until a real consumer needs an
  interface or a test seam.
- Define small interfaces near the consumer; name them by behavior — see
  [naming](naming.md).
- Preserve compatibility deliberately: exported types, errors, wire formats,
  and serialization details are contracts once consumers depend on them.

Do not split code into layers to look architectural. A package earns its
boundary by owning behavior, not by occupying a position in a diagram.

## `internal/` is enforced, not agreed

A package under `internal/` can be imported only from the tree rooted at
`internal/`'s parent. That is the compiler refusing, not a convention
people honour — which makes it the one boundary that actually holds.

Use it for everything that is not part of the module's contract. Code you
have not committed to can then be changed without a major version, and the
`pkg/` directory that exists to signal "public" stops being necessary: what
is not in `internal/` is already public.

A multi-module checkout uses a `go.work` file (Go 1.18+) so the modules
resolve against each other locally instead of through published versions.
It belongs to the developer's checkout, not to the module's contract.

## The module files

`go.mod` records the module path, the language version through the `go`
directive, and the *minimum* version of each dependency. Go resolves a
build with Minimal Version Selection: it takes the highest minimum any
module in the graph asks for, and no more. That is why a build does not
drift when an upstream dependency publishes a release, and why upgrading
is an explicit act rather than a side effect of time passing.

From v2 on, the major version is part of the module path: `/v2` ends the
`module` line in `go.mod` and every import of it; v0 and v1 carry no
suffix. This is Semantic Import Versioning, enforced by the toolchain, and
it follows from the import compatibility rule: "If an old package and a new
package have the same import path, the new package must be backwards
compatible with the old package." A new major is therefore a different
module. Both majors can coexist in one build, `go get -u` never crosses a
major, and `go get` on the unsuffixed path resolves to the last version
published without the suffix, however old. Moving to a new major means
changing the imports. A `+incompatible` version is a v2+ tag of a module
that never adopted the suffix.

`go.sum` records the expected hash of every module in the graph. It is a
tamper check, not a lockfile — MVS already makes the version selection
deterministic — and it belongs in the repository.

Read the `go` directive before judging anything version-sensitive; the rule
is in [runtime](runtime.md).

## Exports and imports

Unexport by default. Exporting later is additive; unexporting later breaks
every consumer, so the asymmetry should decide the default.

When an identifier does have to change, rename it with `gopls` rather than
with grep or sed: it updates every call site in the module atomically, and
it refuses the change when lowercasing a method would break an interface
the type satisfies — a breakage a textual replace ships silently.

A blank import (`_ "pkg"`) runs a package's `init` for its side effect.
Confined to `main` and test packages, that side effect is visible at the
root where someone can reason about it; buried in a library, it fires for
anyone who imports the library for unrelated reasons. A dot import removes
the one clue that says where a name came from — keep it out of library
code entirely.

Within a file, the conventional order is package doc, imports, constants,
types, constructors, methods, then helpers, with a type and its methods
kept together. One primary type per file once it carries real behavior.

## Standard library as design compass

When unsure, look for the pattern in the standard library first — do not
invent a framework pattern when a standard-library pattern is enough:

- `io` for small behavior interfaces.
- `net/http` for handlers and middleware shape.
- `context` for cancellation and deadlines.
- `errors` for wrapping and matching.
- `testing` for table tests and benchmark/fuzz conventions.
- `database/sql` for interface boundaries and explicit error handling.

**Sources:**

- https://go.dev/ref/mod#major-version-suffixes
- https://go.dev/blog/v2-go-modules
- https://research.swtch.com/vgo-import
