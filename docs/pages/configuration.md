---
title: parasite.toml
description: A site's configuration, as data.
---

A site is a folder with a `parasite.toml`. `parasite` builds the site in the working
directory from it.

# Merged over the defaults

parasite has a `defaults.toml`, which documents every key: see [every key](../reference/).
A site's `parasite.toml` is merged over it:

- tables, key by key: a site writes only what differs;
- anything else (strings, numbers, lists) replaced whole;
- `[files]`, `[media.folders]`, `[minify.css]` and `[minify.js]` replaced whole too, as
  they list a site's own entries;
- `[filters]` in the site's order: its filters first, then the defaults it does not
  mention.

# The parts

| table | what |
|---|---|
| `[site]` | URL, title, description, author, language, time zone, logo, copyright, output folder, drafts |
| `[listing]` | the front page, categories, tags and the archive, or none |
| `[feeds]`, `[sitemap]`, `[search]`, `[graph]` | what else is written |
| `[[sources]]` | collections: folders of sources, their extensions, whether they are listed posts, their output profiles |
| `[read]`, `[read.EXT]` | pandoc's options for reading, for every source and per input format |
| `[filters.NAME]` | the filters a site may use (see [filters](../filters/)) |
| `[profiles.NAME]` | output profiles: writer, template, URL rule, options, filters, the page's parts (see [output profiles](../profiles/)) |
| `[files]` | folders of site files, copied whole |
| `[media.folders]` | folders of media, copied by reference: only what pages use |
| `[minify.css]`, `[minify.js]` | style sheets and scripts bundled and minified |
| `[mathjax]` | MathJax's configuration, as a table |

# In strings

`{root}` becomes the relative path from the page to the site's root (`..`, `../..`, or `.`
at the top), and `{years}` the copyright years (a post's own, from its `date` to its
`date-modified`; a page without dates has the site's). The footer also has `{author}`
and `{email}`. No other braces are touched, so scripts need no escaping.

# By language

A string can instead be a table by language, used for the page's `lang`:

```toml
[site]
lang = "zh_tw"
title = { en = "KcIc", zh_tw = "祺" }
```

# On the command line

The settings that are fields of the build (`parasite --help`) can be overridden there,
for one build: `parasite --include-draft`, `parasite --full`, `parasite --prune`.
