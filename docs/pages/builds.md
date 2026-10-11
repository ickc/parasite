---
title: How it builds
description: Read, record, derive, render, write; and only what changed.
---

# The steps

1. **Discover** the sources of each collection.
2. **Read** each into a pandoc document, with the read filters.
3. **Record** it: a small summary of the page (URL, title, dates, category, tags,
   description, search text, links, citations, its outputs, the media it uses).
4. **Derive** what crosses pages from the records alone: listings, categories, tags,
   the archive, feeds, the sitemap, search, the graph, the site's copyright years.
5. **Render** each page in each of its profiles, and the derived pages. A page's
   document is dropped once rendered.
6. **Write**: every file through one output tree.

Pages are read and rendered in a thread pool: most of the work is pandoc, in its own
processes.

# Only what changed

The records are kept in `.para/store.sqlite` (ignore it in git). A build reads a source
again only when its **read key** changed, and renders a page again only when its
**render key** changed or a file it produced is gone:

- the **site key**: the code (the Python modules loaded, the installed packages,
  parasite's own files), pandoc and its data folder, the configuration, the site's other
  files (a bibliography, templates, data files: those git does not ignore) and the list
  of files in the copied folders. Any change here reads everything again;
- a **read key**: the site key and the source's bytes;
- a **render key**: the read key, the page's copyright years and its link to a report.

A derived page is rendered again when its document changed. `parasite --full` ignores
the store. A rebuild with nothing changed takes about a third of a second for a site of a
hundred pages.

# The output tree

Every file has one producer: a page, a derived page, a copied folder, a minified bundle,
a medium, a site-wide file. Two producers of one path is an error. A file is written
only when its bytes change, so an unchanged page keeps its modification time. Files in
the output folder that no step produced (a deleted page's) are reported, and removed
with `parasite --prune`.

# Media

`[media.folders]` are copied **by reference**: only the files the pages use, from their
images and links, raw HTML (`src`, `href`, `data`, `poster`, `url(…)`), their `image`,
and what those files use in turn (an HTML plot's scripts, an SVG's images, a style
sheet's). `[files]` are copied whole.

Media in a source itself (a notebook's outputs) are written next to the page; a PDF
image becomes SVG, which a browser can show.

# Search

With `[search] enabled` and `para[search]` installed, parasite indexes the records with
[Pagefind](https://pagefind.app/) and makes the search page (`[search] page`). The index
is sharded: one more page changes a few of its files. The search box in the navigation
sends `?q=` to it. Every page is indexed in the site's language (Pagefind searches the
index of the search page's language only). Tags and categories are its filters, and a
page's tags are searched as its words.

# Links

With [lychee](https://lychee.cli.rs) installed, parasite checks the output's links when
the build is done, offline: every link and media reference from the site's files to its
files must resolve, or the build fails (the output is written either way; a build that
serves or watches only logs them). This guards the media copied by reference: a
reference parasite did not see would be a broken link here. lychee reads the HTML, raw
HTML and `<style>` elements included, but not `style` attributes or CSS files.

Links known to be broken are excluded by `[check] exclude`, regular expressions of
URLs (a site's file is a `file://` URL); `[check] links = false` turns the check off.

# The post graph

With `[graph] enabled` and sitegraph installed, parasite writes `graph.json` from the
records (links, citations, external links, a page's other outputs) and the `/graph/`
page; every page gets a graph of its neighbours.
