---
title: Install
---

::: note
Not released yet: until `para` is on PyPI, install it [from the source](#from-the-source).
:::

parasite needs Python ≥ 3.12 and pandoc ≥ 3.1. pandoc is not on PyPI: install it from
[pandoc.org](https://pandoc.org/installing.html) or conda-forge.

# With pixi or conda

```sh
pixi add pandoc
pixi add --pypi para
```

# With pip

```sh
pip install para
```

# Optional parts

| extra | for |
|---|---|
| `para[search]` | search, with [Pagefind](https://pagefind.app/) (its binary comes with it) |
| `para[extras]` | coloured logs; watching sources and serving the site while you write |

The post graph needs [sitegraph](https://github.com/ickc/sitegraph) installed, and the
check of the output's links [lychee](https://lychee.cli.rs) (`pixi add lychee`; see
[builds](../builds/)).

Filters a site uses (pantable, pannb, …) are installed like any package, then named in
its `parasite.toml` (see [filters](../filters/)).

# From the source

```sh
git clone https://github.com/ickc/parasite
cd parasite
pixi run test
```
