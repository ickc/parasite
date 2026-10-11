---
title: Output profiles
description: One source, several outputs.
---

An output profile is how a source becomes one output: a pandoc writer, a template, a URL
rule, pandoc's options, the filters that run for that output only, and the page's parts
(style sheets, scripts, includes, navigation, footer). A site declares its profiles in
`[profiles.NAME]`; parasite's defaults have `html` (a page) and `slides` (slidy):

```toml
[profiles.slides]
to = "slidy"
template = "slides"
url = "{stem}/present.html"
css = ["https://example.org/slides.css"]
```

`url` is where a source's output goes, from its path: `{stem}/` is `{stem}/index.html`,
so `posts/a/b.md` is `a/b/` (the `posts` folder is the collection's). A source named
`index` is its folder's page, and `404` is `404.html`.
A document's `output-file` names one output's file instead, in the same folder. `label`
is what links from a page's other outputs to this one say (`format-links`, see
[front matter](../front-matter/)).

# Which profiles a source has

Its collection's (`[[sources]]`'s `format`), or its own:

```yaml
format: [html, slides]
```

The first is its URL's: listings, search and the graph link to it.

# Content for one output

Quarto's syntax: a div (or span) shown only in some outputs, by profile name or writer:

```markdown
::: {.content-visible when-format="html"}
[The slides](present.html), and the slides embedded:

![](present.html){width=100% height=720}
:::

::: {.content-visible when-format="slides"}
See @montgomery_2020.
:::
```

`.content-hidden` is the opposite, and `unless-format` inverts `when-format`.

Each output sees the source **before** it is read: for Markdown the selection is made on
the text, so heading identifiers, crossref's figure numbers and citeproc's bibliography
are each output's own. Such a source is read once per output; any other source, once.

# Metadata for one output

Under its profile's name in `format`, with pandoc's defaults-file key `metadata`:

```yaml
author: Kolen
format:
  html: default
  slides:
    metadata:
      author: Kolen Cheung—SO:UK Data Centre Software Engineer
```

# PDF

parasite's defaults have a `pdf` profile: Typst, through pandoc. One engine per profile
(`engine`: `typst`, or a LaTeX engine such as `xelatex`): a document is not expected
in both. Its template is pandoc's for that engine, unless `template` names a file.

```yaml
format:
  html: default
  pdf:
    variables:
      papersize: a5
format-links: [pdf]
```

`variables` are pandoc's (`--variable`), for any profile. A PDF's images are found from
its folder in the output, where the media it uses are copied; it is dated by its page's
`date-modified` or `date` (`SOURCE_DATE_EPOCH`), so the same page gives the same bytes
and is not rewritten. It needs the engine installed (`pixi add typst`).

