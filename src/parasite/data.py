from __future__ import annotations

from collections import Counter
from itertools import chain
from pathlib import Path
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING
from datetime import datetime
import os
from typing import Final

import panflute

from .apps import read_md_to_ast, app_read_md_to_ast, app_post_to_html

if TYPE_CHECKING:
    from typing import List, Optional, Tuple, Dict

    import pandas as pd


@dataclass
class Page:
    path: Path
    base_path: Path
    out_base_path: Path
    template: Path
    pretty_urls: bool = True

    @property
    def dict(self) -> dict:
        '''A dict representation of self including all attributes and properties

        Primarily for dataframe
        '''
        res = vars(self).copy()
        res['mtime'] = self.mtime
        res['out_path'] = self.out_path
        res['out_url'] = self.out_url
        return res

    @property
    def mtime(self) -> datetime:
        return datetime.fromtimestamp(os.path.getmtime(self.path))

    @cached_property
    def out_path(self) -> Path:
        out_path = self.out_base_path / self.path.relative_to(self.base_path)
        if self.pretty_urls:
            out_path = out_path.parent / out_path.stem / 'index.html'
        else:
            out_path = out_path.parent / (out_path.stem + '.html')
        return out_path

    @cached_property
    def out_url(self) -> Path:
        out_path = self.out_path
        if self.pretty_urls:
            return out_path.parent
        else:
            return out_path

    # AST & its derivatives

    def get_ast(self):
        self._ast = read_md_to_ast(self.path)

    @property
    def ast(self) -> panflute.elements.Doc:
        if not hasattr(self, '_ast'):
            self.get_ast()
        return self._ast

    @ast.setter
    def ast(self, doc: panflute.elements.Doc):
        self._ast = doc

    @ast.deleter
    def ast(self):
        del self._ast


@dataclass
class Post(Page):

    @property
    def dict(self) -> dict:
        res = super().dict
        res['categories'] = self.categories
        return res

    @cached_property
    def categories(self) -> Tuple[str, ...]:
        return self.path.relative_to(self.base_path).parent.parts

    # AST's derivatives

    @property
    def tags(self) -> List[str]:
        tags = self.ast.get_metadata('tags')
        if tags is None:
            tags = []
        return tags

    @property
    def date(self) -> Optional[str]:
        return self.ast.get_metadata('date')

    @property
    def tags_counts(self) -> List[int]:
        try:
            return self._tags_counts
        except AttributeError:
            raise RuntimeError('Tags counts not generated yet. You probably forgot to run Posts.tags_counts first.')

    @tags_counts.setter
    def tags_counts(self, counts: Counter):
        self._tags_counts = [counts[tag] for tag in self.tags]

    @tags_counts.deleter
    def tags_counts(self):
        del self._tags_counts

    @property
    def prev_url(self) -> Path:
        return getattr(self, '_prev_url', None)

    @prev_url.setter
    def prev_url(self, url: Path):
        self._prev_url = url

    @prev_url.deleter
    def prev_url(self):
        del self._prev_url

    @property
    def next_url(self) -> Path:
        return getattr(self, '_next_url', None)

    @next_url.setter
    def next_url(self, url: Path):
        self._next_url = url

    @next_url.deleter
    def next_url(self):
        del self._next_url


@dataclass
class Pages:
    path: Path
    out_path: Path
    ext: str
    template: Path
    pretty_urls: bool = True
    page_class: Final = Page

    def __post_init__(self):
        self.path = Path(self.path)
        self.out_path = Path(self.out_path)
        self.template = Path(self.template)

    @property
    def dict(self) -> List[dict]:
        return [page.dict for page in self.pages]

    @cached_property
    def pages(self) -> list:
        return [self.page_class(path, self.path, self.out_path, self.template, pretty_urls=self.pretty_urls) for path in Path(self.path).glob(f'**/*{self.ext}')]

    @cached_property
    def dataframe(self) -> pd.DataFrame:
        import pandas as pd

        return pd.DataFrame(self.dict)

    # AST & its derivatives

    def get_asts(self):
        pages = self.pages

        # str is to make them hashable
        futures = [
            app_read_md_to_ast(
                page.path,
                page.mtime,
            )
            for page in pages
        ]
        for page, future in zip(pages, futures):
            page.ast = future.result()


@dataclass
class Posts(Pages):
    page_class: Final = Post

    # AST's derivatives

    def sort(self):
        self.pages.sort(key=lambda page: page.date)

    @cached_property
    def tags_counts(self) -> Counter:
        counts = Counter(chain(*(page.tags for page in self.pages)))
        for page in self.pages:
            page.tags_counts = counts
        return counts

    def get_neighbor_urls(self):
        pages = self.pages
        n = len(pages)

        if n > 1:
            i = 0
            page = pages[i]
            page.next_url = pages[i + 1].out_url

            for i, page in enumerate(pages[1:-1]):
                page.prev_url = pages[i - 1].out_url
                page.next_url = pages[i + 1].out_url

            i = n - 1
            page = pages[i]
            page.prev_url = pages[i - 1].out_url

    def exec(
        self,
        header_includes: str = '',
        include_before: str = '',
        include_after: str = '',
        pandoc_options_dict: Dict[str, List[str]] = [],
        output_dir: Path = Path('output'),
    ):
        """Run the site generator pipeline.
        """
        # posts
        posts = self.pages
        pandoc_options = pandoc_options_dict[self.ext]

        futures = [
            app_post_to_html(
                post.ast,
                post.out_path,
                post.template,
                post.tags,
                post.tags_counts,
                post.prev_url,
                post.next_url,
                header_includes=header_includes,
                include_before=include_before,
                include_after=include_after,
                pandoc_options=pandoc_options,
                output_dir=output_dir,
            )
            for post in posts
        ]
        for future in futures:
            future.result()
