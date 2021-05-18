"""Some functions for pipelines

all functions should be imported inside functions for parsl
"""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

import panflute as pf
from panflute.tools import convert_text

from .panflute_filters import meta_append

if TYPE_CHECKING:
    from typing import Optional, List, Tuple, Dict, Callable

    from urlpath import URL as Url


def read_md_to_ast(
    pandoc_options: Callable[[str], List[str]],
    panflute_filters: Callable[[str], List[Callable]],
    inputs: List[Path] = [],
) -> pf.elements.Doc:
    """Read from markdown to panflute AST
    """
    assert len(inputs) == 1
    path = inputs[0]
    ext = path.suffix

    with open(path, 'r') as f:
        doc = convert_text(f.read(), standalone=True, extra_args=pandoc_options(ext))

    fs = panflute_filters(ext)
    if fs:
        pf.io.run_filters(fs, doc=doc)

    return doc


def get_teaser(doc: pf.elements.Doc) -> pf.containers.ListContainer:
    content = doc.content
    for i, item in enumerate(content):
        if (type(item) == pf.RawBlock) and (item.text == '<!-- more -->'):
            break
    return content[:i]


def read_md_to_ast_with_teaser(
    pandoc_options: Callable[[str], List[str]],
    panflute_filters: Callable[[str], List[Callable]],
    inputs: List[Path] = [],
) -> Tuple[pf.elements.Doc, pf.containers.ListContainer]:
    ast = read_md_to_ast(
        pandoc_options=pandoc_options,
        panflute_filters=panflute_filters,
        inputs=inputs
    )
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
    show_previewimage_in_post: bool = True,
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
    logo_url: Optional[Url] = None,
    panflute_filters: Optional[Callable[[str, str], List[Callable]]] = None,
    html_filters: List[Callable[[str], str]] = [],
):
    """
    warning: AST is currently mutated
    """
    assert len(inputs) <= 1
    assert len(outputs) == 1
    template = inputs[0] if inputs else None
    out_path = outputs[0]

    meta_append(ast.metadata, 'header-includes', header_includes(lang, ext, '.html').format(root=root))
    meta_append(ast.metadata, 'include-before', include_before(lang, ext, '.html').format(root=root))
    meta_append(ast.metadata, 'include-after', include_after(lang, ext, '.html').format(root=root))

    if show_previewimage_in_post:
        ast.metadata['show-previewimage-in-post'] = 'true'
    if content_footer:
        ast.metadata['content-footer'] = pf.RawBlock(content_footer(lang, ext, '.html').format(root=root))
    if mathjax_config:
        ast.metadata['mathjax-config'] = pf.RawBlock(mathjax_config)
    if search_form:
        ast.metadata['search-form'] = pf.RawBlock(search_form(lang, ext, '.html').format(root=root))
    if blog_title:
        ast.metadata['title-prefix'] = pf.RawBlock(blog_title[lang])
    if logo_url:
        ast.metadata['logo-url'] = str(logo_url)
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

    extra_args = pandoc_options(ext, '.html') + [f"--css={c.format(root=root)}" for c in css(ext, '.html')]
    if template is not None:
        extra_args.append(f'--template={template}')

    out_path.parent.mkdir(parents=True, exist_ok=True)

    fs = panflute_filters(ext, '.html')
    if fs:
        pf.io.run_filters(fs, doc=ast)
    if not html_filters:
        extra_args.append(f'--output={out_path}')
    html = convert_text(ast, input_format='panflute', output_format='html', standalone=True, extra_args=extra_args)
    if html_filters:
        for html_filter in html_filters:
            html = html_filter(html)
        with open(out_path, 'w') as f:
            f.write(html)
