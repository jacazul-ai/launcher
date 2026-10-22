# Custom Elements Between Combinators

A worked example of a failure a DOM runner cannot fully see. CSS
frameworks tie elements together with combinators: `.list > .item`,
`.item + .item::before`, `.group > .btn:not(:last-child)`. A custom
element host inserted between those elements changes who is whose child
and sibling, and the rules stop matching.

## The shape

```html
<!-- intended -->
<ol class="crumbs">
  <li class="item">Home</li>
  <li class="item">Docs</li>
</ol>

<!-- rendered by components -->
<ol class="crumbs">
  <x-crumb><li class="item">Home</li></x-crumb>
  <x-crumb><li class="item">Docs</li></x-crumb>
</ol>
```

Each `.item` is now the only child of its own host. `.item + .item`
matches nothing, so the divider disappears; `.crumbs > .item` matches
nothing, so the flex layout on `.crumbs` lays out the hosts, not the
items.

Tables add a parser trap: an unknown element written directly inside
`<table>` or `<tr>` in HTML source is moved out of the table by foster
parenting before any script runs.

## The checks

| Check | Where | Assertion |
| --- | --- | --- |
| Siblings still match | DOM runner | `items[1].matches('.item + .item')` is `true` |
| Divider renders | Real browser | `getComputedStyle(items[1], '::before').content` is not `none` |
| Items are flex items | Real browser | `getComputedStyle(items[0].parentElement).display` is `flex` |
| Joined button corners | Real browser | inner buttons report `0px` radius on the joined sides |
| Custom element kept in the table | DOM runner | after parsing, the element's `closest('table')` is not `null` |

## Fixes to weigh

The component renders without a wrapping host (light DOM content placed
directly), the host takes the framework class and role itself, the host
uses `display: contents` (then check the accessibility tree per
[engines](engines.md)), or the styles are rewritten against the hosts.
The choice belongs to the component's design; the checks above prove
whichever one is chosen.
