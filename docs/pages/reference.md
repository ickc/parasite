---
title: Every key
description: parasite's defaults.toml, which a site's parasite.toml is merged over.
---

<!-- written by docs/makefile from src/para/defaults.toml: do not edit -->

A site's `parasite.toml` is merged over this file (see [parasite.toml](../configuration/)).

```toml
# parasite's defaults. A site's parasite.toml is merged over this: tables key by key,
# everything else (strings, numbers, lists) replaced whole, and so are [files] and
# [minify.*], which list the site's own entries. In strings, {root} becomes
# the relative path from the page to the site's root, and {years} the copyright years.

[site]
url = ""
# a string, or a table by language: { en = "…", zh_tw = "…" }
title = ""
description = ""
author = ""
email = ""
lang = "en"
timezone = "America/Los_Angeles"
logo = ""
copyright = "Contents © {years} {author}"
output = "output"
date-format = "%Y-%m-%d"
drafts = false

[listing]
# the listings of posts: the front page, categories, tags, the archive (a site without
# posts has none; without listings, a page index.md is the front page)
enabled = true
# the front page: the newest `index-length` posts, the first `jumbotron` large, the next
# `grid` in a grid; older posts are in the archive
index-length = 10
jumbotron = 1
grid = 2
include-jumbotron = true
tag-cloud = [70, 280]
# the output profile of the derived pages (listings, the archive, the graph)
profile = "html"

[feeds]
rss = true
atom = true
length = 10

[sitemap]
enabled = true

# search (Pagefind, needs pagefind[bin]): an index of the pages, and a search page
[search]
enabled = true
# the search page, a folder ("search/") or a file ("search.html")
page = "search/"

# links checked after the build with lychee (https://lychee.cli.rs), offline: every link
# and media reference from the site's files to its files must resolve, else the build
# fails (after writing the output). Without lychee installed, a warning
[check]
links = true
# regular expressions of links not to check: a site's file is a file:// URL
exclude = []
# regular expressions of the output's files not to read
exclude-path = []

[graph]
enabled = false
uncoloured = []
colours = 7

[media]
# convert PDF media embedded in sources (e.g. notebook outputs) to SVG
convert-pdf = true

# folders of media, copied by reference: only the files pages use (their images, links,
# raw HTML, `image`, and what those files reference); source folder = output folder
[media.folders]
media = "media"

# folders of site files, copied whole (robots.txt, favicons, …): source folder = output folder
[files]
files = ""

# minified into the output: output path = [source files]
[minify.css]
"assets/css/all-nocdn.css" = [
    "_css/bootstrap.css",
    "_css/rst_base.css",
    "_css/nikola_rst.css",
    "_css/code.css",
    "_css/theme.css",
    "_css/bootblog.css",
    "_css/custom.css",
]

[minify.js]

# window.MathJax, as a table; `macros-file` (a JSON file) is merged into tex.macros
[mathjax]

# What is built: each collection is a folder of sources with given extensions, built into
# `out` (a folder of the output) in the output profiles of `format`. Posts are `listed`:
# dated, and in the listings and feeds.
[[sources]]
dir = "posts"
ext = [".md", ".ipynb"]
listed = true
format = ["html"]
exclude = [".ipynb_checkpoints/**"]

[[sources]]
dir = "pages"
ext = [".md", ".ipynb"]
format = ["html"]
exclude = [".ipynb_checkpoints/**"]

[[sources]]
dir = "posts"
ext = [".markdown"]
format = ["slides"]

# Reading: pandoc's options, for every source and per input format (appended).
[read]
options = []

# The filters a site may use, in the order they run (a site's [filters] table sets the
# order: its filters first, in its order, then the defaults it does not mention). `python` is an importable
# "module:function" taking and returning a panflute Doc; `at` is "read" (after reading,
# for every output) or "render" (named by a profile, for its output only); `inputs`
# limits a read filter to some input formats; `default` runs it on every document.
[filters.lightgallery-from-dir]
python = "para.panflute_filters:lightgallery_from_dir_filter"
default = true

[filters.lightgallery]
python = "para.panflute_filters:lightgallery_filter"
at = "render"

[filters.mathjax-bold-ell]
python = "para.panflute_filters:mathjax_bold_ell_filter"
at = "render"

# Output profiles: the writer (`to`), the template (a built-in name: post, index,
# slides; or a path), the URL of a source's output ({stem} is its name; "{stem}/" is
# {stem}/index.html), pandoc's options, the render filters, and the page's parts.
[profiles.html]
to = "html"
template = "post"
url = "{stem}/"
options = ["--mathjax", "--wrap=none"]
filters = ["lightgallery", "mathjax-bold-ell"]
show-image = true
css = [
    "{root}/assets/css/all-nocdn.css",
    "https://fonts.googleapis.com/css?family=Playfair+Display:700,900",
]
js = [
    "https://cdn.jsdelivr.net/npm/jquery@3/dist/jquery.min.js",
    "https://cdn.jsdelivr.net/npm/bootstrap@4/dist/js/bootstrap.bundle.min.js",
    "https://cdn.jsdelivr.net/npm/tocbot@4/dist/tocbot.min.js",
    "https://cdn.jsdelivr.net/npm/lightgallery@2/lightgallery.umd.js",
    "https://cdn.jsdelivr.net/npm/lightgallery@2/plugins/thumbnail/lg-thumbnail.umd.js",
    "https://cdn.jsdelivr.net/npm/justifiedGallery@3/dist/js/jquery.justifiedGallery.min.js",
]
header-includes = ""
include-before = ""
include-after = ""
script-include-after = """tocbot.init({
  tocSelector: '.js-toc',
  contentSelector: '.entry-content',
  headingSelector: 'h1, h2, h3, h4, h5, h6',
  collapseDepth: 1,
});"""
# a list of { text, href } and { text, menu = [ … ] }, or a table of them by language
nav = [
    { text = "Home", href = "{root}/index.html" },
    { text = "About", href = "{root}/about/" },
    { text = "Archive", menu = [
        { text = "Categories", href = "{root}/categories/" },
        { text = "Archive", href = "{root}/archive/" },
    ] },
]
footer = 'Contents © {years}         <a href="mailto:{email}">{author}</a>'
search-form = """<form class="navbar-form navbar-left" action="{root}/search/" role="search">
    <div class="form-group">
        <input type="text" class="form-control" name="q" placeholder="Search" autocomplete="off" />
    </div>
</form>"""

[profiles.slides]
to = "slidy"
template = "slides"
url = "{stem}/present.html"
options = ["--mathjax", "--wrap=none"]
filters = ["lightgallery", "mathjax-bold-ell"]
show-image = true
css = []
js = []
header-includes = ""
include-before = ""
include-after = ""
script-include-after = ""
nav = []
footer = ""
search-form = ""
```
