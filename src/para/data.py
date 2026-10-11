from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import panflute as pf
from panflute.tools import convert_text

if TYPE_CHECKING:
    from typing import (
        List,
        Optional,
        Sequence,
        Tuple,
        TypeVar,
    )

    from .config import Collection, Config, Profile
    from .record import Record

    PagesLike = TypeVar("PagesLike", bound="Pages")

logger = getLogger(__name__)


# front-matter keys of parasite ≤ 0.1 (and Nikola before it), and what replaces each
RETIRED_KEYS = {
    "status": "draft: true for a draft, nothing otherwise",
    "previewimage": "image",
    "slug": "the source's path (output-file for an exception)",
    "pretty_url": "the source's path (output-file for an exception)",
    "url_type": "the source's path (output-file for an exception)",
    "type": "nothing",
    "sidebar_toc": "toc",
    "temp": "nothing: pandoc includes MathJax for raw TeX math environments",
}


def format_years(years: Optional[Tuple[int, int]]) -> str:
    """``2016``, ``2016–2026``, or empty when unknown."""
    if years is None:
        return ""
    first, last = years
    return str(first) if first == last else f"{first}–{last}"


def root_of(out_path: Path) -> str:
    """The relative path from the output ``out_path`` to the site's root.

    Note: not a URL object, as one would normalise "." to ""."""
    level = len(out_path.parent.parts)
    return "." if level == 0 else "/".join([".."] * level)


@dataclass
class Page:
    """A source, and its outputs: one per output profile, the first its URL's."""

    path: Path
    collection: Collection
    # the site's profiles by name
    site_profiles: dict[str, Profile] = field(repr=False)
    timezone: str = r"America/Los_Angeles"
    date_format: str = r"%Y-%m-%d"
    default_lang: str = "en"
    # its record, once read (see para.record)
    record: Optional[Record] = field(default=None, init=False, repr=False)
    # the key it was read under, and the files its read wrote into the output (para.store)
    read_key: str = field(default="", init=False, repr=False)
    claims: List[str] = field(default_factory=list, init=False, repr=False)
    # its profiles: the collection's, until its own ``format`` is read
    profiles: List[Profile] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.profiles = [self.site_profiles[name] for name in self.collection.format]

    @property
    def base_path(self) -> Path:
        return self.collection.dir

    @property
    def out_base_path(self) -> Path:
        return self.collection.out

    @property
    def ext(self) -> str:
        return self.path.suffix

    def _out_path(self, profile: Profile) -> Path:
        rel = self.out_base_path / self.path.relative_to(self.base_path)
        return profile.out_path(rel.parent, rel.stem)

    @property
    def outputs(self) -> List[Tuple[Profile, Path]]:
        """Its outputs: (profile, path in the output directory)."""
        return [(profile, self._out_path(profile)) for profile in self.profiles]

    @property
    def out_path(self) -> Path:
        """Its first output's path."""
        return self._out_path(self.profiles[0])

    @cached_property
    def media_dir(self) -> Path:
        """Where its read writes media: the folder of its collection's first output. Its
        outputs are all in this folder (see :meth:`set_profiles`)."""
        return self._out_path(self.site_profiles[self.collection.format[0]]).parent

    def set_profiles(self) -> None:
        """Its profiles from its ``format``: a list of profile names, or a table keyed by
        them (Quarto's form), else its collection's."""
        value = self.ast.get_metadata("format")
        if value is None:
            return
        names = list(value) if isinstance(value, (list, dict)) else [str(value)]
        unknown = [name for name in names if name not in self.site_profiles]
        if unknown:
            raise ValueError(f"{self.path}: format {unknown} not in the site's [profiles]")
        self.profiles = [self.site_profiles[name] for name in names]
        elsewhere = [str(path) for _, path in self.outputs if path.parent != self.media_dir]
        if elsewhere:
            raise ValueError(f"{self.path}: outputs {elsewhere} are not in {self.media_dir}, where its media are")

    @cached_property
    def per_profile(self) -> bool:
        """Whether the source has content per profile (``.content-visible``,
        ``.content-hidden``): a cheap test of its text."""
        return b"content-visible" in (data := self.path.read_bytes()) or b"content-hidden" in data

    @property
    def url(self) -> str:
        """Its URL relative to the site's root: ``a/b/`` for ``a/b/index.html`` from a
        profile of folders."""
        out_path = self.out_path
        if self.profiles[0].pretty and out_path.name == "index.html":
            parent = out_path.parent.as_posix()
            return ("" if parent == "." else parent) + "/"
        return out_path.as_posix()

    @cached_property
    def category(self) -> str:
        """Its one category, a path: ``category`` in its metadata, else its source's
        directory below the posts' root ("" at the root)."""
        category = self.ast.get_metadata("category")
        if category:
            return str(category).strip("/")
        return "/".join(self.path.relative_to(self.base_path).parent.parts)

    @property
    def root(self) -> str:
        """The relative path from its first output to the site's root."""
        return root_of(self.out_path)

    def _metadata_time(self, key: str) -> Optional[datetime]:
        """The date-time in metadata ``key``, in the site's time zone unless it says
        otherwise; None if absent or not a date."""
        value = self.ast.get_metadata(key)
        if value is None:
            return None
        value = str(value).strip()
        try:
            time = datetime.strptime(value, self.date_format)
        except ValueError:
            try:
                time = datetime.fromisoformat(value)
            except ValueError:
                logger.warning("%s: %s is not a date: %s", self.path, key, value)
                return None
        if time.tzinfo is None:
            time = time.replace(tzinfo=ZoneInfo(key=self.timezone))
        return time

    @cached_property
    def published(self) -> Optional[datetime]:
        """When it was first published: its ``date``."""
        return self._metadata_time("date")

    @cached_property
    def modified(self) -> Optional[datetime]:
        """When its content last changed: its ``date-modified``, set by hand."""
        return self._metadata_time("date-modified")

    @property
    def updated(self) -> Optional[datetime]:
        return self.modified or self.published

    @property
    def years(self) -> Optional[Tuple[int, int]]:
        """The first and last year of its content, from its own dates only."""
        if self.published is None:
            return None
        return self.published.year, max(self.published, self.updated).year

    # AST & its derivatives

    # TODO: consider adding pandoc_input_options, panflute_input_filters
    # to self.options s.t. we can pass it here?
    # def get_ast(self):
    # missing arg below
    #     self._ast = read_md_to_ast([self.path])

    @property
    def ast(self) -> pf.elements.Doc:
        # if not hasattr(self, '_ast'):
        #     self.get_ast()
        # return self._ast
        try:
            return self._ast
        except AttributeError:
            raise AttributeError(
                "ast not set yet. Consider using para.apps.read_md_to_ast"
            )

    @ast.setter
    def ast(self, doc: pf.elements.Doc) -> None:
        self._ast = doc

    @ast.deleter
    def ast(self) -> None:
        del self._ast

    @cached_property
    def text(self) -> str:
        return "\n".join(pf.stringify(elem) for elem in self.ast.content)

    @cached_property
    def html(self) -> str:
        """HTML frament.

        Primarily for feed.
        """
        return convert_text(
            self.ast,
            input_format="panflute",
            output_format="html",
            standalone=False,
            extra_args=["--wrap=none"],
        )

    @property
    def title(self) -> Optional[str]:
        return self.ast.get_metadata("title")

    @property
    def author(self) -> Optional[str]:
        return self.ast.get_metadata("author")

    @property
    def lang(self) -> str:
        lang = self.ast.get_metadata("lang")
        if lang is None:
            lang = self.default_lang
            self.ast.metadata["lang"] = lang
        return lang

    @property
    def tags(self) -> List[str]:
        tags = self.ast.get_metadata("tags")
        if tags is None:
            tags = []
        return tags

    @property
    def description(self) -> Optional[str]:
        """The summary of the page: its ``description``, as plain text."""
        meta = self.ast.metadata.content.get("description")
        return None if meta is None else pf.stringify(meta)

    @property
    def summary(self) -> Optional[str]:
        """What listings show for the page: its ``description``, else its ``subtitle``."""
        if (res := self.description) is not None:
            return res
        meta = self.ast.metadata.content.get("subtitle")
        return None if meta is None else pf.stringify(meta)

    @property
    def image(self) -> Optional[str]:
        """Its thumbnail and og:image: ``image``."""
        res = self.ast.get_metadata("image")
        return None if res is None else str(res)

    def check_metadata(self) -> None:
        """Warn about front matter from parasite ≤ 0.1, which is ignored now."""
        for key, replacement in RETIRED_KEYS.items():
            if key in self.ast.metadata.content:
                logger.warning("%s: %s is retired, use %s", self.path, key, replacement)
        for elem in self.ast.content:
            if isinstance(elem, pf.RawBlock) and elem.format == "html" and "<!-- more -->" in elem.text:
                logger.warning("%s: <!-- more --> is retired, use description", self.path)
                break

    @property
    def is_draft(self) -> bool:
        """``draft: true``: built only with include_draft, never listed."""
        return bool(self.ast.get_metadata("draft", False))


@dataclass
class Post(Page):
    """A listed page: dated, in the listings and feeds."""


@dataclass
class Pages:
    pages: Sequence[Page]
    page_class: ClassVar[type] = Page

    @classmethod
    def from_config(cls: type[PagesLike], config: Config) -> PagesLike:
        """The sources of the config's collections: those listed for :class:`Posts`, the
        others for :class:`Pages`."""
        listed = cls is not Pages
        res: list[Page] = []
        for collection in config.collections:
            if collection.listed is not listed:
                continue
            for ext in collection.ext:
                res += [
                    cls.page_class(
                        path,
                        collection,
                        config.profiles,
                        timezone=config.timezone,
                        date_format=config.date_format,
                        default_lang=config.default_lang,
                    )
                    for path in collection.dir.glob(f"**/*{ext}")
                    if not any(path.match(exclude) for exclude in collection.exclude)
                ]
        return cls(res)


@dataclass
class Posts(Pages):
    pages: Sequence[Post]
    page_class: ClassVar[type] = Post
