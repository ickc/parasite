---
title: Install
---

::: note
On PyPI the distribution is `python-para` for now (the name `para` is requested); it
installs the package `para` and the command `parasite`.
:::

para.site needs Python ≥ 3.12 and pandoc ≥ 3.1. pandoc is not on PyPI: install it from
[pandoc.org](https://pandoc.org/installing.html) or conda-forge.

# With pixi or conda

```sh
pixi add pandoc
pixi add --pypi python-para
```

# With pip

```sh
pip install python-para
```

# Optional parts

| extra | for |
|---|---|
| `python-para[search]` | search, with [Pagefind](https://pagefind.app/) (its binary comes with it) |
| `python-para[extras]` | coloured logs; watching sources and serving the site while you write |

The post graph needs [paragraphic](https://github.com/ickc/paragraphic) installed (`pip
install 'paragraphic @ git+https://github.com/ickc/paragraphic@v0.1.0'`, or `pixi add
--pypi 'paragraphic @ git+https://github.com/ickc/paragraphic@v0.1.0'`), and the check of
the output's links [lychee](https://lychee.cli.rs) (`pixi add lychee`; see
[builds](../builds/)).

Filters a site uses (pantable, pannb, …) are installed like any package, then named in
its `parasite.toml` (see [filters](../filters/)).

# From the source

```sh
git clone https://github.com/ickc/parasite
cd parasite
pixi run test
```
