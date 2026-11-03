# parasite

A pandoc-first static site generator: websites from documents pandoc can read, with
listings, categories and tags, feeds, a sitemap, search, a graph of how the pages link,
and builds that redo only what changed. A site is configured by one file,
`parasite.toml`.

The Python package is `para`, the command `parasite`:

```python
from para import site
```

Documentation: <https://ickc.github.io/parasite/> (its source is `docs/`, built with
parasite).

## Develop

```sh
pixi run test
make docs
```

## Licence

BSD-3-Clause.
