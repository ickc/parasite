# Revision history for `para`

## v0.2.3

- **Deterministic on any filesystem:** sources are read in path order, not the
  filesystem's, so posts of the same date are listed in path order, and the search
  index is the same, wherever the site is built.

## v0.2.2

- **Links:** a link or image URL from the site's root (`/about/`) is written relative
  to the page (`../../about/`), after the read filters, so a site works under any path
  (a GitHub project site, a path on a shared server). The lightgallery filters' photo
  links are relative too.

## v0.2.1

- **Post graph:** paragraphic 0.3 (`pandoc-para[graph]`). Its viewer pairs the
  posts that share a source through an index from each source to its posts, so a
  large site's graph opens faster; the graph itself is unchanged.

## v0.2.0

A rewrite around records, output profiles and incremental builds. The package is
`para` (on PyPI as `pandoc-para`), the site generator `para.site` (`from para.site
import Config, cli`); the command is `parasite`.

- **Configuration:** a site is configured by `parasite.toml`, merged over
  `para/defaults.toml`, which documents every key. A site's `run.py` is no longer
  needed (see the docs' migration page).
- **Pipeline:** sources are read into records (URL, title, dates, category, tags,
  description, search text, links, citations, outputs, media). Listings, feeds, the
  sitemap, search and the post graph come from records, and every file goes through one
  output tree. That tree refuses two producers of one path, writes only changed bytes,
  and reports or prunes (`--prune`) what the build no longer produces.
- **Incremental builds:** a record store (`.para/store.sqlite`). A source is read again
  only when its bytes, the site's code, pandoc, config, or a file its read touched
  changed; `--full` ignores the store.
- **Output profiles:** a source has an output per profile (`format: [html, slides]`).
  Content for some outputs uses Quarto's `.content-visible`/`.content-hidden`, and an
  output can have its own metadata (`format: NAME: metadata:`) and pandoc variables.
  Also `output-file`, and `format-links` with a profile's `label`.
- **PDF output:** a `pdf` profile, Typst by default, dated by the page, so a PDF is the
  same from build to build.
- **Languages:** BCP 47 tags, with lookups from the most specific to the least.
  Translations: `x.LANG.md` beside `x.md`, or made by OpenCC
  (`pandoc-para[opencc]`), linked with `hreflang`.
- **Filters by name:** Python (`module:function`) or installed Lua filters, chosen per
  document with `filters: [name, -name]`.
- **Media:** copied by reference (`[media.folders]`): only what pages use. After the
  build, lychee checks every link offline, and the build fails on broken ones.
- **Search:** Pagefind (`pandoc-para[search]`), indexing the records in the site's
  language, with tags and categories as filters, deterministic from build to build.
- **Post graph:** `graph.json`, a local graph on each page, and `/graph/` (needs
  `pandoc-para[graph]`, paragraphic ≥ 0.2).
- **Listings:** `description` instead of teasers, falling back to `subtitle`. The front
  page shows the newest posts, with an archive by year. Categories form a tree, and
  feeds carry the newest posts. Copyright years come from the pages' own dates.
- **Removed:** parsl (now a thread pool, `--jobs`), urlpath, tipuesearch,
  previous/next links, and the retired front-matter keys (`status`, `previewimage`,
  `slug`, …; para.site warns).
- **Output:** well-formed XHTML; pandoc ≥ 3.11's `--math-method`.
- **Requirements:** Python ≥ 3.12 and pandoc ≥ 3.1.

## v0.1.0

First release and proof of concept.
