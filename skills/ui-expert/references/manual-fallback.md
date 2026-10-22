# Manual Fallback

When no browser MCP server is configured, the operator runs the check.
Hand over two things: the URL of the page and a snippet to paste into the
browser's developer console. Do not reach for a harness-specific browser
or page tool instead; the fallback is the same in every harness.

## The snippet

Self-contained, read-only, one line per check, a summary at the end:

```js
(() => {
  const checks = [
    ['crumb divider renders', () => {
      const item = document.querySelectorAll('.crumb')[1];
      const content = getComputedStyle(item, '::before').content;
      return [content !== 'none' && content !== 'normal', content];
    }],
    ['crumbs are flex items', () => {
      const item = document.querySelector('.crumb');
      const display = getComputedStyle(item.parentElement).display;
      return [display === 'flex', display];
    }],
  ];
  let failed = 0;
  for (const [name, check] of checks) {
    let ok = false;
    let value;
    try {
      [ok, value] = check();
    } catch (error) {
      value = error.message;
    }
    if (!ok) failed++;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${name}: ${value}`);
  }
  console.log(failed ? `${failed} check(s) failed` : 'all checks passed');
})();
```

A check that throws reports `FAIL` with the error, so a missing element
reads as a failure instead of stopping the run.

## What to ask back

Ask the operator for the printed lines, the browser and its version. The
browser decides which engine the result covers (see
[engines](engines.md)).
