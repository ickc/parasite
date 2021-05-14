"""Some functions for pipelines

all functions should be imported inside functions for parsl
"""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

import panflute as pf
from panflute.tools import convert_text

if TYPE_CHECKING:
    from typing import Optional, List, Tuple, Dict, Callable

    from urlpath import URL as Url


def read_md_to_ast(inputs: List[Path] = []) -> pf.elements.Doc:
    """Read from markdown to panflute AST
    """
    assert len(inputs) == 1
    path = inputs[0]

    with open(path, 'r') as f:
        return convert_text(f.read(), standalone=True)


def get_teaser(doc: pf.elements.Doc) -> pf.containers.ListContainer:
    content = doc.content
    for i, item in enumerate(content):
        if (type(item) == pf.RawBlock) and (item.text == '<!-- more -->'):
            break
    return content[:i]


def read_md_to_ast_with_teaser(inputs: List[Path] = []) -> Tuple[pf.elements.Doc, pf.containers.ListContainer]:
    ast = read_md_to_ast(inputs)
    teaser = get_teaser(ast)
    return ast, teaser


def post_to_html(
    ast: pf.elements.Doc,
    root: str,
    prev: Optional[Tuple[Url, Optional[str]]],
    next: Optional[Tuple[Url, Optional[str]]],
    lang: str,
    ext: str,
    inputs: List[Path] = [],   # template
    outputs: List[Path] = [],  # out_path
    header_includes: Optional[Callable[[str, str, str], str]] = None,
    include_before: Optional[Callable[[str, str, str], str]] = None,
    include_after: Optional[Callable[[str, str, str], str]] = None,
    mathjax_config: str = '',
    search_form: Optional[Callable[[str, str, str], str]] = None,
    content_footer: Optional[Callable[[str, str, str], str]] = None,
    blog_title: Dict[str, str] = {},
    nav: Optional[Callable[[str, str, str], str]] = None,
    pandoc_options: Optional[Callable[[str, str], List[str]]] = None,
    css: Optional[Callable[[str, str], List[str]]] = None,
):
    """
    warning: AST is currently mutated
    """
    assert len(inputs) <= 1
    assert len(outputs) == 1
    template = inputs[0] if inputs else None
    out_path = outputs[0]

    ast.metadata['header-includes'] = pf.RawBlock(header_includes(lang, ext, '.html').format(root=root))
    ast.metadata['include-before'] = pf.RawBlock(include_before(lang, ext, '.html').format(root=root))
    ast.metadata['include-after'] = pf.RawBlock(include_after(lang, ext, '.html').format(root=root))
    if content_footer:
        ast.metadata['content-footer'] = pf.RawBlock(content_footer(lang, ext, '.html').format(root=root))
    if mathjax_config:
        ast.metadata['mathjax-config'] = pf.RawBlock(mathjax_config)
    if search_form:
        ast.metadata['search-form'] = pf.RawBlock(search_form(lang, ext, '.html').format(root=root))
    if blog_title:
        ast.metadata['title-prefix'] = pf.RawBlock(blog_title[lang])
    if nav:
        ast.metadata['nav'] = pf.RawBlock(nav(lang, ext, '.html').format(root=root))
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

    css_options = [f"--css={c.format(root=root)}" for c in css(ext, '.html')]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    other_options = [f'--output={out_path}']
    if template is not None:
        other_options.append(f'--template={template}')

    convert_text(ast, input_format='panflute', output_format='html', standalone=True, extra_args=pandoc_options(ext, '.html') + css_options + other_options)
