---
title: parasite
subtitle: A pandoc-first static site generator
---

parasite builds websites from documents pandoc can read: Markdown, Jupyter notebooks,
and anything else pandoc has a reader for. Its documents, metadata and templates are
pandoc's own. It adds what a site needs around them: listings, categories and tags, an
archive, feeds, a sitemap, search, a graph of how the pages link, and builds that redo
only what changed.

The Python package is `para`, and the command is `parasite`:

```python
from para import site
```

# Why

- **pandoc first.** No syntax of its own: no shortcodes, no extensions to Markdown.
  A source is a pandoc document; its options are pandoc's options.
- **Configured as data.** A site is described by one file, `parasite.toml`. Code runs
  only as filters you named, from packages you installed.
- **One source, several outputs.** A talk can be a page and its slides, from one file
  (see [output profiles](profiles/)).
- **Incremental.** A build reads and renders only what changed; a rebuild with nothing
  changed takes a fraction of a second (see [how it builds](builds/)).
- **Valid XHTML.** Every page is well-formed.

# A site in a minute

A folder with a `parasite.toml`:

```toml
[site]
url = "https://example.org/"
title = "My site"
author = "Me"
```

and Markdown files under `posts/` (dated, listed) and `pages/` (not listed):

```markdown
---
title: Hello
date: 2026-10-11
tags: [hello]
---

The first post.
```

Then, in that folder:

```sh
parasite
```

writes the site to `output/`. `parasite --help` lists what the command line can
override.

These pages are themselves built with parasite: see `docs/` in its repository.
