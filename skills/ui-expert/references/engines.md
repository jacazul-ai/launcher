# Engine Coverage

A result covers the engine it ran on. Chromium-based browsers share Blink;
Safari runs WebKit; Firefox runs Gecko. Automation servers built on the
Chrome DevTools Protocol drive Blink only.

## Say it in the finding

Every finding and every pass names the engine and its version, and lists
what stays unverified:

```text
PASS on Chromium 141 (Blink). Not verified on WebKit or Gecko.
```

## Where engines are known to differ

| Area | Difference |
| --- | --- |
| Customized built-in elements (`<button is="x-button">`) | Blink and Gecko support them; WebKit does not, so the element stays a plain built-in there. Never let a Blink pass vouch for them. |
| `display: contents` | Engines have historically dropped the element's role and name from the accessibility tree; check the accessibility tree per engine when a semantic element uses it. |
| Newer CSS (`:has()`, container queries, anchor positioning, `@scope`) | Support arrived at different releases per engine; check the project's browser baseline before relying on a Blink result. |

## When a second engine is required

When the project's supported browsers include Safari or Firefox and the
change touches one of the areas above, the result needs a run on that
engine, by the project's own cross-browser setup or by the operator
through the [manual fallback](manual-fallback.md). Until then, report the
gap instead of a pass.
