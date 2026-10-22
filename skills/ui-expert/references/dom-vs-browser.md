# DOM Runner vs Real Browser

Put each check where it can be computed. A DOM runner (jsdom, happy-dom)
parses HTML and runs selectors; it has no layout engine and no renderer.
A real browser computes everything, at the cost of a slower, heavier run.

## What each one can prove

| Fact | DOM runner | Real browser |
| --- | --- | --- |
| Element tree after parsing, including parser fix-ups such as table foster parenting | ✅ | ✅ |
| Attributes, text, custom element upgrade and lifecycle callbacks | ✅ | ✅ |
| Selector matching: `el.matches('.a + .a')`, `querySelectorAll` | ✅ | ✅ |
| Events dispatched by the test | ✅ | ✅ |
| Cascade result: which declaration wins, inherited values | ⚠️ partial, no layout-dependent values | ✅ |
| Pseudo-element content and style (`::before`, `::after`, `::marker`) | ❌ not rendered | ✅ |
| Layout: box size and position, flex and grid placement, overflow | ❌ every box is zero | ✅ |
| Media queries, viewport units, container queries | ❌ | ✅ |
| Accessibility tree: computed role and name | ❌ | ✅ |
| Console errors from the page's own scripts and resources | ⚠️ only what the runner executes | ✅ |
| Rendering differences between engines | ❌ | ✅ per engine run |

## Default

Prove DOM facts in the DOM runner: they are fast, run in the project's
unit suite and fail close to the cause. Move a check to the real browser
only when the table says the runner cannot compute it.

A DOM-runner test that asserts layout or a pseudo-element passes or fails
for the wrong reason: the runner returns zero boxes and empty pseudo
content whether the CSS is right or not. Treat such a test as no evidence.

## Splitting one claim

Most UI claims have a DOM half and a rendering half. "The breadcrumb shows
a divider between items" splits into:

1. DOM runner: the items are siblings, and `.item + .item` matches the
   second one.
2. Real browser: `getComputedStyle(second, '::before').content` is the
   divider, not `none`.

The first half catches a broken tree in milliseconds; the second proves
the user sees the divider.
