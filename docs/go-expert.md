# Go Expert Skill

Guide for the go-expert skill: idiomatic Go, explicit quality-gate boundaries,
`gofmt` then `goimports` formatting, and Line of Sight readability.

## Trigger → Action

### When the user asks for a Go code review

Use the implementation guidance in
the topic references under
[`skills/go-expert/references/`](../skills/go-expert/references/) when writing
Go. Use the separate scenario-based directives in
[`skills/go-expert/CODE-REVIEW.md`](../skills/go-expert/CODE-REVIEW.md) when
reviewing it. Start with the `go` directive in `go.mod` before judging
version-sensitive behavior.

The main skill page provides both entry points:
[`skills/go-expert/SKILL.md`](../skills/go-expert/SKILL.md). Repository
configuration takes precedence over optional checks.

Classify each review finding using the global
[`code-review` scale](../skills/code-review/SKILL.md): technical level, impact
area, evidence, and advisory. A non-blocking `FIX-OR-TECH-DEBT` finding must be
corrected or converted into a linked `TECH-DEBT` task with context and
acceptance criteria; it must not silently become “later.” Time-dependent tests
using `time.Now()` or mixed UTC/timezone semantics are a standard example.

### When Go tests must vary environment before initialization

Use an environment-guarded helper process when a variable such as `TZ` must be
set before package initialization or `sync.Once` setup. This is a valid
standard-library Go idiom: re-execute the test binary with `os.Executable()`,
set a guard such as `GO_WANT_EPOCH_HELPER=1`, pass the selected environment,
and limit the child with `-test.run=^TestName$`. It lets date tests run a fixed
epoch under multiple timezone interpretations without reusing the parent's
initialized state. The helper-process pattern is standard-library-backed; the
timezone/date scenario is our application-specific use of it.

The child is a full test binary, so its stdout ends with the harness's own
`PASS` line after the helper branch returns. Read the first line of the
output, never the whole capture, and do not call `os.Exit(0)` from the test
function to suppress it.

See the [process-isolated test guidance][go-helper-tests] and the [review
directive][go-helper-review] for the guard, `os.Executable()`, direct
`exec.Command`, and evidence rules.

[go-helper-tests]: ../skills/go-expert/references/testing.md#process-isolated-tests-for-initialization-time-environment
[go-helper-review]: ../skills/go-expert/CODE-REVIEW.md#init-time-environment-changes-and-helper-process-tests

### When the user asks for Go formatting

Run `gofmt` first, then run `goimports` if available. This is the preferred
operational sequence even though `goimports` is `gofmt`-compatible: normalize
formatting first, then organize imports.

If `goimports` is unavailable, use `gofmt` alone and say that the import
organization pass was skipped. In COUNSELOR mode, ask for authorization before
installing missing tools. When authorized, install with:

```bash
go install golang.org/x/tools/cmd/goimports@latest
```

Use write-mode commands for correction: `gofmt -w` and `goimports -w`.
Use `goimports -l` only to list files whose formatting/imports differ, and
`goimports -d` only to inspect the diff. These check modes do not replace the
correction baseline.

### When the user asks whether a Go check is mandatory

Separate repository policy from convention:

- Repository mandates come from CI, Makefiles, scripts, docs, task context, or
  the skill itself.
- Go conventions are expert guidance, not proof that the repository enforces a
  gate.
- Optional gates such as `golangci-lint`, race checks, coverage thresholds, or
  fuzzing are mandatory only when configured, requested, or documented.

### When Go code changes and no stronger gate exists

Use the conventional baseline:

1. Run `gofmt` on touched Go files, then `goimports` if available.
2. Run `go test ./...`.
3. Run `go vet ./...` when the module layout supports it.

### When the user writes or reviews Go doc comments

Write doc comments for rendered output, not just source readability.
`go doc` and pkg.go.dev apply formatting rules that can turn a comment into a
clean overview or a useless wall of text depending on spacing and indentation.

- Package docs must sit immediately above `package <name>` with no blank line
  between them, or they are not recognized as package documentation.
- Indented lines (tab or at least four spaces) render as code blocks; use them
  for examples.
- Lines starting with `-`, `*`, `+`, or a number render as list items;
  continuation lines must stay aligned or the rendered list breaks.
- Lines starting with `# ` render as headings; use them sparingly in package
  docs.
- Doc comments for exported identifiers should start with the identifier name
  (`// Foo does X`) so the comment follows standard Go documentation
  conventions.

Before treating Go documentation as done, run `go doc ./<package>` or
`go doc <package>.<Symbol>` and inspect the rendered output. Source text that
looks fine can still render as a run-on paragraph, broken list, or malformed
example block.

### When a Go program panics on nil or truncates a number

The skill has no "safety" page. Defensive correctness is a property of a
subject, not a subject of its own, so each trap is documented by the
reference that owns the thing it happens to:

| Symptom | Reference |
| --- | --- |
| `if err != nil` fires on success | [errors](../skills/go-expert/references/errors.md) |
| Panic on a nil receiver or a nil callback field | [structs-interfaces](../skills/go-expert/references/structs-interfaces.md) |
| Panic writing to a map; two slices corrupting each other | [data-structures](../skills/go-expert/references/data-structures.md) |
| A number wraps, a float comparison fails, a divide panics | [numbers](../skills/go-expert/references/numbers.md) |
| File handles accumulate until the function returns | [resources](../skills/go-expert/references/resources.md) |

The routing table in
[`skills/go-expert/SKILL.md`](../skills/go-expert/SKILL.md) is the only
index; there is no second one to keep in sync.

### When the user asks to make Go code faster

Refuse the shortcut: there is no optimization step before a measurement.
The chain is three references and it is read in order.

1. [benchmarks](../skills/go-expert/references/benchmarks.md) — write the
   benchmark that produces a number, run it with `-count` and compare with
   `benchstat`. One run is a sample of one.
2. [profiling](../skills/go-expert/references/profiling.md) — find where
   the time, the allocations, or the blocking actually are. A CPU profile
   that looks flat while the wall clock is long means waiting; read a
   trace.
3. [performance](../skills/go-expert/references/performance.md) — apply
   the pattern that matches the proven bottleneck, then measure again.

Rule out the boring answer first: a missing index, a call in a loop, or an
unconfigured HTTP transport dwarfs anything won by removing allocations.
Collector and toolchain knobs — `GOGC`, `GOMEMLIMIT`, `GOMAXPROCS`, PGO —
belong to [runtime](../skills/go-expert/references/runtime.md).

### When upstream publishes a new version of the Go skills

The comparison is pinned, not continuous. Re-evaluate only what changed,
and never silently re-import what was refused.

```bash
git -C <upstream-clone> fetch origin
git -C <upstream-clone> diff --stat \
  19a0626ae8565d27a7b7bdf59d8d99d94d7e284c..origin/main
```

Read that diff against the verdict already recorded below:

| The diff touches | Do |
| --- | --- |
| A skill in **Adapted** | Re-read only the changed sections, adapt or ignore, then update the row |
| A skill in **Refused** | Nothing, unless the change removes the conflict that caused the refusal. Record the re-check either way |
| A skill in **Not yet compared** | Nothing. It was never compared, so a diff against it means nothing |
| A skill **out of scope** | Nothing. The boundary does not move because upstream grew |
| A **new** skill | Triage it into one of the four tables |

Advance the pin in this document and in
`tests/test_go_expert_provenance.py` only once the verdicts are updated, in
the same change. A pin that moves ahead of its verdicts is worse than a
stale one, because it claims a comparison that never happened.

Three things force a re-check with no upstream release at all: a Go release
that changes version-sensitive guidance, a local reference that contradicts
a recorded verdict, and a refused rule arriving again by a different route.

## Package design

Go is package-first. Keep package names short, lowercase, and meaningful. Name
packages by the behavior or domain they provide, not by artificial layers.

Avoid grab-bag packages such as `util`, `common`, or `helpers` unless the
repository already uses that convention and the package has a clear boundary.
Do not split code into Java-style layers just to look architectural. Prefer a
small public API and keep unexported details inside the package that owns them.

The same reference covers how modules version: Minimal Version Selection,
`go.sum` as a tamper check, and Semantic Import Versioning, where a v2+
module carries `/vN` in its path, so moving to a new major is an explicit
import change that `go get -u` never makes for you.

## Error handling

Errors are part of the API contract. Return errors with enough context for the
caller to act, but do not spam redundant context at every layer.

- Wrap underlying errors with `%w` when callers may need `errors.Is` or
  `errors.As`.
- Use `errors.Is` and `errors.As` for error matching and extraction.
- Do not compare error strings.
- Use sentinel errors only when they are a deliberate part of the package
  contract.
- Prefer direct `if err != nil { return ... }` handling that preserves Line of
  Sight.

## Numeric conversion and precision

Go has no implicit numeric conversion, so every conversion is deliberate —
and every out-of-range conversion is a silent wraparound rather than an
error. Treat a conversion as a validation boundary and check range, sign,
unit, and precision there, once, rather than at every layer.

- Narrowing a variable the compiler cannot see wraps; guard against
  `math.MaxInt32` and friends before converting, or let
  `strconv.ParseInt(raw, 10, 32)` enforce the width at the boundary.
- Compare floats with a tolerance, never `==`, and keep money in integer
  minor units or a decimal type.
- Integer division by zero panics while float division yields `Inf` or
  `NaN`; guard a divisor that came from data.
- Put the unit in the type. `time.Duration(n) * time.Second` says n counted
  seconds; `time.Duration(n)` alone silently means nanoseconds.

## Line of Sight

The skill uses Mat Ryer's **Line of Sight** readability principle.

Definition: "a straight line along which an observer has unobstructed vision."

In Go, this means:

- Keep the happy path aligned to the left.
- Make a function easy to scan for expected flow.
- Handle errors and edge cases early with guard clauses or early returns.
- Keep error handlers and edge cases indented.
- Avoid deep nesting and unnecessary `else` blocks.
- Prefer the happy successful return as the last statement when possible.
- Flip conditionals to handle failure first.

Reference: Mat Ryer talk, https://www.youtube.com/watch?v=yeetIgNeIkc

- `04:18-06:02`: introduces Line of Sight and keeping the main flow visible.
- `06:05`: prefer the happy return as the final statement when possible.
- `06:20`: flip logic to handle failures first and avoid unnecessary `else`.

## Idiomatic Go, not Java

The skill should challenge Java-style ceremony in Go code:

- Avoid class terminology; Go has types, structs, and interfaces.
- Prefer concrete types and package-level functions when they are enough.
- Keep interfaces small and behavior-based.
- Define interfaces near consumers unless the repository has a clear boundary.
- Avoid `IThing`, `ThingInterface`, `AbstractThing`, and `BaseThing`.
- Treat generic `Manager` or `Service` suffixes as suspect unless they express
  real domain behavior.

## Standard library as design compass

When unsure, prefer standard-library patterns:

- `io` for small behavior interfaces.
- `net/http` for handler and middleware shape.
- `context` for cancellation and deadlines.
- `errors` for wrapping and matching.
- `testing` for table tests, benchmarks, and fuzzing conventions.
- `database/sql` for explicit boundaries and error handling.

## Concurrency and lifecycle

Concurrency must justify its complexity. Sequential code is the default; use
goroutines, channels, and synchronization only when the behavior needs parallel
I/O, cancellation, timeouts, fan-out, or explicit coordination.

Every goroutine needs an owner and an exit path. The code that starts it should
make clear how it finishes, how errors are observed, and how cancellation is
propagated.

Use the simplest primitive that matches the behavior:

- Channels transfer values, ownership, or completion signals.
- `sync.Mutex` protects small shared state when clearer than a channel.
- `sync.WaitGroup` waits for fan-out work.
- `sync.Once` handles one-time initialization.

Use `context.Context` for cancellation, deadlines, and request-scoped values.
For functions that accept context, it should be the first parameter after the
receiver. Prefer passing context explicitly to each operation that needs it. Do
not store `context.Context` in long-lived or reusable structs because it obscures
lifetime, prevents per-call cancellation/deadlines, and intermingles scopes.

Storing context is acceptable only when the struct is operation-scoped, not
reused, and its lifetime is clearly tied to the context lifetime, or when
preserving API compatibility requires it. Rare compatibility retrofits include
cases such as `net/http.Request`; prefer Context-suffixed methods when
practical. When in doubt, pass context as an argument.

For external commands, prefer `exec.CommandContext(ctx, ...)` when the command
must respect cancellation or timeout. When creating a timeout with
`context.WithTimeout`, call the returned cancel function, usually with
`defer cancel()`.

For Go versions before 1.23, unreferenced timers created by `time.After` were
not garbage collected until they fired. In modern Go, prefer lifecycle clarity:
use `context.WithTimeout` for cancellation/deadlines, and use `time.NewTimer`
or `time.Ticker` with explicit `Stop()` when timer control matters.

Use a buffered channel as a simple semaphore when limiting concurrency is enough:

```go
sem := make(chan struct{}, 4)

var wg sync.WaitGroup
for _, job := range jobs {
	sem <- struct{}{}
	wg.Add(1)

	go func() {
		defer wg.Done()
		defer func() { <-sem }()

		run(ctx, job)
	}()
}

wg.Wait()
```

For Go versions before 1.22, shadow the loop variable inside the loop
(`job := job`) before starting the goroutine to avoid closure-capture bugs.

When concurrent code changes, `go test -race ./...` is a conventional baseline
check if the module supports it. Treat it as a project mandate only when the
repository configures or documents it.

## Runtime and GC diagnostics

Do not blame application logic for CPU or latency changes after a Go upgrade
without checking runtime changes first. Compare Go version, `GOEXPERIMENT`,
architecture, allocation profile, runtime metrics, and `pprof` data.

Green Tea GC was introduced as an experiment in Go 1.25 with
`GOEXPERIMENT=greenteagc` and became the default garbage collector in Go 1.26.
Go 1.26 still allows opting out at build time with
`GOEXPERIMENT=nogreenteagc`, but the Go 1.26 release notes state this opt-out is
expected to be removed in Go 1.27.

Green Tea can reduce GC overhead for allocation-heavy workloads, especially
small-object workloads, but some workloads may not benefit or may regress. If a
CPU increase appears after moving to Go 1.26 or enabling Green Tea, compare with
and without `GOEXPERIMENT=nogreenteagc` while that opt-out exists, then validate
with `runtime/metrics`, `GODEBUG=gctrace=1`, and CPU/heap profiles before
changing application code.

References:
- https://go.dev/blog/greenteagc
- https://go.dev/doc/go1.26#runtime

## Logging and output

Follow the repository-local output and logging convention. Do not introduce
`log`, `slog`, `fmt`, or a new logger abstraction as a cosmetic preference.

If the project defines a logging interface or output contract, program against
that contract and keep concrete logger implementations swappable.

For simple CLI output, stdout/stderr writes may be enough. For services or
observability-heavy code, structured logging may be required by the repository.
Read the local pattern first.

## Testing and mocks

Prefer designing testable code over adding mocks. Use small interfaces, explicit
dependencies, and simple seams so behavior can be tested without a mocking
framework whenever possible.

Do not force an interface solely because code shells out to an external process.
Direct shell-out can be tested through controlled external-process resources:
temporary filesystem fixtures, environment variables, PATH shims or fake
executables, local URLs or `httptest.Server`, captured stdout/stderr, and
controlled exit codes.

Choose the least artificial reliable boundary for the behavior under test.
Extract a seam or interface when shell-out logic becomes complex, expensive,
unsafe, hard to reproduce, or has multiple real consumers; do not extract one
for architectural purity alone.

When a mock is necessary, prefer a function-field mock struct pattern:

- Define a struct with function fields matching the interface methods.
- Implement each method by calling the corresponding function field.
- Customize return values, errors, and argument capture per test.
- Do not implement behavior the test does not care about.
- Treat a nil panic from an unexpected method call as useful signal that the
  code did something the test did not anticipate.

## Generated code

Do not edit generated Go files manually when they contain a marker such as
`// Code generated ... DO NOT EDIT.` Change the generator, template, schema, or
source input instead, then regenerate. If a generated file lacks a standard
marker, inspect repository conventions before editing.

## Upstream parity de-para

This skill was compared against [`samber/cc-skills-golang`][upstream], a
46-skill Go catalogue, pinned at commit `19a0626a` for the whole comparison.
The upstream tree is reference material only: nothing in it is executed, and
every import is an adaptation rather than a copy, because upstream states
universal `MUST` and `ALWAYS` rules that conflict with this skill's
project-aware posture.

Precedence when the two disagree: repository mandates first, then this
project's Go policy, then adapted upstream guidance.

The table below is the record of what was taken, what was reshaped on the
way in, and what was refused — kept so a future re-evaluation starts from
the decisions instead of repeating the analysis. Local content is
authoritative throughout; upstream is fitted to it, never the reverse.

### Provenance

| Field | Value |
| --- | --- |
| Upstream | [`samber/cc-skills-golang`](https://github.com/samber/cc-skills-golang) |
| Reviewed at | `19a0626ae8565d27a7b7bdf59d8d99d94d7e284c`, dated 2026-09-07 |
| Reviewed on | 2026-09-20 |
| Licence | MIT, Copyright (c) 2026 Samuel Berthe |

Upstream asks to be cited through its own `CITATION.cff`:

> Berthe, Samuel. *samber/cc-skills-golang: AI Agent Skills for
> production-ready Go projects.*
> DOI [10.5281/zenodo.21605229](https://doi.org/10.5281/zenodo.21605229).

Nothing below is a copy. Every adapted item was rewritten to fit this
skill's project-aware posture, and the tables record which conflict forced
each change. The attribution stands regardless, because the analysis that
found the gaps started from upstream's enumeration of the subject.

### Adapted

| Upstream skill | Local destination | Shape of the adaptation |
| --- | --- | --- |
| `golang-structs-interfaces` | `references/structs-interfaces.md` | New reference. The earlier restructure deliberately did not create it — local content was thin, and an almost-empty file is structure by prediction. The imported material is what justified it. |
| `golang-data-structures` | `references/data-structures.md` | New reference for a confirmed gap: preallocation, capacity growth, the `slices` and `maps` packages, string building, `container/`. |
| `golang-safety` | dissolved into five references | No safety page. Safety is a property of a subject, not a subject of its own: the typed-nil return went to `errors`, nil receivers and nil callback fields to `structs-interfaces`, nil collections and `append` aliasing to `data-structures`, `defer` in a loop to `resources`, and the numeric cluster to the new `numbers`. |
| `golang-code-style` | `code-style.md`, `packages.md`, `data-structures.md` | Only the rules a formatter cannot decide. `gofmt` already owns everything mechanical. |
| `golang-benchmark` | `references/benchmarks.md`, `references/profiling.md` | Split by question rather than by upstream file. Benchmarks own producing a number to compare; profiling owns finding where it is spent. A second pass read `pprof.md` in depth for interpretation rather than surface: flat against cum, runtime frames as symptoms, the heap pair read together and diffed with `-base`, labels, and the goroutine leak views, including the `goroutineleak` profile upstream does not cover. The flag catalogue, export formats and symbolization options stay with `go tool pprof -h`, which owns them and cannot drift. `trace.md` got the same reading: goroutine states as the diagnosis, `-pprof=sched` and its siblings, `runtime/trace` annotations, and the Go 1.25 flight recorder. The viewer's colours and keyboard shortcuts were refused as interface detail that changes between releases, and the rule to wrap every request in a task was softened to annotating where a latency question is open. |
| `golang-performance` | `references/performance.md`, `runtime.md` | Patterns enter conditioned on a measurement, never as defaults. Collector and toolchain knobs went to runtime, which already owned that subject. A second pass read `cpu.md` and `memory.md` in full and took the pointer-in-the-pool rule, the trailing zero-size field, contiguous matrices and index trees, false sharing, conversion and reflection costs, and substring retention; the pool allocation and the padding were measured on Go 1.27, not taken on trust. Upstream dates `strings.Clone` to Go 1.20; the toolchain's API file says 1.18. |
| `golang-troubleshooting` | dissolved into six references | Its `common-go-bugs.md` is a catalogue defined by a property, and roughly sixty percent was already owned after the previous slice. The residue went to its owners: shadowing and the `break`/`fallthrough` traps to code-style, `os.Exit` and JSON decoding to resources, closed-channel semantics and `recover`'s scope to concurrency, bytes versus runes to data-structures, `time.Time` comparison to values, and the `iota` zero value to structs-interfaces. |
| `golang-security` | `references/security.md` | Only the language surface. Of twelve upstream references, seven — threat modelling, checklist, secrets, third-party, architecture, cookies, logging — are repository concerns owned by `security-expert`. The five that are Go got imported as a risk-to-stdlib-answer table plus the path, injection, crypto and transport specifics. A second pass read those five reference files in full rather than their hub summary, and took identifiers that placeholders cannot bind, SSRF checked at dial time, the length `ConstantTimeCompare` leaks, password KDFs, archive extraction, `os.Root`'s documented limits, and the resource limits a server needs. The items refused on that pass are in the table below. |
| `golang-project-layout`, `golang-dependency-management`, `golang-gopls` | `references/packages.md` | Dissolved into the reference that owns package and module boundaries: `internal/` as the only compiler-enforced boundary, `go.work`, Minimal Version Selection, `go.sum` as a tamper check, and the one thing `gopls` rename does that grep cannot. |
| `golang-database` | `references/resources.md` | Only the three `database/sql` edges that are the language's: `rows.Err()` after the loop, the deferred `Rollback` after `Begin`, and NULL not being the zero value. Isolation levels and row locking are the database's domain. |
| `golang-naming` | `references/naming.md` | The local file was 1.4 KB of Java-shaped anti-patterns and carried none of the conventions a reviewer cites. Two upstream rules were softened as non-canonical: boolean fields need no `is`/`has` prefix, and sentinel error strings need no package prefix. |
| `golang-error-handling` | `references/errors.md` | Three unwritten decisions: the unexplained `_`, `%w` as an API commitment versus `%v` at a boundary, and `errors.Join` for failures that are parallel rather than chained. |
| `golang-context` | `references/context.md` | The three mistakes that reach production: a `Background` created mid-chain, a string value key, and work that must outlive the request. |
| `golang-concurrency` | `references/concurrency.md` | The local file named the primitives; the import added what bites with each, and recorded that the standard library has no group-with-errors primitive. |
| `golang-testing` | `references/testing.md` | Independence, `t.Parallel` against `t.Setenv`, build tags, `testing/synctest`, and the `Fuzz` and `Example` forms. |
| `golang-documentation` | `references/documentation.md` | Only the language-level part. README, CONTRIBUTING and changelog are repository concerns governed by the Documentation Mandate, and the reference now says so. |
| `golang-design-patterns` | dissolved | Rejected as a category: it mixes three altitudes and is the most connected node in the upstream graph, which is the signature of a grab bag. Only its `architecture.md` survived, into `packages.md`. |

### Refused, with the reason

| Upstream material | Reason |
| --- | --- |
| `clean-architecture.md`, `hexagonal-architecture.md`, `ddd.md` | Named architectures are team choices with real trade-offs, not Go defaults. Adopting one is a project decision, not a style correction. |
| 12-factor guidance inside `architecture.md` | An operations concern, not a Go language concern. |
| "Functions should be short and focused — one function, one job" | Contradicts the local principle that function scope is contract, not size. Extracting until nothing is left to extract is a gradient with no floor, and in Go it costs Line of Sight. |
| "Slices and maps MUST be initialized explicitly, never nil" | True for maps, wrong for slices, and the two are bundled under one rule. A nil slice appends correctly and is the idiomatic accumulator. The real concern is the `null` versus `[]` wire contract, which belongs at the serialization boundary, not the declaration site. The canonical Go guidance prefers the nil slice and treats JSON as a limited exception. |
| The debugging methodology golden rules: read the error, reproduce before fixing, one hypothesis at a time, root cause over workaround | Generic engineering discipline, not Go expertise, and already mandated by the Test-First section of `AGENTS.md`. Restating it in a language skill buys tokens on every load and changes nothing. |
| `golang-dependency-injection` as a category | Three of its four references are library-specific (`google-wire`, `uber-dig`/`uber-fx`, `samber/do`) and fall under the library boundary below. The residue, manual constructor injection, is not a Go technique — it is passing arguments to a constructor, and explicit dependencies are already owned by [packages](../skills/go-expert/references/packages.md) and [testing](../skills/go-expert/references/testing.md). A container is an abstraction that has not earned its existence. |
| `golang-how-to` as a router | Its job is done locally by the routing table in `SKILL.md`. Upstream's is an always-triggering description plus a thirty-row prose table executed by the model, costing about 4k tokens of recurring body per Go task, with no evals. |
| `golang-lint` and `golang-modernize` as references | Both are already the local pattern rather than a page: linters appear as a **Diagnose:** line inside the reference that owns the subject, and version-sensitive idiom is carried per reference with the `go` directive rule in `runtime.md`. A separate page would duplicate and drift. |
| `golang-refactoring` as a category | Process rather than language — a coverage safety net and behavior-preserving discipline that belong to review and version control. Its one Go-specific fact, the `gopls` rename, was imported instead. |
| SIMD and CPU-specific instruction-set dispatch | Architecture and assembly territory rather than Go. |
| A third-party collection dependency for filter and group-by | The skill is standard-library-oriented; a library choice belongs to the project that makes it. |
| Sub-agent fan-out for style review | Cascading activation is forbidden by the Horizontal Skill Architecture mandate in `AGENTS.md`. |
| XXE hardening for `encoding/xml` (`golang-security` `network.md`) | Wrong for Go. `encoding/xml` imports no network or file I/O and hands a `DOCTYPE` back as a `Directive` token, so there is no external entity to resolve and the string scan it recommends guards nothing. |
| An `unsafe` overlap check before `copy` (`memory-safety.md`) | The builtin is specified to handle overlapping slices. The check adds `unsafe` to solve a problem that does not exist. |
| SSRF prevented by checking the URL's host name (`injection.md`) | Loses to a name that resolves to an internal address. The dial-time check in the `net.Dialer` was imported instead. |
| "Never bind to `0.0.0.0`" (`network.md`) | A deployment decision: a server in a container has to. The language concern, `net/http/pprof` on the public mux, was already owned by profiling. |
| "Prefer `sqlx` or `pgx` over `database/sql`" (`injection.md`) | A library choice, outside the standard-library boundary. The Go fact underneath, that placeholders bind values and never identifiers, was imported. |
| `//go:noinline` calls as preemption points in tight loops (`cpu.md`) | Obsolete. Asynchronous preemption interrupts a call-free loop; measured on Go 1.27, the loop was preempted on time and only hung with `GODEBUG=asyncpreemptoff=1`. |
| Value receivers "enable inlining" with an unmeasured 80% gain (`cpu.md`) | A number with no benchmark behind it, and it cuts against the receiver-consistency rule in `structs-interfaces.md`. |
| "Don't pool objects over 32 KB" and "direct indexing avoids bounds checks" (`memory.md`) | Stated as mechanism without evidence, and the second is wrong as stated: indexing is bounds-checked too, unless the compiler proves it away. |
| Multi-accumulator loops, row-major traversal, struct-of-arrays (`cpu.md`) | CPU architecture rather than Go, the same boundary that kept SIMD out. The Go-specific residue, `[][]T` with one allocation per row, was imported. |

### Not yet compared in depth

Nothing. Every upstream skill at the recorded pin carries a verdict in
one of the tables on this page, and a test asserts it.

That is a statement about coverage, not about agreement: a verdict of
refused or out of scope is as deliberate as an import, and the reason is
recorded beside it so a later reader does not reopen a closed question by
accident.

### Out of scope by boundary

`golang-observability` is out for a different reason than the library
catalogues: it is infrastructure. Prometheus, OpenTelemetry, Grafana,
Pyroscope, server-side RUM and consent-driven tracking are operational
choices a project makes and documents, the same ruling that kept 12-factor
out of package design. `logging.md` deliberately states that there is no
house logger and that the repository's existing choice wins, so importing
advocacy for one would contradict standing policy. A test asserts the
vendor names stay absent from the skill.

This skill is the Go language engine. Library and framework catalogues
stay out regardless of their quality. A project that adopts one of these
documents it in its own repository, not in the language expert.

| Group | Upstream skills |
| --- | --- |
| The `samber` family | `golang-samber-lo`, `golang-samber-mo`, `golang-samber-ro`, `golang-samber-do`, `golang-samber-hot`, `golang-samber-oops`, `golang-samber-slog` |
| CLI and configuration | `golang-spf13-cobra`, `golang-spf13-viper` |
| Assertions | `golang-stretchr-testify` |
| DI containers | `golang-google-wire`, `golang-uber-dig`, `golang-uber-fx` |
| Protocols and schemas | `golang-grpc`, `golang-graphql`, `golang-swagger` |
| Surveys | `golang-popular-libraries` |
| Application shape | `golang-cli` |
| Pipelines | `golang-continuous-integration` |
| Lookup tooling | `golang-pkg-go-dev` |
| Link lists | `golang-stay-updated` |

They are named rather than described as a family, so the boundary can be
checked by a test instead of read and trusted.

[upstream]: https://github.com/samber/cc-skills-golang

## Planned distribution

Not implemented. This records the intended shape so cross-references and
skill boundaries are designed against it now instead of being retrofitted.

Each skill becomes its own repository under the `jacazul-ai` organization,
this one as `jacazul-ai/go-expert-skill`. Every skill repository carries its
own hatch, following the pattern established by `jacazul-ai/jaflow`: the
hatch is consumed as an embedded library rather than an installed
component, so a consumer gets the skill without gaining a second binary to
install, version, and keep on `PATH`.

Two consumption paths are supported, and both resolve to the same source:

- from this project, for anyone already running `jacazul-ai-cli`;
- directly through the `jacazul` CLI, for anyone who wants the skill alone.

### Consequence for cross-references

One repository per skill supplies the `owner/repo` namespace that atomic
leaves need to reference each other unambiguously. Leaf references use the
upstream identifier convention — `owner/repo@skill`, written in backticks
as a citation, never as a bare `@` mention, which some harnesses read as a
force-load directive that pulls the whole referenced skill into context.

For this skill the form is `jacazul-ai/go-expert-skill@<leaf>`.

---

**Version:** 0.1.0
**Last Updated:** 2026-09-20
