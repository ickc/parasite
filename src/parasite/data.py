from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import panflute as pf
from panflute.tools import convert_text
from urlpath import URL as Url

if TYPE_CHECKING:
    from typing import (
        Any,
        Callable,
        Dict,
        List,
        Optional,
        Sequence,
        Tuple,
        TypeVar,
        Union,
    )

    import pandas as pd

    from .config import Config

    PagesLike = TypeVar("PagesLike", bound="Pages")

logger = getLogger(__name__)


def format_years(years: Optional[Tuple[int, int]]) -> str:
    """``2016``, ``2016–2026``, or empty when unknown."""
    if years is None:
        return ""
    first, last = years
    return str(first) if first == last else f"{first}–{last}"


def site_years(pages: Sequence[Page]) -> Optional[Tuple[int, int]]:
    """The first and last year of the site's content, from the pages' own dates:
    importing an old post widens the range, and the clock never enters it."""
    years = [page.years for page in pages if page.years is not None]
    if not years:
        return None
    return min(first for first, _ in years), max(last for _, last in years)


@dataclass
class Page:
    path: Path
    base_path: Path
    out_base_path: Path
    template: Optional[Path]
    timezone: str = r"America/Los_Angeles"
    pretty_urls: Union[bool, Callable[[Path, str], Path]] = True
    date_format: str = r"%Y-%m-%d"
    default_lang: str = "en"
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # special casing 404
        if self.pretty_urls is True and str(self.out_path) == "404/index.html":
            logger.debug(f"Forcing non-pretty URL for {self.path}.")
            self.pretty_urls = False
            del self.out_path

    @property
    def _dict(self) -> dict[str, Any]:
        """A dict representation of self including all attributes and properties

        Primarily for dataframe
        """
        return {
            # init
            "path": self.path,
            "base_path": self.base_path,
            "out_base_path": self.out_base_path,
            "template": self.template,
            "pretty_urls": self.pretty_urls,
            # property
            "out_path": self.out_path,
            "url": self.url,

            "level": self.level,
            "root": self.root,
        }

    @property
    def dict_ast(self) -> dict[str, Any]:
        """A dict representation of self including the AST derived attributes

        Primarily for dataframe
        """
        res = self._dict
        res["lang"] = self.lang
        for key in self.ast.metadata.content:
            res["ast." + key] = self.ast.get_metadata(key)
        return res

    @property
    def ext(self) -> str:
        return self.path.suffix

    @cached_property
    def out_path(self) -> Path:
        out_path = self.out_base_path / self.path.relative_to(self.base_path)
        pretty_urls = self.pretty_urls
        if pretty_urls is True:
            out_path = out_path.parent / out_path.stem / "index.html"
        elif callable(pretty_urls):
            out_path = pretty_urls(out_path.parent, out_path.stem)
        else:
            out_path = out_path.parent / (out_path.stem + ".html")
        return out_path

    @cached_property
    def url(self) -> Url:
        out_path = self.out_path
        # pass to Url to normalize
        # to str to force adding a trailing /
        # back to Url again
        return (
            Url(str(Url(out_path.parent)) + "/")
            if self.pretty_urls is True
            else Url(out_path)
        )

    @cached_property
    def category(self) -> str:
        """Its one category, a path: ``category`` in its metadata, else its source's
        directory below the posts' root ("" at the root)."""
        category = self.ast.get_metadata("category")
        if category:
            return str(category).strip("/")
        return "/".join(self.path.relative_to(self.base_path).parent.parts)

    @cached_property
    def level(self) -> int:
        return len(self.out_path.parent.parts)

    @cached_property
    def root(self) -> str:
        """Relative path to root directory.

        Note: this cannot return `Url`. As `Url(".")` would be normalized to `Url("")`."""
        return "." if (level := self.level) == 0 else "/".join([".."] * level)

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
                "ast not set yet. Consider using parasite.apps.read_md_to_ast"
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

        TODO: handle AST mutation
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
    def previewimage(self) -> Optional[Url]:
        res = self.ast.get_metadata("previewimage")
        return None if res is None else Url(res)

    @property
    def status(self) -> str:
        return self.ast.get_metadata("status", "")

    @property
    def is_draft(self) -> bool:
        return self.status == "draft"


@dataclass
class Post(Page):
    @property
    def dict_ast(self) -> dict[str, Any]:
        dict_ast = super().dict_ast
        dict_ast["time"] = self.time
        return dict_ast

    @property
    def date(self) -> str:
        date = self.ast.get_metadata("date")
        if date is None:
            raise ValueError(f"The following post has no date: {self.path}")
        return date

    @cached_property
    def time(self) -> datetime:
        time = datetime.strptime(self.date, self.date_format)
        time = time.replace(tzinfo=ZoneInfo(key=self.timezone))
        return time



@dataclass
class Pages:
    pages: Sequence[Page]
    page_class: ClassVar[type] = Page

    @classmethod
    def from_file_system(
        cls: type[PagesLike],
        path: Path,
        out_path: Path,
        ext: str,
        template: Optional[Path],
        excludes: list[str] = [],
        timezone: str = r"America/Los_Angeles",
        pretty_urls: Union[bool, Callable[[Path, str], Path]] = True,
        date_format: str = r"%Y-%m-%d",
        default_lang: str = "en",
        options: dict[str, Any] = {},
    ) -> PagesLike:
        path = Path(path)
        out_path = Path(out_path)
        return cls(
            [
                cls.page_class(
                    path_,
                    path,
                    out_path,
                    template,
                    timezone=timezone,
                    pretty_urls=pretty_urls,
                    date_format=date_format,
                    default_lang=default_lang,
                    options=options,
                )
                for path_ in path.glob(f"**/*{ext}")
                if not any(path_.match(exclude) for exclude in excludes)
            ]
        )

    @classmethod
    def from_config(
        cls: type[PagesLike],
        config: Config,
    ) -> PagesLike:
        pageses: list[Page] = []
        for path, out_path, ext, template, excludes in (
            config.pages if cls is Pages else config.posts
        ):
            options = {
                "show_previewimage_in_post": config.show_previewimage_in_post,
                "header_includes": config.header_includes,
                "include_before": config.include_before,
                "include_after": config.include_after,
                "script_include_after": config.script_include_after,
                "mathjax_config": config.mathjax_config,
                "search_form": config.search_form,
                "content_footer": config.content_footer,
                "blog_title": config.blog_title,
                "nav": config.nav_includes,
                "pandoc_options": config.pandoc_output_options,
                "css": config.css,
                "js": config.js,
                "logo_url": Url(config.logo_url) if config.logo_url else None,
                "panflute_filters": config.panflute_output_filters,
                "html_filters": config.html_filters,
            }
            pageses += cls.from_file_system(
                Path(path),
                Path(out_path),
                ext,
                template,
                excludes=excludes,
                timezone=config.timezone,
                pretty_urls=config.pretty_urls[ext],
                date_format=config.date_format,
                default_lang=config.default_lang,
                options=options,
            ).pages
        return cls(pageses)

    @property
    def _dict(self) -> List[dict[str, Any]]:
        return [page._dict for page in self.pages]

    @property
    def dict_ast(self) -> List[dict[str, Any]]:
        return [page.dict_ast for page in self.pages]

    @cached_property
    def dataframe(self) -> pd.DataFrame:
        import pandas as pd

        return pd.DataFrame(self._dict)

    @cached_property
    def dataframe_ast(self) -> pd.DataFrame:
        import pandas as pd

        return pd.DataFrame(self.dict_ast)


@dataclass
class Posts(Pages):
    pages: Sequence[Post]
    page_class: ClassVar[type] = Post

    # AST's derivatives

    def sort(self) -> None:
        self.pages = sorted(self.pages, key=lambda page: page.time, reverse=True)

    @cached_property
    def tags(self) -> Dict[str, List[Post]]:
        res = defaultdict(list)
        for page in self.pages:
            for tag in page.tags:
                res[tag].append(page)
        return res

    @cached_property
    def categories(self) -> Dict[str, List[Post]]:
        """Posts by category; a category also lists its subcategories' posts."""
        res = defaultdict(list)
        for page in self.pages:
            parts = page.category.split("/") if page.category else []
            for i in range(1, len(parts) + 1):
                res["/".join(parts[:i])].append(page)
        return dict(sorted(res.items()))
