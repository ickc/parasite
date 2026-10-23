"""A page's record: what the build knows about a page apart from rendering it.

A record is made from the page's AST once it is read (step 3 of the pipeline). Everything
that crosses pages (listings, categories and tags, the archive, feeds, the sitemap,
search, the post graph, the site's years) is derived from records alone, so a document
is only needed to render it. Records are small and serialize to JSON.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import panflute as pf

if TYPE_CHECKING:
    from typing import Any, Optional, Sequence, Tuple

    from .data import Page


def _bibliography(doc: pf.Doc) -> list[pf.Div]:
    """citeproc's entries: the divs with id ref-<key> inside #refs."""
    found: list[pf.Div] = []

    def action(elem: pf.Element, doc: pf.Doc) -> None:
        if isinstance(elem, pf.Div) and elem.identifier.startswith("ref-"):
            found.append(elem)

    doc.walk(action)
    return found


def _links(elem: pf.Element) -> list[str]:
    found: list[str] = []

    def action(e: pf.Element, doc: pf.Doc) -> None:
        if isinstance(e, pf.Link):
            found.append(e.url)

    elem.walk(action)
    return found


@dataclass(frozen=True)
class Record:
    source: str
    # relative to the output directory, and the URL relative to the site's root
    out_path: str
    url: str
    post: bool
    title: Optional[str] = None
    author: Optional[str] = None
    lang: str = "en"
    # ``date`` as written (listings show it), and the dates as ISO 8601
    date: Optional[str] = None
    published: Optional[str] = None
    modified: Optional[str] = None
    category: str = ""
    tags: Tuple[str, ...] = ()
    summary: Optional[str] = None
    image: Optional[str] = None
    draft: bool = False
    # search
    text: str = ""
    # every link's URL in document order, and citeproc's entries: key → their URLs
    links: Tuple[str, ...] = ()
    citations: dict[str, Tuple[str, ...]] = field(default_factory=dict)
    # its outputs, by profile: the first is out_path's
    outputs: dict[str, str] = field(default_factory=dict)
    # the media files it uses, in the output directory (copied by reference)
    media: Tuple[str, ...] = ()
    # the source of the page it is a version of (its own, for a primary); for a
    # translation, its language, and whether OpenCC made it (see para.data.Page)
    group: str = ""
    translation: str = ""
    converted: bool = False
    # ``output-file``, by profile; ``image-alt``
    output_files: dict[str, str] = field(default_factory=dict)
    image_alt: Optional[str] = None

    @classmethod
    def from_page(cls, page: Page, post: bool, media: Sequence[str] = ()) -> Record:
        doc = page.ast
        date = doc.get_metadata("date")
        if post and page.published is None:
            raise ValueError(f"The following post has no date: {page.path}")
        tags = page.tags
        return cls(
            source=page.key,
            out_path=page.out_path.as_posix(),
            url=str(page.url),
            post=post,
            title=page.title,
            author=page.author,
            lang=page.lang,
            date=None if date is None else str(date),
            published=None if page.published is None else page.published.isoformat(),
            modified=None if page.modified is None else page.modified.isoformat(),
            category=page.category,
            tags=tuple(tags) if isinstance(tags, list) else (str(tags),),
            summary=page.summary,
            image=None if page.image is None else str(page.image),
            draft=page.is_draft,
            text=page.text,
            links=tuple(_links(doc)),
            citations={entry.identifier.removeprefix("ref-"): tuple(_links(entry)) for entry in _bibliography(doc)},
            outputs={profile.name: path.as_posix() for profile, path in page.outputs},
            media=tuple(media),
            group=page.group,
            translation=page.translation,
            converted=bool(page.convert),
            output_files=dict(page.output_files),
            image_alt=page.image_alt,
        )

    @property
    def time(self) -> Optional[datetime]:
        return None if self.published is None else datetime.fromisoformat(self.published)

    @property
    def updated(self) -> Optional[datetime]:
        return datetime.fromisoformat(self.modified) if self.modified is not None else self.time

    @property
    def years(self) -> Optional[Tuple[int, int]]:
        """The first and last year of its content, from its own dates only."""
        if self.time is None:
            return None
        return self.time.year, max(self.time, self.updated).year

    @property
    def external_candidates(self) -> list[str]:
        """The URLs of links outside the bibliography, in document order."""
        cited = Counter(url for urls in self.citations.values() for url in urls)
        res = []
        for url in self.links:
            if cited[url]:
                cited[url] -= 1
            else:
                res.append(url)
        return res

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Record:
        data = dict(data)
        data["tags"] = tuple(data["tags"])
        data["links"] = tuple(data["links"])
        data["citations"] = {k: tuple(v) for k, v in data["citations"].items()}
        data["media"] = tuple(data.get("media", ()))
        return cls(**data)


def site_years(records: Sequence[Record]) -> Optional[Tuple[int, int]]:
    """The first and last year of the site's content, from the pages' own dates:
    importing an old post widens the range, and the clock never enters it."""
    years = [record.years for record in records if record.years is not None]
    if not years:
        return None
    return min(first for first, _ in years), max(last for _, last in years)


def by_tag(posts: Sequence[Record]) -> dict[str, list[Record]]:
    res: dict[str, list[Record]] = {}
    for post in posts:
        for tag in post.tags:
            res.setdefault(tag, []).append(post)
    return res


def by_category(posts: Sequence[Record]) -> dict[str, list[Record]]:
    """Posts by category; a category also lists its subcategories' posts."""
    res: dict[str, list[Record]] = {}
    for post in posts:
        parts = post.category.split("/") if post.category else []
        for i in range(1, len(parts) + 1):
            res.setdefault("/".join(parts[:i]), []).append(post)
    return dict(sorted(res.items()))


def by_year(posts: Sequence[Record]) -> dict[int, list[Record]]:
    """Posts by the year they were published, newest year first."""
    res: dict[int, list[Record]] = {}
    for post in posts:
        res.setdefault(post.time.year, []).append(post)
    return dict(sorted(res.items(), reverse=True))
