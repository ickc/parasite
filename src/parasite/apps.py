"""Some functions for pipelines

all functions should be imported inside functions for parsl
"""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
import os

import panflute
from parsl import python_app
from parsl.dataflow.memoization import id_for_memo

if TYPE_CHECKING:
    from typing import Optional, List, Tuple


# doesn't work: https://bugs.python.org/issue24132
# class InputPath(Path):
#     pass

class InputPath:

    def __init__(self, path: str):
        self.path = Path(path)

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return repr(self.path)

    def __truediv__(self, other):
        return self.path / other


def read_md_to_ast(path: InputPath) -> panflute.elements.Doc:
    """Read from markdown to panflute AST
    """
    from panflute.tools import convert_text

    with open(path, 'r') as f:
        return convert_text(f.read(), standalone=True)


def post_to_html(
    ast: panflute.elements.Doc,
    out_path: Path,
    root: str,
    template: InputPath,
    prev: Optional[Tuple[Path, Optional[str]]],
    next: Optional[Tuple[Path, Optional[str]]],
    header_includes: str = '',
    include_before: str = '',
    include_after: str = '',
    mathjax_config: str = '',
    search_form: str = '',
    content_footer: str = '',
    blog_title: str = '',
    nav: str = '',
    pandoc_options: List[str] = [],
    css: List[str] = [],
    output_dir: Path = Path('output'),
):
    """
    warning: AST is currently mutated
    """
    ast.metadata['header-includes'] = panflute.RawBlock(header_includes.format(root=root))
    ast.metadata['include-before'] = panflute.RawBlock(include_before)
    ast.metadata['include-after'] = panflute.RawBlock(include_after)
    if content_footer:
        ast.metadata['content-footer'] = panflute.RawBlock(content_footer)
    if mathjax_config:
        ast.metadata['mathjax-config'] = panflute.RawBlock(mathjax_config)
    if search_form:
        ast.metadata['search-form'] = panflute.RawBlock(search_form.format(root=root))
    if blog_title:
        ast.metadata['title-prefix'] = panflute.RawBlock(blog_title)
    if nav:
        ast.metadata['nav'] = panflute.RawBlock(nav.format(root=root))
    if root:
        ast.metadata['root'] = root
    if prev is not None:
        ast.metadata['prev-url'] = str(root / prev[0])
        title = prev[1]
        if title is not None:
            ast.metadata['prev-title'] = title
    if next is not None:
        ast.metadata['next-url'] = str(root / next[0])
        title = next[1]
        if title is not None:
            ast.metadata['next-title'] = title

    css_options = [f"--css={root + c if c.startswith('/') else c}" for c in css]

    other_options = [
        f'--output={Path(output_dir) / out_path}',
        f'--template={template}',
    ]

    panflute.tools.convert_text(ast, input_format='panflute', output_format='html', standalone=True, extra_args=pandoc_options + css_options + other_options)


@id_for_memo.register(Path)
def id_for_memo_path(path: Path, output_ref: bool = False) -> bytes:
    return id_for_memo(str(path))


@id_for_memo.register(InputPath)
def id_for_memo_inputpath(path: Path, output_ref: bool = False) -> bytes:
    return id_for_memo((str(path), os.path.getmtime(str(path))))


@id_for_memo.register(panflute.elements.Doc)
def id_for_memo_doc(doc: panflute.elements.Doc, output_ref: bool = False) -> bytes:
    return id_for_memo(doc.to_json())


app_read_md_to_ast = python_app(read_md_to_ast, cache=True)
app_post_to_html = python_app(post_to_html, cache=True)


def _nav(
    data: Tuple[Tuple[str, str], Tuple[Tuple[str, str], str]],
    ul_class: str = "navbar-nav nav-fill d-flex w-100",
    li_class: str = "nav-item",
    a_class: str = "nav-link",
    dropdown_li_class: str = "nav-item dropdown",
    dropdown_a_class: str = "nav-link dropdown-toggle",
    dropdown_a_attrs: str = 'data-toggle="dropdown" aria-haspopup="true" aria-expanded="false"',
    inner_ul_class: str = "dropdown-menu",
    inner_li_class: str = "dropdown-item",
    inner_a_class: str = "dropdown-item",
) -> List[str]:
    res = [f'<ul class="{ul_class}">']
    for datum in data:
        type_ = type(datum[0])
        if type_ == str:
            url, title = datum
            res.append(f'<li class="{li_class}"><a href="{{root}}{url}" class="{a_class}">{title}</a></li>')
        elif type_ == tuple:
            inner_data, title = datum
            res.append(f'<li class="{dropdown_li_class}"><a href="#" class="{dropdown_a_class}" {dropdown_a_attrs}>{title}</a>')
            res += _nav(inner_data, ul_class=inner_ul_class, li_class=inner_li_class, a_class=inner_a_class)
            res.append('</li>')
        else:
            raise TypeError('Unknown type inside nav data: {type_}.')
    res.append('</ul>')
    return res


def nav(data: Tuple[Tuple[str, str], Tuple[Tuple[str, str]]]) -> str:
    return ''.join(_nav(data))
