---
title: Install
---

::: note
On PyPI the distribution is `pandoc-para` for now (the name `para` is requested); it
installs the package `para` and the command `parasite`.
:::

para.site needs Python ≥ 3.12 and pandoc ≥ 3.1. pandoc is not on PyPI: install it from
[pandoc.org](https://pandoc.org/installing.html) or conda-forge.

# With pixi or conda

```sh
pixi add pandoc
pixi add --pypi pandoc-para
```

# With pip

```sh
pip install pandoc-para
```

# Optional parts

| extra | for |
|---|---|
| `pandoc-para[search]` | search, with [Pagefind](https://pagefind.app/) (its binary comes with it) |
| `pandoc-para[extras]` | watching sources and serving the site while you write, reloading pages as they are rebuilt |
| `pandoc-para[graph]` | the post graph, with [paragraphic](https://github.com/ickc/paragraphic) |

The check of the output's links needs [lychee](https://lychee.cli.rs) (`pixi add
lychee`; see [builds](../builds/)).

Filters a site uses (pantable, pannb, …) are installed like any package, then named in
its `parasite.toml` (see [filters](../filters/)).

# From the source

```sh
git clone https://github.com/ickc/parasite
cd parasite
pixi run test
```
