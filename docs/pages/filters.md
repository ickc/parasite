---
title: Filters
description: The code a site runs, named in its parasite.toml.
---

A site lists the filters it may use in `[filters.NAME]`, in the order they run. A filter
is code from something you installed, never a path in the site: Python, a function
taking and returning a panflute document named as an importable `module:function`; or
Lua, by name, found where packages install Lua filters (the environment's
`share/pandoc/filters/`, as pandoc-forge's packages do) or in pandoc's user data
directory.

```toml
[filters.amsthm]
lua = "amsthm"
default = true

[filters.pannb]
python = "pannb:main"
inputs = ["ipynb"]
default = true

[filters.texp]
python = "texp.panflute_filter:main"
```

| key | meaning |
|---|---|
| `python` | the function, `module:function` |
| `lua` | the Lua filter's name (`amsthm` is `amsthm.lua`) |
| `at` | `"read"` (the default): after reading, for every output; `"render"`: for an output whose profile names it in its `filters`, or of a document that names it |
| `inputs` | a read filter for these input formats only (extensions without the dot) |
| `default` | a read filter runs on every document |

A document chooses among them with Quarto's key, by name:

```yaml
filters: [texp, -pantable]
```

turns `texp` on and `pantable` (a default) off. A name the site does not list fails that
page, with a message saying where to add it; a path is refused. The filters run in the
site's order, not the document's, so two documents with the same filters run them the
same way.

Read filters run after pandoc's own (the `--filter` and `--citeproc` of
`[read] options`), Lua ones in a pandoc call of their own. A Lua render filter runs in
the call that writes the output, after the Python ones, so that `FORMAT` is the
output's.

parasite's own: `lightgallery-from-dir` (read: a gallery from a folder of photos),
`lightgallery` and `mathjax-bold-ell` (render: MathJax has no bold ℓ, so
`\mathbf{\ell}` is written `\pmb{\ell}` in HTML).

pandoc's JSON filters (pandoc-crossref) and citeproc are pandoc options: put them in
`[read] options`. WebAssembly filters are planned.

# From other tools

Each has its own key for a document's filters; parasite reads none of them yet:

| tool | key |
|---|---|
| Quarto | `filters:`, names or paths, with `at:` for the stage |
| panflute | `panflute-filters:`, with `panflute-path:` |
| panzer | `style:`, naming a set of filters defined elsewhere |
| pandocomatic | `pandocomatic_:` |
