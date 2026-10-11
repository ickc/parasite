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
from .config import by_lang
from .panflute_filters import meta_append, select_content

if TYPE_CHECKING:
    from .config import Config, Profile
    from .output import Output
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


# pandoc options that run filters or feed them (citeproc's): with a value, and flags
FILTER_OPTIONS = ("--filter", "-F", "--lua-filter", "-L", "--bibliography", "--csl", "--citation-abbreviations",
                  "--metadata", "-M", "--metadata-file")
FILTER_FLAGS = ("--citeproc", "-C")


def split_filter_options(options: List[str]) -> tuple[List[str], List[str]]:
    """``options`` as (the reader's, the filters'): see :data:`FILTER_OPTIONS`."""
    reader: List[str] = []
    filters: List[str] = []
    it = iter(options)
    for option in it:
        name = option.split("=", 1)[0]
        if option in FILTER_FLAGS:
            filters.append(option)
        elif name in FILTER_OPTIONS:
            filters.append(option)
            if "=" not in option and not (name.startswith("-") and not name.startswith("--") and len(option) > 2):
                filters.append(next(it))
        else:
            reader.append(option)
    return reader, filters


def read_md_to_ast(
    pandoc_options: Callable[[str], List[str]],
    panflute_filters: Callable[[str], list[PanfluteFilter]],
    inputs: List[Path] = [],
    out_dir: Optional[Path] = None,
    output_dir: Path = Path("output"),
    files_folders: Dict[str, str] = {},
    convert_pdf_media: bool = True,
    claim: Optional[Callable[[Path], None]] = None,
    select: Optional[Profile] = None,
) -> pf.elements.Doc:
    """Read from markdown to panflute AST

    If ``out_dir``, the output directory of the page, is given, embedded media are
    written there, and relative URLs to local files are made to work from the page,
    see :mod:`para.media`; ``claim`` is told each media file written.

    With ``select``, the document is read as that profile's output sees it: its content
    per profile is selected (:func:`para.panflute_filters.select_content`) after
    parsing and before pandoc's filters (crossref numbers, citeproc's bibliography).
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
    if select is None:
        doc = convert_text(text, input_format=input_format, standalone=True, extra_args=extra_args)
    else:
        reader, filters = split_filter_options(extra_args)
        doc = convert_text(text, input_format=input_format, standalone=True, extra_args=reader)
        doc = select_content(doc, select)
        doc = convert_text(doc, input_format="panflute", output_format="panflute", standalone=True, extra_args=filters)
    if out_dir is not None:
        doc = localize_extracted_media(doc, out_dir, convert_pdf=convert_pdf_media, claim=claim)
        doc = rebase_relative_urls(
            doc,
            path,
            out_dir,
            output_dir,
            files_folders,
            image_extension=default_image_extension(options),
            convert_pdf=convert_pdf_media,
            claim=claim,
        )

    for filter_ in panflute_filters(ext):
        doc = filter_(doc)
    return doc


def profile_metadata(ast: pf.elements.Doc, name: str) -> None:
    """The document's metadata for its output in profile ``name``: ``format``'s
    ``NAME: {metadata: …}`` (pandoc's defaults-file key) over the document's own."""
    fmt = ast.metadata.content.get("format")
    if not isinstance(fmt, pf.MetaMap):
        return
    over = fmt.content.get(name)
    if not isinstance(over, pf.MetaMap):
        return
    unknown = sorted(set(over.content) - {"metadata"})
    if unknown:
        logger.warning("format: %s: only metadata is supported, not %s", name, ", ".join(unknown))
    metadata = over.content.get("metadata")
    if isinstance(metadata, pf.MetaMap):
        for key, value in list(metadata.content.items()):
            ast.metadata[key] = value


def post_to_html(
    ast: pf.elements.Doc,
    root: str,
    lang: str,
    profile: Profile,
    out_path: Path,
    config: Config,
    /,
    *,
    template: Optional[Path] = None,
    years: str = "",
    output: Optional[Output] = None,
    owner: str = "",
) -> None:
    """Write ``ast`` as a standalone page in output profile ``profile`` (its template,
    or ``template``), with the page's parts from ``config``. ``{root}`` and ``{years}``
    in the parts become ``root`` and ``years``.

    It changes ``ast`` (the includes, the output filters): render an AST once, after
    everything that reads it.
    """
    template = template or profile.template

    def part(name: str) -> str:
        return config.part(profile, name, lang).replace("{root}", root).replace("{years}", years)

    profile_metadata(ast, profile.name)
    if "lang" not in ast.metadata.content:
        ast.metadata["lang"] = lang
    meta_append(ast.metadata, "header-includes", part("header_includes"))
    meta_append(ast.metadata, "include-before", part("include_before"))
    meta_append(ast.metadata, "include-after", part("include_after"))
    if config.write_graph:
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
    for url in profile.js:
        meta_append(ast.metadata, "js-include-after", url.replace("{root}", root))
    meta_append(ast.metadata, "script-include-after", part("script_include_after"))

    if profile.show_image:
        ast.metadata["show-image-in-post"] = "true"
    # <meta name="description"> falls back to the subtitle, as listings do
    if "description" not in ast.metadata.content and "subtitle" in ast.metadata.content:
        ast.metadata["description-meta"] = pf.MetaString(pf.stringify(ast.metadata.content["subtitle"]))
    # set even when empty, as before
    ast.metadata["content-footer"] = pf.RawBlock(part("footer"))
    if config.mathjax_config:
        ast.metadata["mathjax-config"] = pf.RawBlock(config.mathjax_config)
    ast.metadata["search-form"] = pf.RawBlock(part("search_form"))
    if config.blog_title:
        ast.metadata["title-prefix"] = pf.RawBlock(by_lang(config.blog_title, lang, config.default_lang))
    if config.logo_url:
        ast.metadata["logo-url"] = config.logo_url
    ast.metadata["nav"] = pf.RawBlock(part("nav"))
    if root:
        ast.metadata["root"] = root

    extra_args = list(profile.options) + [f"--css={c.replace('{root}', root)}" for c in profile.css]
    if template is not None:
        extra_args.append(f"--template={template}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    for filter_ in profile.filters:
        ast = filter_(ast)
    html = convert_text(
        ast,
        input_format="panflute",
        output_format="html",
        standalone=True,
        extra_args=extra_args,
    )
    html = xml_safe(html)
    for html_filter in config.html_filters:
        html = html_filter(html)
    if output is None:
        with open(out_path, "w") as f:
            f.write(html)
    else:
        output.write(out_path, html, owner)
