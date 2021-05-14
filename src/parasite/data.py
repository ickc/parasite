from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING
from typing import Final
from logging import getLogger
from datetime import datetime

import panflute as pf
from urlpath import URL as Url

from .apps import read_md_to_ast, get_teaser

if TYPE_CHECKING:
    from typing import List, Optional, Tuple, Callable, Union, Dict

    import pandas as pd

logger = getLogger('parasite')


@dataclass
class Page:
    path: Path
    base_path: Path
    out_base_path: Path
    template: Optional[Path]
    pretty_urls: Union[bool, Callable[[Path, str], Path]] = True
    date_format: str = r'%Y-%m-%d'
    default_lang: str = 'en'
    options: dict = field(default_factory=dict)

    def __post_init__(self):
        # special casing 404
        if self.pretty_urls is True and str(self.out_path) == '404/index.html':
            logger.info(f'Forcing non-pretty URL for {self.path}.')
            self.pretty_urls = False
            del self.out_path

    @property
    def dict(self) -> dict:
        '''A dict representation of self including all attributes and properties

        Primarily for dataframe
        '''
        return {
            # init
            'path': self.path,
            'base_path': self.base_path,
            'out_base_path': self.out_base_path,
            'template': self.template,
            'pretty_urls': self.pretty_urls,
            # property
            'out_path': self.out_path,
            'url': self.url,
            'categories': self.categories,
            'level': self.level,
            'root': self.root,
        }

    @property
    def dict_ast(self) -> dict:
        '''A dict representation of self including the AST derived attributes

        Primarily for dataframe
        '''
        res = self.dict
        res['time'] = self.time
        res['lang'] = self.lang
        for key in self.ast.metadata.content:
            res['ast.' + key] = self.ast.get_metadata(key)
        prev = self.prev
        res['prev.url'] = None if prev is None else prev[0]
        res['prev.title'] = None if prev is None else prev[1]
        next = self.next
        res['next.url'] = None if next is None else next[0]
        res['next.title'] = None if next is None else next[1]
        return res

    @property
    def ext(self) -> str:
        return self.path.suffix

    @cached_property
    def out_path(self) -> Path:
        out_path = self.out_base_path / self.path.relative_to(self.base_path)
        pretty_urls = self.pretty_urls
        if pretty_urls is True:
            out_path = out_path.parent / out_path.stem / 'index.html'
        elif callable(pretty_urls):
            out_path = pretty_urls(out_path.parent, out_path.stem)
        else:
            out_path = out_path.parent / (out_path.stem + '.html')
        return out_path

    @cached_property
    def url(self) -> Url:
        out_path = self.out_path
        if self.pretty_urls is True:
            return Url(str(out_path.parent) + '/')
        else:
            return Url(str(out_path))

    @cached_property
    def categories(self) -> str:
        return '|'.join(self.path.relative_to(self.base_path).parent.parts)

    @cached_property
    def level(self) -> int:
        return len(self.out_path.parent.parts)

    @cached_property
    def root(self) -> str:
        level = self.level
        if level == 0:
            return '.'
        else:
            return '/'.join(['..'] * level)

    # AST & its derivatives

    def get_ast(self):
        self._ast = read_md_to_ast([self.path])

    @property
    def ast(self) -> pf.elements.Doc:
        if not hasattr(self, '_ast'):
            self.get_ast()
        return self._ast

    @ast.setter
    def ast(self, doc: pf.elements.Doc):
        self._ast = doc

    @ast.deleter
    def ast(self):
        del self._ast

    @property
    def title(self) -> Optional[str]:
        return self.ast.get_metadata('title')

    @property
    def author(self) -> Optional[str]:
        return self.ast.get_metadata('author')

    @property
    def lang(self) -> str:
        lang = self.ast.get_metadata('lang')
        if lang is None:
            lang = self.default_lang
            self.ast.metadata['lang'] = lang
        return lang

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
        dict_ast['teaser'] = self.teaser
        return dict_ast

    # AST's derivatives

    def get_teaser(self):
        self._ast = get_teaser(self.ast)

    @property
    def teaser(self) -> pf.elements.Doc:
        if not hasattr(self, '_teaser'):
            self.get_teaser()
        return self._teaser

    @teaser.setter
    def teaser(self, doc: pf.containers.ListContainer):
        self._teaser = doc

    @teaser.deleter
    def teaser(self):
        del self._teaser

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
    def previewimage(self) -> Optional[str]:
        return self.ast.get_metadata('previewimage')

    @cached_property
    def time(self) -> Optional[datetime]:
        date = self.date
        return None if date is None else datetime.strptime(date, self.date_format)

    @property
    def prev(self) -> Optional[Tuple[Url, Optional[str]]]:
        return getattr(self, '_prev', None)

    @prev.setter
    def prev(self, data: Tuple[Url, Optional[str]]):
        self._prev = data

    @prev.deleter
    def prev(self):
        del self._prev

    @property
    def next(self) -> Optional[Tuple[Url, Optional[str]]]:
        return getattr(self, '_next', None)

    @next.setter
    def next(self, data: Tuple[Url, Optional[str]]):
        self._next = data

    @next.deleter
    def next(self):
        del self._next


@dataclass
class Pages:
    pages: List[Page]
    page_class: Final = Page

    @classmethod
    def from_file_system(
        cls,
        path: Path,
        out_path: Path,
        ext: str,
        template: Optional[Path],
        pretty_urls: Union[bool, Callable[[Path, str], Path]] = True,
        date_format: str = r'%Y-%m-%d',
        default_lang: str = 'en',
        options: dict = {},
    ):
        path = Path(path)
        out_path = Path(out_path)
        if template is not None:
            template = Path(template)
        return cls(
            [
                cls.page_class(
                    path_,
                    path,
                    out_path,
                    template,
                    pretty_urls=pretty_urls,
                    date_format=date_format,
                    default_lang=default_lang,
                    options=options,
                )
                for path_ in Path(path).glob(f'**/*{ext}')
            ]
        )

    @property
    def dict(self) -> List[dict]:
        return [page.dict for page in self.pages]

    @property
    def dict_ast(self) -> List[dict]:
        return [page.dict_ast for page in self.pages]

    @cached_property
    def dataframe(self) -> pd.DataFrame:
        import pandas as pd

        return pd.DataFrame(self.dict)

    @cached_property
    def dataframe_ast(self) -> pd.DataFrame:
        import pandas as pd

        return pd.DataFrame(self.dict_ast)


@dataclass
class Posts(Pages):
    pages: List[Post]
    page_class: Final = Post

    # AST's derivatives

    def sort(self):
        self.pages.sort(key=lambda page: page.time, reverse=True)

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
