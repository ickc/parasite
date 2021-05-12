from __future__ import annotations

from collections import Counter, defaultdict
from itertools import chain
from pathlib import Path
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING
from typing import Final
from logging import getLogger

import panflute as pf

from .apps import read_md_to_ast, app_read_md_to_ast, app_post_to_html, InputPath

if TYPE_CHECKING:
    from typing import List, Optional, Tuple, Dict

    import pandas as pd

logger = getLogger('parasite')


@dataclass
class Page:
    path: InputPath
    base_path: Path
    out_base_path: Path
    template: InputPath
    pretty_urls: bool = True

    def __post_init__(self):
        # special casing 404
        if self.pretty_urls and str(self.out_path) == '404/index.html':
            logger.info(f'Forcing non-pretty URL for {self.path}.')
            self.pretty_urls = False
            del self.out_path

    @property
    def dict(self) -> dict:
        '''A dict representation of self including all attributes and properties

        Primarily for dataframe
        '''
        res = vars(self).copy()
        res['out_path'] = self.out_path
        res['url'] = self.url
        return res

    @cached_property
    def out_path(self) -> Path:
        out_path = self.out_base_path / self.path.relative_to(self.base_path)
        if self.pretty_urls:
            out_path = out_path.parent / out_path.stem / 'index.html'
        else:
            out_path = out_path.parent / (out_path.stem + '.html')
        return out_path

    @cached_property
    def url(self) -> Path:
        out_path = self.out_path
        if self.pretty_urls:
            return out_path.parent
        else:
            return out_path

    @cached_property
    def categories(self) -> Tuple[str, ...]:
        return self.path.relative_to(self.base_path).parent.parts

    @cached_property
    def level(self) -> int:
        categories = self.categories
        n = len(categories)
        return n + 1 if self.pretty_urls else n

    @cached_property
    def root(self) -> str:
        level = self.level
        if level == 0:
            return '.'
        else:
            return '/'.join(['..'] * level)

    # AST & its derivatives

    def get_ast(self):
        self._ast = read_md_to_ast(self.path)

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
    def prev(self):
        return None

    @property
    def next(self):
        return None


@dataclass
class Post(Page):

    @property
    def dict(self) -> dict:
        res = super().dict
        res['categories'] = self.categories
        return res

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
    def prev(self) -> Optional[Tuple[Path, Optional[str]]]:
        return getattr(self, '_prev', None)

    @prev.setter
    def prev(self, data: Tuple[Path, Optional[str]]):
        self._prev = data

    @prev.deleter
    def prev(self):
        del self._prev

    @property
    def next(self) -> Optional[Tuple[Path, Optional[str]]]:
        return getattr(self, '_next', None)

    @next.setter
    def next(self, data: Tuple[Path, Optional[str]]):
        self._next = data

    @next.deleter
    def next(self):
        del self._next


@dataclass
class Pages:
    path: Path
    out_path: Path
    ext: str
    template: InputPath
    pretty_urls: bool = True
    page_class: Final = Page

    def __post_init__(self):
        self.path = Path(self.path)
        self.out_path = Path(self.out_path)
        self.template = InputPath(self.template)

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
            app_read_md_to_ast(page.path)
            for page in pages
        ]
        for page, future in zip(pages, futures):
            page.ast = future.result()

    def future_output_pages(
        self,
        header_includes: str = '',
        include_before: str = '',
        include_after: str = '',
        mathjax_config: str = '',
        search_form: str = '',
        content_footer: str = '',
        blog_title: str = '',
        nav: str = '',
        pandoc_options_dict: Dict[str, List[str]] = defaultdict(list),
        css_dict: Dict[str, List[str]] = defaultdict(list),
        output_dir: Path = Path('output'),
    ) -> list:
        pages = self.pages
        pandoc_options = pandoc_options_dict[self.ext]
        css = css_dict[self.ext]

        return [
            app_post_to_html(
                page.ast,
                page.out_path,
                page.root,
                page.template,
                page.prev,
                page.next,
                header_includes=header_includes,
                include_before=include_before,
                include_after=include_after,
                mathjax_config=mathjax_config,
                search_form=search_form,
                content_footer=content_footer,
                blog_title=blog_title,
                nav=nav,
                pandoc_options=pandoc_options,
                css=css,
                output_dir=output_dir,
            )
            for page in pages
        ]

    def exec(
        self,
        header_includes: str = '',
        include_before: str = '',
        include_after: str = '',
        mathjax_config: str = '',
        search_form: str = '',
        content_footer: str = '',
        blog_title: str = '',
        nav: str = '',
        pandoc_options_dict: Dict[str, List[str]] = defaultdict(list),
        css_dict: Dict[str, List[str]] = defaultdict(list),
        output_dir: Path = Path('output'),
    ):
        """Run the site generator pipeline.
        """
        futures = self.future_output_pages(
            header_includes,
            include_before,
            include_after,
            mathjax_config,
            search_form,
            content_footer,
            blog_title,
            nav,
            pandoc_options_dict=pandoc_options_dict,
            css_dict=css_dict,
            output_dir=output_dir,
        )
        for future in futures:
            future.result()


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

    @cached_property
    def tag_ast(self) -> pf.elements.Doc:
        tags_counts = self.tags_counts

        meta = {
            'title': 'Tags and Categories',
        }
        # lis = []
        # for tag, count in tags_counts.items():
        #     lis.append(
        #         pf.ListItem(
        #             pf.Plain(
        #                 pf.Link(
        #                     pf.Str(tag),
        #                     url=tag + '/',
        #                     classes=['list-inline-item', 'reference', 'badge', 'badge-secondary']
        #                 )
        #             )
        #         )
        #     )
        # tag_ast = pf.Doc(
        #     pf.Header(pf.Str('Tags')),
        #     # pf.Div(pf.BulletList(*lis), classes=['list-inline']),
        #     pf.BulletList(*lis, classes=['list-inline']),
        #     metadata=meta,
        # )

        # scale
        counts = tags_counts.values()
        font_size_min = 70
        font_size_max = 280
        min_ = min(counts)
        max_ = max(counts)
        m = (font_size_max - font_size_min) / (max_ - min_)
        c = font_size_min - m * min_

        res = ['<ul class="list-inline">']
        for tag, count in tags_counts.items():
            font_size = m * count + c
            res.append(f'<li class="list-inline-item"><a class="reference badge badge-secondary" href="{tag}/" style="font-size: {font_size}% !important;">{tag}</a></li>')
        res.append('</ul>')
        tag_ast = pf.Doc(
            pf.Header(pf.Str('Tags')),
            pf.RawBlock(''.join(res), format='html'),
            metadata=meta,
        )
        return tag_ast

    def get_neighbor_urls(self):
        pages = self.pages

        prev_page = pages[0]
        prev = (prev_page.url, prev_page.title)
        for i in range(1, len(pages)):
            page = pages[i]
            curr = (page.url, page.title)

            prev_page.next = curr
            page.prev = prev

            prev_page = page
            prev = curr

    def exec(
        self,
        header_includes: str = '',
        include_before: str = '',
        include_after: str = '',
        mathjax_config: str = '',
        search_form: str = '',
        content_footer: str = '',
        blog_title: str = '',
        nav: str = '',
        pandoc_options_dict: Dict[str, List[str]] = defaultdict(list),
        css_dict: Dict[str, List[str]] = defaultdict(list),
        output_dir: Path = Path('output'),
    ):
        """Run the site generator pipeline.
        """
        futures = self.future_output_pages(
            header_includes,
            include_before,
            include_after,
            mathjax_config,
            search_form,
            content_footer,
            blog_title,
            nav,
            pandoc_options_dict=pandoc_options_dict,
            css_dict=css_dict,
            output_dir=output_dir,
        )

        pandoc_options = pandoc_options_dict[self.ext]
        css = css_dict[self.ext]
        # tags
        futures.append(app_post_to_html(
            self.tag_ast,
            'categories/index.html',
            '..',
            self.template,
            None,
            None,
            header_includes=header_includes,
            include_before=include_before,
            include_after=include_after,
            mathjax_config=mathjax_config,
            search_form=search_form,
            content_footer=content_footer,
            blog_title=blog_title,
            nav=nav,
            pandoc_options=pandoc_options,
            css=css,
            output_dir=output_dir,
        ))

        for future in futures:
            future.result()
