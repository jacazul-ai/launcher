# UI Verification Review Directives

Review scenarios for UI verification and browser automation setup: the
shape to avoid, what can fail, and the evidence or correction a reviewer
should require.

The review method, scenario format, tracks, areas, technical levels,
advisories and evidence labels are owned by the shared
[Code Review skill](../code-review/SKILL.md). This file adds UI scenarios
only and never redefines those labels.

## Worked example (full form)

```json
{
  "mcpServers": {
    "browser": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest",
               "--wsEndpoint=ws://127.0.0.1:9222/devtools/browser"]
    }
  }
}
```

**Avoid:** a browser server that attaches to a running browser through
its remote-debugging port, at a floating version.

**Context:** the operator started their daily browser with
`--remote-debugging-port=9222` so the agent could see their pages.

**Runtime sequence:** every session spawns a server that connects to the
operator's browser. Tool calls act on real tabs with real cookies. The
harness does not stop the server when the session ends, so each session
leaves one more process behind, each with its telemetry child. `@latest`
pulls whatever was published last.

**Failure modes:** a page-listing or navigation call hangs or crashes the
operator's working browser; any local process can drive the open
debugging port; leftover servers accumulate; a bad release reaches the
machine the day it ships.

**Review directive:** require launch mode with a dedicated binary and the
full launch flag set from
[browser-safety](references/browser-safety.md), an exact pin at least
7 days old, and no browser started with a debugging port.

**Acceptable correction:** replace the arguments with the reference
command shape, close the debugging port, and have the operator remove the
leftover processes after confirming them.

**Classification:** `BLOCKER` / `FIX-NOW` / `SECURITY`, `LIFECYCLE` /
`TRACE`.

## Foundations: evidence

### 1. Screenshot as the only proof

**Problem:** a UI change is declared correct because a screenshot "looks
right".

**What can happen:** a 1px border, a wrong shade, a missing divider or a
shifted box passes; nobody can rerun the judgment.

**Safer shape:** computed-value assertions from
[assertions](references/assertions.md), one `PASS`/`FAIL` line each; the
screenshot accompanies them.

**Classification:** `WARNING` / `FIX-OR-TECH-DEBT` / `TEST`.

### 2. Layout or pseudo-elements asserted in a DOM runner

**Problem:** a jsdom or happy-dom test asserts `::before` content, a
bounding box or a flex placement.

**What can happen:** the runner returns empty pseudo content and zero
boxes whatever the CSS says, so the test is green or red for a reason
unrelated to the change.

**Safer shape:** split the claim per
[dom-vs-browser](references/dom-vs-browser.md): DOM facts stay in the
runner, rendering facts move to a real browser.

**Classification:** `WARNING` / `FIX-NOW` / `TEST`.

### 3. A pass with no engine named

**Problem:** "verified in the browser" with no engine or version, on a
change that touches customized built-ins, `display: contents` or recent
CSS.

**What can happen:** a Blink-only pass ships a component that does not
upgrade on WebKit or loses its accessible name.

**Safer shape:** name the engine and what stays unverified, per
[engines](references/engines.md).

**Classification:** `SUGGESTION` / `FIX-OR-TECH-DEBT` / `TEST`.

## Boundaries: browser lifecycle

### 4. Persistent or real profile

**Problem:** the server runs without `--isolated`, or `--userDataDir`
points at the operator's profile.

**What can happen:** state leaks between runs, the profile grows without
bound, or automation reads and changes the operator's logged-in sessions.

**Safer shape:** `--isolated`, and no `--userDataDir` unless it names a
directory created for automation.

**Classification:** `WARNING` / `FIX-NOW` / `SECURITY`, `LIFECYCLE`.

### 5. Process cleanup without consent

**Problem:** a script or agent kills browser or server processes it found
by name.

**What can happen:** it closes the operator's daily browser or another
session's server, losing work.

**Safer shape:** report the processes and print the command; run it only
after the operator confirms.

**Classification:** `WARNING` / `FIX-NOW` / `LIFECYCLE`.

### 6. Headed browser in an unattended run

**Problem:** the server launches without `--headless` for a scripted or
agent-driven check.

**What can happen:** windows steal focus and the operator's input lands
in the automated page.

**Safer shape:** `--headless`; a headed run only when the operator asks to
watch.

**Classification:** `SUGGESTION` / `FIX-OR-TECH-DEBT` / `LIFECYCLE`.

## Systems: supply chain and data egress

### 7. Floating or fresh server version

**Problem:** `@latest`, no version at all, or a release younger than
7 days.

**What can happen:** the tool changes under the agent between runs; a
compromised or broken release reaches the machine before anyone pulls it.

**Safer shape:** an exact pin chosen per
[browser-safety](references/browser-safety.md#picking-the-pin).

**Classification:** `WARNING` / `FIX-NOW` / `SECURITY`.

### 8. Telemetry and field-data lookups left on

**Problem:** the launch lacks `--no-usage-statistics` or
`--no-performance-crux`, or update checks stay enabled.

**What can happen:** usage data and the URLs of pages under test (often
internal or unreleased) leave the machine.

**Safer shape:** the full launch flag set and environment from the server
table.

**Classification:** `WARNING` / `FIX-NOW` / `SECURITY`.

### 9. Harness-specific browser tool

**Problem:** verification goes through a browser or page tool that only
one harness provides.

**What can happen:** the check cannot be repeated by another agent, in
another harness or in CI, and the project's evidence depends on one
vendor.

**Safer shape:** an open browser MCP server under the same rules, or the
[manual fallback](references/manual-fallback.md).

**Classification:** `WARNING` / `FIX-OR-TECH-DEBT` / `POLICY`.
