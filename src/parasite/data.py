from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cached_property
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import panflute as pf
from panflute.tools import convert_text
from urlpath import URL as Url

from .apps import get_teaser

if TYPE_CHECKING:
    from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

    import pandas as pd

logger = getLogger(__name__)


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
    options: dict = field(default_factory=dict)

    def __post_init__(self):
        # special casing 404
        if self.pretty_urls is True and str(self.out_path) == "404/index.html":
            logger.debug(f"Forcing non-pretty URL for {self.path}.")
            self.pretty_urls = False
            del self.out_path

    @property
    def _dict(self) -> dict:
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
            "categories": self.categories,
            "level": self.level,
            "root": self.root,
        }

    @property
    def dict_ast(self) -> dict:
        """A dict representation of self including the AST derived attributes

        Primarily for dataframe
        """
        res = self._dict
        res["lang"] = self.lang
        for key in self.ast.metadata.content:
            res["ast." + key] = self.ast.get_metadata(key)
        prev = self.prev
        res["prev.url"] = None if prev is None else prev[0]
        res["prev.title"] = None if prev is None else prev[1]
        next = self.next
        res["next.url"] = None if next is None else next[0]
        res["next.title"] = None if next is None else next[1]
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
        if self.pretty_urls is True:
            return Url(str(out_path.parent) + "/")
        else:
            return Url(str(out_path))

    @cached_property
    def categories(self) -> str:
        return "|".join(self.path.relative_to(self.base_path).parent.parts)

    @cached_property
    def level(self) -> int:
        return len(self.out_path.parent.parts)

    @cached_property
    def root(self) -> str:
        level = self.level
        if level == 0:
            return "."
        else:
            return "/".join([".."] * level)

    @cached_property
    def mtime(self) -> datetime:
        return datetime.fromtimestamp(os.path.getmtime(self.path), timezone.utc)

    @cached_property
    def committed_date(self) -> datetime:
        import git

        repo = git.Repo(".")
        try:
            commit = next(repo.iter_commits(paths=self.path, max_count=1))
            return datetime.fromtimestamp(commit.committed_date, timezone.utc)
        except StopIteration:
            logger.warn(
                f"Cannot obtain committed date for {self.path}, returning mtime"
                " instead."
            )
            return self.mtime

    @cached_property
    def committed_date_str(self) -> str:
        return self.committed_date.strftime(r"%Y-%m-%d")

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
    def ast(self, doc: pf.elements.Doc):
        self._ast = doc

    @ast.deleter
    def ast(self):
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
            self.ast, input_format="panflute", output_format="html", standalone=False
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
    def previewimage(self) -> Optional[Url]:
        res = self.ast.get_metadata("previewimage")
        if res is not None:
            return Url(res)
        return None

    @property
    def status(self) -> str:
        return self.ast.get_metadata("status", "")

    @property
    def is_draft(self) -> bool:
        return self.status == "draft"

    @property
    def prev(self):
        return None

    @property
    def next(self):
        return None


@dataclass
class Post(Page):
    @property
    def dict_ast(self) -> dict:
        dict_ast = super().dict_ast
        dict_ast["time"] = self.time
        dict_ast["teaser"] = self.teaser
        return dict_ast

    # AST's derivatives

    def get_teaser(self):
        self._ast = get_teaser(self.ast)

    @property
    def teaser(self) -> pf.elements.Doc:
        if not hasattr(self, "_teaser"):
            self.get_teaser()
        return self._teaser

    @teaser.setter
    def teaser(self, doc: pf.containers.ListContainer):
        self._teaser = doc

    @teaser.deleter
    def teaser(self):
        del self._teaser

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

    @property
    def prev(self) -> Optional[Tuple[Url, Optional[str]]]:
        return getattr(self, "_prev", None)

    @prev.setter
    def prev(self, data: Tuple[Url, Optional[str]]):
        self._prev = data

    @prev.deleter
    def prev(self):
        del self._prev

    @property
    def next(self) -> Optional[Tuple[Url, Optional[str]]]:
        return getattr(self, "_next", None)

    @next.setter
    def next(self, data: Tuple[Url, Optional[str]]):
        self._next = data

    @next.deleter
    def next(self):
        del self._next


@dataclass
class Pages:
    pages: Sequence[Page]
    page_class: ClassVar[type] = Page

    @classmethod
    def from_file_system(
        cls,
        path: Path,
        out_path: Path,
        ext: str,
        template: Optional[Path],
        timezone: str = r"America/Los_Angeles",
        pretty_urls: Union[bool, Callable[[Path, str], Path]] = True,
        date_format: str = r"%Y-%m-%d",
        default_lang: str = "en",
        options: dict = {},
    ):
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
                for path_ in Path(path).glob(f"**/*{ext}")
            ]
        )

    @property
    def _dict(self) -> List[dict]:
        return [page._dict for page in self.pages]

    @property
    def dict_ast(self) -> List[dict]:
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

    def sort(self):
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
        res = defaultdict(list)
        for page in self.pages:
            res[page.categories].append(page)
        return res

    def get_neighbor_urls(self):
        pages = self.pages

        next_page = pages[0]
        next = (next_page.url, next_page.title)
        for i in range(1, len(pages)):
            page = pages[i]
            curr = (page.url, page.title)

            next_page.prev = curr
            page.next = next

            next_page = page
            next = curr
