# Objective Assertions

Every visual claim becomes a value read from the engine and compared with
an expected value. The same expressions work through a browser MCP
server's script tool and in the manual console snippet.

## Assertion shapes

| Claim | Read | Pass when |
| --- | --- | --- |
| A pseudo-element renders | `getComputedStyle(el, '::before').content` | not `none` or `normal`; equals the expected string when it matters |
| A style applies | `getComputedStyle(el).<property>` | equals the expected computed value (`rgb(...)`, `px`) |
| Corners are joined | `getComputedStyle(el).borderTopRightRadius` (and siblings) | `0px` on the joined side |
| An element is a flex or grid item | `getComputedStyle(el.parentElement).display` | `flex` / `grid` on the parent that actually contains it |
| Layout | `el.getBoundingClientRect()` | width and height above zero; positions in the expected order |
| Visible | `el.checkVisibility()` | `true` |
| Accessible name and role | the server's accessibility snapshot, or the browser's accessibility panel | the role and name the component promises |
| Clean console | the server's console messages tool, or the console panel | zero errors after load and after the interaction |

Compare computed values, not authored ones: the engine reports `rgb()`
for colors and `px` for lengths, whatever the stylesheet wrote.

## One line per check

Each check prints one line that a human or a script can read:

```text
PASS breadcrumb divider: ::before content is "/"
FAIL button group joined corners: border-top-right-radius is 6px, want 0px
```

The line names the check, the value read and, on failure, the value
wanted. A run is green only when every line is `PASS`.

## Screenshots

Take one after the assertions, as supporting evidence for a human. Never
let a screenshot replace an assertion: a model reading pixels misses a
1px border, a wrong shade and a divider rendered in the wrong place.

## Interaction checks

Assert the state before and after: focus moved (`document.activeElement`),
the attribute changed (`aria-expanded`), the box appeared. Wait on a
condition, never on a fixed delay.
