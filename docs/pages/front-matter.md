---
title: Front matter
description: The keys parasite reads from a document's metadata.
---

A document's metadata is pandoc's: YAML front matter in Markdown, the first raw cell of a
notebook. pandoc's own keys keep pandoc's meaning; where Quarto has the same idea,
parasite uses Quarto's name.

| key | meaning |
|---|---|
| `title`, `subtitle`, `author`, `abstract` | pandoc's |
| `lang` | the page's language, a BCP 47 tag (see [languages](../languages/)); a translation's comes from its file name |
| `date` | when it was first published; a post needs one. An ISO 8601 date or date-time, in the site's time zone unless it says otherwise |
| `date-modified` | when its content last changed, by hand. A post's copyright runs from `date` to `date-modified` |
| `description` | one or two plain sentences, for listings, `<meta name="description">` and search; shown under the title. Without one, the `subtitle` is used |
| `category` | one per post, a path (`so-uk/meetings`). It defaults to the source's folder, so it is rarely written; a category lists its subcategories' posts too |
| `tags` | a list; each tag has a page |
| `draft: true` | built only with `--include-draft`, and never listed |
| `image`, `image-alt` | its thumbnail in listings, from the site's root, and the thumbnail's text (else the title) |
| `format` | its output profiles (see [output profiles](../profiles/)) |
| `format-links` | which of its other outputs an output links to, by each profile's `label`: `true` all, `false` none, or a list of profile names. Without it, slides link to the page beside them (Report) |
| `output-file` | an output's file name, in its folder, as an exception to the URL rules: at the top level the first output's, under `format: NAME:` that output's |

# Keys from parasite ≤ 0.1

parasite warns about these and otherwise ignores them:

| key | instead |
|---|---|
| `<!-- more -->` (a teaser) | `description` |
| `status: draft` | `draft: true` |
| `status: featured` | nothing: the front page shows the newest posts |
| `previewimage` | `image` |
| `slug`, `pretty_url`, `url_type` | the source's path |
| `type` | nothing |
| `sidebar_toc` | `toc` |
| `temp` | nothing |
