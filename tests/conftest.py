from __future__ import annotations

from pathlib import Path

import panflute as pf

from para.config import Collection, Config
from para.data import Page

CONFIG = Config()
POSTS = Collection(Path("posts"), Path(""), (".md",), True, ("html",), ())


def make_page(cls: type[Page], path: str, ast: pf.Doc, format: tuple[str, ...] = ("html",)) -> Page:
    """A page of ``posts/`` with ``ast`` as read, in the default profiles."""
    collection = Collection(POSTS.dir, POSTS.out, (Path(path).suffix,), cls is not Page, format, ())
    page = cls(Path("posts") / path, collection, CONFIG.profiles)
    page.ast = ast
    page.set_profiles()
    return page
