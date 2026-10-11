"""Reading sources and writing pages: the work the pipeline does per page."""

from __future__ import annotations

import json
import os
import re
import subprocess  # nosec
import tempfile
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
from .filters import chosen, run
from .lang import convert
from .panflute_filters import meta_append, select_content, select_text

if TYPE_CHECKING:
    from .config import Config, Profile
    from .output import Output
    from typing import Callable, Dict, List, Mapping, Optional, Sequence


    from .filters import Filter

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
    filters: Mapping[str, Filter],
    inputs: List[Path] = [],
    out_dir: Optional[Path] = None,
    output_dir: Path = Path("output"),
    files_folders: Dict[str, str] = {},
    convert_pdf_media: bool = True,
    claim: Optional[Callable[[Path], None]] = None,
    select: Optional[Profile] = None,
    pandoc_filters: bool = True,
    extra_options: Sequence[str] = (),
    conversion: str = "",
) -> pf.elements.Doc:
    """Read from markdown to panflute AST

    If ``out_dir``, the output directory of the page, is given, embedded media are
    written there, and relative URLs to local files are made to work from the page,
    see :mod:`para.media`; ``claim`` is told each media file written.

    With ``select``, the document is read as that profile's output sees it: its content
    per profile is selected before pandoc reads it (:func:`para.panflute_filters.select_text`:
    heading identifiers, crossref's numbers and citeproc's bibliography are the
    output's own), or for a notebook after parsing and before pandoc's filters.
    ``pandoc_filters`` False leaves out pandoc's filters (crossref, citeproc, Lua).
    ``filters`` is the site's allow-list: the read filters the document chooses run
    after pandoc's (see :mod:`para.filters`).
    ``extra_options`` are the page's own pandoc options (its language, its primary's
    front matter, see :mod:`para.lang`); ``conversion``, an OpenCC conversion of its
    text, applied last.
    """
    assert len(inputs) == 1
    path = inputs[0]
    ext = path.suffix

    with open(path, "r") as f:
        text = f.read()
    input_format = "markdown" if ext == ".md" else ext[1:]
    # comments in a source are notes, not content: and commented-out drafts
    # (`<!-- … -- … -->`) would make the page ill-formed
    options = ["--strip-comments"] + pandoc_options(ext) + list(extra_options)
    if not pandoc_filters:
        # e.g. to list the media of every output of a source with content per profile
        options, _ = split_filter_options(options)
    extra_args = options if out_dir is None else options + extract_media_options(ext, out_dir)
    if select is not None and ext != ".ipynb":
        text = select_text(text, select)
    if select is None or ext != ".ipynb":
        doc = convert_text(text, input_format=input_format, standalone=True, extra_args=extra_args)
    else:
        # a notebook's cells are JSON: selected on its AST, before pandoc's filters
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

    doc = run(chosen(filters, "read", doc.get_metadata("filters"), str(path), ext=ext), doc)
    if conversion:
        doc = convert(doc, conversion)
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
    unknown = sorted(set(over.content) - {"metadata", "output-file", "variables"})
    if unknown:
        logger.warning("format: %s: only metadata, variables and output-file are supported, not %s", name, ", ".join(unknown))
    metadata = over.content.get("metadata")
    if isinstance(metadata, pf.MetaMap):
        for key, value in list(metadata.content.items()):
            ast.metadata[key] = value


def variables(ast: pf.elements.Doc, name: str) -> List[str]:
    """pandoc's ``--variable`` options from ``format``'s ``NAME: {variables: …}`` (a list
    is the variable given once per item)."""
    fmt = ast.metadata.content.get("format")
    over = fmt.content.get(name) if isinstance(fmt, pf.MetaMap) else None
    table = over.content.get("variables") if isinstance(over, pf.MetaMap) else None
    if not isinstance(table, pf.MetaMap):
        return []
    res = []
    for key, value in table.content.items():
        items = value.content if isinstance(value, pf.MetaList) else [value]
        for item in items:
            text = str(item.boolean).lower() if isinstance(item, pf.MetaBool) else pf.stringify(item)
            res.append(f"--variable={key}:{text}")
    return res


def post_to_pdf(
    ast: pf.elements.Doc,
    profile: Profile,
    out_path: Path,
    config: Config,
    /,
    *,
    epoch: int = 0,
    output: Optional[Output] = None,
    owner: str = "",
) -> None:
    """Write ``ast`` as a PDF in profile ``profile`` (its engine, its template or pandoc's).
    Its images are found from its folder in the output (``out_path``'s), where they are
    copied, and it is dated ``epoch`` (``SOURCE_DATE_EPOCH``), its page's date, so that
    the same page gives the same bytes. It changes ``ast`` (the render filters)."""
    profile_metadata(ast, profile.name)
    chain = chosen(config.filters, "render", ast.get_metadata("filters"), str(out_path), profile=profile.filters)
    ast = run([f for f in chain if not f.lua], ast)
    args = list(profile.options) + variables(ast, profile.name) + [f"--lua-filter={f.path}" for f in chain if f.lua]
    if profile.template is not None:
        args.append(f"--template={profile.template}")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "out.pdf"
        res = subprocess.run(  # nosec
            ["pandoc", "--from=json", f"--output={pdf}", f"--resource-path={out_path.parent}", *args],
            input=json.dumps(ast.to_json()),
            text=True,
            capture_output=True,
            env={**os.environ, "SOURCE_DATE_EPOCH": str(epoch)},
        )
        if res.returncode != 0:
            raise RuntimeError(f"{out_path}: pandoc failed to write the PDF:\n{res.stderr}")
        data = pdf.read_bytes()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if output is None:
        out_path.write_bytes(data)
    else:
        output.write(out_path, data, owner)


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
        ast.metadata["title-prefix"] = pf.RawBlock(config.localized(config.blog_title, lang))
    if config.logo_url:
        ast.metadata["logo-url"] = config.logo_url
    ast.metadata["nav"] = pf.RawBlock(part("nav"))
    if root:
        ast.metadata["root"] = root

    extra_args = list(profile.options) + [f"--css={c.replace('{root}', root)}" for c in profile.css]
    extra_args += variables(ast, profile.name)
    if template is not None:
        extra_args.append(f"--template={template}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # the render filters: Python here, Lua in the call writing the output (its FORMAT)
    chain = chosen(config.filters, "render", ast.get_metadata("filters"), str(out_path), profile=profile.filters)
    ast = run([f for f in chain if not f.lua], ast)
    extra_args += [f"--lua-filter={f.path}" for f in chain if f.lua]
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
