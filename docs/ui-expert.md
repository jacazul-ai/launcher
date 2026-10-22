# UI Expert Skill

Guide for the ui-expert skill: verifying UI in a real browser with
assertions a machine can repeat, and running browser automation without
risking the operator's machine. The same scheme works in every harness:
the shell, the project's scripts and an open browser MCP server.

The skill lives in [`skills/ui-expert/`](../skills/ui-expert/SKILL.md). It
does not cover visual design, UX, or writing the JavaScript, TypeScript or
Web Components themselves; that stays with
[js-ts-expert](js-ts-expert.md).

## Trigger → Action

### When you want an agent to check a page in a browser

Give it a browser MCP server that launches its own browser. Never point
the server at the browser you work in, and never start that browser with
`--remote-debugging-port`. For chrome-devtools-mcp (version and path are
examples; pick the pin yourself):

```bash
npx -y chrome-devtools-mcp@<pinned> \
  --executablePath <dedicated-chromium> \
  --isolated --headless --no-usage-statistics --no-performance-crux
```

Set `CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS=1` in the server's environment.
Every required flag, the forbidden attach flags and their aliases are in
[browser-safety](../skills/ui-expert/references/browser-safety.md).

### When you pick the server version

Look up the release dates (`npm view chrome-devtools-mcp time --json`),
take the newest release at least 7 days old, and write that exact version
into the command. Never `@latest`.

### When you want to know what browser automation is running

Run `jacazul ui doctor`. It lists every chrome-devtools-mcp server with its
parent and age, flags orphans left by finished sessions, attach mode,
unpinned versions, missing launch flags and telemetry watchdogs, and
reports open remote-debugging ports and whether a dedicated Chromium is
installed. It works on Linux, macOS and Windows.

| Exit | Meaning |
|---|---|
| 0 | Nothing needs you |
| 1 | Something needs you; the report says what |
| 2 | The doctor could not look, or the command was wrong |

It never kills or changes anything. It prints the commands (`kill <pid>`,
or `Stop-Process -Id <pid>` on Windows); run them after you check each
one, then fix the configuration that started the process. On Windows it
needs an elevated shell to see other users' command lines. It cannot read
another process's environment, so the update-check variable stays a
configuration check. Without the launcher, the skill lists the same audit
as plain commands per system.

### When a change claims to fix how something looks

Expect computed values, not a screenshot: `getComputedStyle` for styles
and pseudo-elements, `getBoundingClientRect` for layout, the accessibility
snapshot for role and name, and an empty console. The agent prints one
`PASS` or `FAIL` line per check; a screenshot only goes along with them.

### When a DOM test (jsdom, happy-dom) covers the UI

Keep DOM facts there: tree shape, parser fix-ups, `matches()` for
selectors. Layout, pseudo-elements and the accessibility tree need a real
browser; a jsdom assertion on them proves nothing.

### When no browser server is configured

The agent hands you the page URL and a console snippet. Paste it into the
browser's developer console and send back the printed lines, with the
browser name and version.

### When Safari or Firefox matter

A Chromium pass does not cover WebKit or Gecko. Results name the engine
they ran on and what stays unverified, notably customized built-in
elements (`is=`), which WebKit does not support.

### When you review a browser server configuration

Use the scenarios in
[`skills/ui-expert/CODE-REVIEW.md`](../skills/ui-expert/CODE-REVIEW.md) on
the shared [code-review scale](../skills/code-review/SKILL.md). An
attached, floating-version server is a `BLOCKER`.

## Measurement

The eval record is in [Skill Evals](skill-evals.md#current-record-ui-expert).
It measures Claude Code only; the skill text is the same in every harness.

---

**Last Updated:** 2026-10-21
