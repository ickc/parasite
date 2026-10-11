"""Reading sources and writing pages: the work the pipeline does per page."""

from __future__ import annotations

import re
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import panflute as pf
from panflute.tools import convert_text

from .media import (
    default_image_extension,
    extract_media_options,
    localize_extracted_media,
    rebase_relative_urls,
)
from .panflute_filters import meta_append

if TYPE_CHECKING:
    from typing import Callable, Dict, List, Optional


    from .panflute_filters import PanfluteFilter

logger = getLogger(__name__)

# ANSI escape sequences (colours in notebook outputs), and the C0 controls XML forbids
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def xml_safe(html: str) -> str:
    """Drop what makes a page not well-formed XML: terminal escapes, C0 controls, and
    pandas' <style scoped> (an obsolete attribute without a value)."""
    html = XML_INVALID.sub("", ANSI_ESCAPE.sub("", html))
    return html.replace("<style scoped>", "<style>")


def read_md_to_ast(
    pandoc_options: Callable[[str], List[str]],
    panflute_filters: Callable[[str], list[PanfluteFilter]],
    inputs: List[Path] = [],
    out_dir: Optional[Path] = None,
    output_dir: Path = Path("output"),
    files_folders: Dict[str, str] = {},
    convert_pdf_media: bool = True,
) -> pf.elements.Doc:
    """Read from markdown to panflute AST

    If ``out_dir``, the output directory of the page, is given, embedded media are
    written there, and relative URLs to local files are made to work from the page,
    see :mod:`para.media`.
    """
    assert len(inputs) == 1
    path = inputs[0]
    ext = path.suffix

    with open(path, "r") as f:
        text = f.read()
    input_format = "markdown" if ext == ".md" else ext[1:]
    # comments in a source are notes, not content: and commented-out drafts
    # (`<!-- … -- … -->`) would make the page ill-formed
    options = ["--strip-comments"] + pandoc_options(ext)
    extra_args = options if out_dir is None else options + extract_media_options(ext, out_dir)
    doc = convert_text(
        text, input_format=input_format, standalone=True, extra_args=extra_args
    )
    if out_dir is not None:
        doc = localize_extracted_media(doc, out_dir, convert_pdf=convert_pdf_media)
        doc = rebase_relative_urls(
            doc,
            path,
            out_dir,
            output_dir,
            files_folders,
            image_extension=default_image_extension(options),
            convert_pdf=convert_pdf_media,
        )

    for filter_ in panflute_filters(ext):
        doc = filter_(doc)
    return doc


def post_to_html(
    ast: pf.elements.Doc,
    root: str,
    lang: str,
    ext: str,
    /,
    *,
    inputs: List[Path] = [],  # template
    outputs: List[Path] = [],  # out_path
    show_image_in_post: bool = True,
    header_includes: Callable[[str, str, str], str],
    include_before: Callable[[str, str, str], str],
    include_after: Callable[[str, str, str], str],
    script_include_after: Callable[[str, str], str],
    pandoc_options: Callable[[str, str], List[str]],
    panflute_filters: Callable[[str, str], list[PanfluteFilter]],
    js: Callable[[str, str], List[str]],
    css: Callable[[str, str], List[str]],
    mathjax_config: str = "",
    search_form: Optional[Callable[[str, str, str], str]] = None,
    content_footer: Optional[Callable[[str, str, str], str]] = None,
    blog_title: Dict[str, str] = {},
    nav: Optional[Callable[[str, str, str], str]] = None,
    logo_url: Optional[str] = None,
    html_filters: List[Callable[[str], str]] = [],
    years: str = "",
    graph: bool = False,
) -> None:
    """Write ``ast`` as a standalone HTML page.

    It changes ``ast`` (the includes, the output filters): render an AST once, after
    everything that reads it.
    """
    assert len(inputs) <= 1
    assert len(outputs) == 1
    template = inputs[0] if inputs else None
    out_path = outputs[0]

    meta_append(
        ast.metadata,
        "header-includes",
        header_includes(lang, ext, ".html").format(root=root),
    )
    meta_append(
        ast.metadata,
        "include-before",
        include_before(lang, ext, ".html").format(root=root),
    )
    meta_append(
        ast.metadata,
        "include-after",
        include_after(lang, ext, ".html").format(root=root),
    )
    if graph:
        # the post graph: the local graph on every page (it does nothing on a page
        # that is not in the graph), the full one at /graph/
        meta_append(
            ast.metadata,
            "header-includes",
            f'<link rel="stylesheet" href="{root}/sitegraph.css" />',
        )
        meta_append(
            ast.metadata,
            "include-after",
            f'<script src="{root}/sitegraph-local.js" data-src="{root}/graph.json"'
            f' data-page="{root}/graph/" data-after="article" defer="defer"></script>',
        )
    for url in js(ext, ".html"):
        meta_append(ast.metadata, "js-include-after", url.format(root=root))
    meta_append(
        ast.metadata,
        "script-include-after",
        script_include_after(ext, ".html").format(root=root),
    )

    if show_image_in_post:
        ast.metadata["show-image-in-post"] = "true"
    # <meta name="description"> falls back to the subtitle, as listings do
    if "description" not in ast.metadata.content and "subtitle" in ast.metadata.content:
        ast.metadata["description-meta"] = pf.MetaString(pf.stringify(ast.metadata.content["subtitle"]))
    if content_footer:
        ast.metadata["content-footer"] = pf.RawBlock(
            content_footer(lang, ext, ".html").format(root=root, years=years)
        )
    if mathjax_config:
        ast.metadata["mathjax-config"] = pf.RawBlock(mathjax_config)
    if search_form:
        ast.metadata["search-form"] = pf.RawBlock(
            search_form(lang, ext, ".html").format(root=root)
        )
    if blog_title:
        ast.metadata["title-prefix"] = pf.RawBlock(blog_title[lang])
    if logo_url:
        ast.metadata["logo-url"] = str(logo_url)
    if nav:
        ast.metadata["nav"] = pf.RawBlock(nav(lang, ext, ".html").format(root=root))
    if root:
        ast.metadata["root"] = root

    extra_args = pandoc_options(ext, ".html") + [
        f"--css={c.format(root=root)}" for c in css(ext, ".html")
    ]
    if template is not None:
        extra_args.append(f"--template={template}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    for filter_ in panflute_filters(ext, ".html"):
        ast = filter_(ast)
    html = convert_text(
        ast,
        input_format="panflute",
        output_format="html",
        standalone=True,
        extra_args=extra_args,
    )
    html = xml_safe(html)
    for html_filter in html_filters:
        html = html_filter(html)
    with open(out_path, "w") as f:
        f.write(html)
