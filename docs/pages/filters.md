---
title: Filters
description: The code a site runs, named in its parasite.toml.
---

A site lists the filters it may use in `[filters.NAME]`, in the order they run. A filter
is a Python function taking and returning a panflute document, named as an importable
`module:function`: code comes from packages you installed, never from a path in the
site.

```toml
[filters.pannb]
python = "pannb:main"
inputs = ["ipynb"]
default = true

[filters.pantable]
python = "pantable.cli.pantable:main"
default = true
```

| key | meaning |
|---|---|
| `python` | the function |
| `at` | `"read"` (the default): after reading, for every output; `"render"`: for the outputs whose profile names it in its `filters` |
| `inputs` | a read filter for these input formats only (extensions without the dot) |
| `default` | a read filter runs on every document |

parasite's own: `lightgallery-from-dir` (read: a gallery from a folder of photos),
`lightgallery` and `mathjax-bold-ell` (render: MathJax has no bold ℓ, so
`\mathbf{\ell}` is written `\pmb{\ell}` in HTML).

pandoc's own filters (Lua, JSON filters such as pandoc-crossref, citeproc) are pandoc
options: put them in `[read] options`.

Planned: a document opting in to a site's filter by name (`filters: [texp]`, Quarto's
key), and Lua and WebAssembly filters in the allow-list.

# From other tools

Each has its own key for a document's filters; parasite reads none of them yet:

| tool | key |
|---|---|
| Quarto | `filters:`, names or paths, with `at:` for the stage |
| panflute | `panflute-filters:`, with `panflute-path:` |
| panzer | `style:`, naming a set of filters defined elsewhere |
| pandocomatic | `pandocomatic_:` |
