---
title: Languages
description: A site's language, a page's, and translations written beside each other or made by conversion.
---

# Language tags

Languages are [BCP 47](https://www.rfc-editor.org/info/bcp47) tags, which name the
written language: `en`, `zh-Hant` (Traditional Chinese), `zh-Hans` (Simplified), and if
needed more specific ones, such as `zh-Hant-HK`. `[site] lang` is the site's; a page sets
its own with `lang` in its front matter. Tags are written in any case, and `_` is read as
`-`: Nikola's `zh_tw` is `zh-TW`, Chinese as used in Taiwan, a region rather than a
script.

A value by language, such as `title = { en = "…", zh-Hant = "…" }` or a profile's `nav`,
is looked up from the most specific tag to the least: a page in `zh-Hant-HK` takes the
`zh-Hant` value, then `zh`'s, then the site language's.

# Translations

Each of the site's other languages is a table of `[translations]`:

```toml
[site]
lang = "zh-Hant"

[translations.en]
[translations.zh-Hans]
convert = "hk2s"
```

**Written by hand.** `x.en.md` is the English translation of `x.md`, next to it. Its
outputs are written beside the primary's, in the same folder: `x/index.html` and
`x/index.en.html` (slides: `present.html` and `present.en.html`). So its relative links
and media work as they are written in `x.md`. Front matter it does not set (the date,
tags, category, image, `format`) is `x.md`'s; its title, description and body are its
own. `x.en.md` without an `x.md` is a page in English, at `x/`.

**Made by conversion.** With `convert`, an [OpenCC](https://github.com/BYVoid/OpenCC)
conversion (`hk2s`, `t2s`, `tw2s`, `s2t`, `s2hk`, `s2tw`, …), each page in the site's
language (or `from`) that has no written translation gets one: its text and metadata
converted, its code, URLs and raw HTML left as they are. It needs `para[opencc]`. A
value by language the site does not give for that language (its title, the `nav`) is
the source language's, converted.

**Between them.** Each version of a page links to the others: `<link rel="alternate"
hreflang>` in its head, and a line under the byline naming each language (`name` in its
table, else its own name: 繁體中文, 简体中文, English, …). Listings, tag and category
pages, feeds and the post graph show each page once, its primary version; the sitemap
lists every version, and search every version but conversions (the same text in
another script).

Not yet: listings, feeds and search per language, as a site per language under its own
folder; the theme's words for more languages than English and Chinese.
