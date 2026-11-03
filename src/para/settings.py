"""parasite.toml: a site's configuration, as data.

The site's file is merged over parasite's defaults (``defaults.toml``, which documents
every key). :func:`load` returns the site's :class:`para.site.Config`: its fields'
defaults come from the file, so a command line can still override them, and the rest
is read from its ``settings``. Code runs only from what is installed: filters are named
as importable ``module:function``, never as paths in the site.
"""

from __future__ import annotations

import tomllib
from dataclasses import field, make_dataclass
from pathlib import Path
from typing import Any

from .config import SettingsError, defaults, mathjax_config
from .lang import tag
from .site import Config

FILE = "parasite.toml"

# tables that list a site's own entries: a site's replaces the default whole
WHOLE = {("files",), ("media", "folders"), ("minify", "css"), ("minify", "js")}
# tables whose order matters: a site's keys come first, in its order
ORDERED = {("filters",)}


def merge(base: dict[str, Any], over: dict[str, Any], at: tuple[str, ...] = ()) -> dict[str, Any]:
    """``over`` merged into ``base``: tables key by key (but those in :data:`WHOLE`),
    anything else replaced; in the tables of :data:`ORDERED` ``over``'s keys first."""
    res = dict(base)
    for key, value in over.items():
        here = (*at, key)
        if isinstance(value, dict) and isinstance(res.get(key), dict) and here not in WHOLE:
            res[key] = merge(res[key], value, here)
        else:
            res[key] = value
    if at in ORDERED:
        res = {**{key: res[key] for key in over}, **{key: v for key, v in res.items() if key not in over}}
    return res


def read(path: Path = Path(FILE)) -> dict[str, Any]:
    with open(path, "rb") as f:
        return merge(defaults(), tomllib.load(f))


def load(path: Path = Path(FILE)) -> type[Config]:
    """The Config class of the site configured by ``path``."""
    s = read(path)
    site, listing = s["site"], s["listing"]
    font_min, font_max = listing["tag-cloud"]
    values = {
        # with its trailing slash: page URLs are appended to it
        "site_url": site["url"] and site["url"].rstrip("/") + "/",
        "blog_email": site["email"],
        "n_jumbotron": listing["jumbotron"],
        "n_grid": listing["grid"],
        "index_include_jumbotron": listing["include-jumbotron"],
        "tag_cloud_font_size_min": font_min,
        "tag_cloud_font_size_max": font_max,
        "logo_url": site["logo"],
        "output_dir": Path(site["output"]),
        "date_format": site["date-format"],
        "mathjax_config": mathjax_config(s["mathjax"]),
        "default_lang": tag(site["lang"]),
        "timezone": site["timezone"],
        "convert_pdf_media": s["media"]["convert-pdf"],
        "write_search": s["search"]["enabled"],
        "search_page": s["search"]["page"],
        "check_links": s["check"]["links"],
        "write_rss": s["feeds"]["rss"],
        "write_atom": s["feeds"]["atom"],
        "write_sitemap": s["sitemap"]["enabled"],
        "include_draft": site["drafts"],
        "index_length": listing["index-length"],
        "feed_length": s["feeds"]["length"],
        "write_listings": listing["enabled"],
        "write_graph": s["graph"]["enabled"],
        "graph_colours": s["graph"]["colours"],
    }
    uncoloured = list(s["graph"]["uncoloured"])
    fields = [(name, type(value), field(default=value)) for name, value in values.items()]
    fields.append(("graph_uncoloured", list[str], field(default_factory=lambda: list(uncoloured))))
    return make_dataclass("SiteConfig", fields, bases=(Config,), namespace={"settings": s})


__all__ = ["FILE", "SettingsError", "load", "merge", "read"]
