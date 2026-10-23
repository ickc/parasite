---
title: Migrating
description: From parasite ≤ 0.1, and its run.py.
---

parasite ≤ 0.1 was configured by a site's `run.py`, a subclass of its `Config`. Every
part of it has a place in `parasite.toml`:

| run.py | parasite.toml |
|---|---|
| `site_url`, `blog_email`, `logo_url`, `default_lang`, `timezone` | `[site]` `url`, `email`, `logo`, `lang`, `timezone` |
| `blog_title`, `blog_author`, `blog_description` | `[site]` `title`, `author`, `description` (a string, or a table by language) |
| `copyright` | `[site] copyright`, with `{years}` and `{author}` |
| `n_jumbotron`, `n_grid`, `index_include_jumbotron` | `[listing]` `jumbotron`, `grid`, `include-jumbotron` |
| `write_rss`, `write_atom`, `write_sitemap`, `write_graph` | `[feeds]`, `[sitemap]`, `[graph]` |
| `write_tipuesearch_json` | `[search]` (Pagefind; parasite makes the search page) |
| `mathjax_config` | `[mathjax]`, as a table |
| `files_folders` | `[files]` (copied whole) and `[media.folders]` (copied by reference) |
| `posts`, `pages` | `[[sources]]`, with `listed = true` for posts |
| `pretty_urls` | a profile's `url` |
| `pandoc_input_options(ext)` | `[read] options`, `[read.EXT] options` |
| `panflute_input_filters(ext)` | `[filters.NAME]`, with `inputs` |
| `pandoc_output_options`, `panflute_output_filters`, `css`, `js`, `header_includes`, `include_before`, `include_after`, `script_include_after`, `nav_includes`, `content_footer`, `search_form` (by extension) | a profile's `options`, `filters`, `css`, `js`, `header-includes`, `include-before`, `include-after`, `script-include-after`, `nav`, `footer`, `search-form` |

The makefile then runs `parasite` instead of `./run.py`.

# Front matter

See [front matter](../front-matter/) for the keys parasite ≤ 0.1 used and what replaces
them. A teaser (`<!-- more -->`) becomes the `description`; tabs after a key's colon,
which pandoc accepts and PyYAML does not, become spaces.

# A page and its slides

A talk kept as `X.md` (the page) and `X.markdown` (the slides) becomes one source with
`format: [html, slides]`, what only one of them had in `.content-visible` divs (see
[output profiles](../profiles/)), and the slides' own metadata under `format: slides:
metadata:`.

# Search

The search page (`pages/search.md`, and tipuesearch's scripts) goes: parasite makes it.
