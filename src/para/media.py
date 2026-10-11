"""Resolve media and relative URLs of a page against its output location.

A source file refers to media in ways that need help to work from the output page:

- relative paths written relative to the source file, e.g. ``../../media/fig.svg``,
  which only work if the page is output at the same depth as its source;
- relative paths to files outside the folders copied to the output, which are not
  in the output at all;
- media embedded in the source (e.g. notebook outputs), which pandoc keeps in its media
  bag and never writes out unless asked to.
"""

from __future__ import annotations

import hashlib
import os
import posixpath
import subprocess  # nosec
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote, unquote, urlsplit

from panflute.elements import Image, Link

if TYPE_CHECKING:
    from typing import Callable, Dict, List, Optional

    from panflute.elements import Doc, Element

logger = getLogger(__name__)

# formats whose embedded media pandoc can extract
EMBEDDED_MEDIA_EXTS = {".ipynb"}


def extract_media_options(ext: str, out_dir: Path) -> List[str]:
    """pandoc options to write the embedded media of a source into the page output directory."""
    return [f"--extract-media={out_dir}"] if ext in EMBEDDED_MEDIA_EXTS else []


def default_image_extension(pandoc_options: List[str]) -> str:
    """The value of ``--default-image-extension`` in pandoc options, with a leading dot, or ''."""
    prefix = "--default-image-extension="
    for option in reversed(pandoc_options):
        if option.startswith(prefix):
            ext = option[len(prefix) :]
            return ext if ext.startswith(".") else f".{ext}"
    return ""


def pdf_to_svg(path: Path) -> Path:
    """Convert a single page PDF to SVG with pdf2svg, which browsers can display."""
    out_path = path.with_suffix(".svg")
    cmd = ["pdf2svg", str(path), str(out_path)]
    logger.debug("Running %s", " ".join(cmd))
    subprocess.run(cmd, check=True)  # nosec
    return out_path


def localize_extracted_media(
    doc: Doc, out_dir: Path, convert_pdf: bool = True, claim: Optional[Callable[[Path], None]] = None
) -> Doc:
    """Make URLs of media extracted into ``out_dir`` relative to the page in ``out_dir``.

    PDFs are converted to SVG if ``convert_pdf``, as an HTML page can only embed them.
    ``claim`` is told each file written.
    """
    prefix = f"{out_dir}{os.sep}"

    def action(elem: Element, doc: Doc) -> None:
        if isinstance(elem, Image) and elem.url.startswith(prefix):
            path = Path(elem.url)
            if claim is not None:
                claim(path)
            if convert_pdf and path.suffix == ".pdf":
                path = pdf_to_svg(path)
                if claim is not None:
                    claim(path)
            elem.url = path.name

    return doc.walk(action)


def copy_media(
    path: Path, out_dir: Path, convert_pdf: bool = True, claim: Optional[Callable[[Path], None]] = None
) -> Path:
    """Copy a local media file next to the page in ``out_dir``, named by its content hash
    as pandoc names extracted media, converting PDF to SVG if ``convert_pdf``. ``claim``
    is told each file written."""
    data = path.read_bytes()
    dest = out_dir / (hashlib.sha1(data, usedforsecurity=False).hexdigest() + path.suffix)
    if claim is not None:
        claim(dest)
    if not dest.exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    if convert_pdf and dest.suffix == ".pdf":
        dest = pdf_to_svg(dest)
        if claim is not None:
            claim(dest)
    return dest


def rebase_relative_urls(
    doc: Doc,
    source: Path,
    out_dir: Path,
    output_dir: Path,
    files_folders: Dict[str, str],
    image_extension: str = "",
    convert_pdf: bool = True,
    claim: Optional[Callable[[Path], None]] = None,
) -> Doc:
    """Rewrite relative URLs of local files to work from the page in ``out_dir``.

    A relative URL is resolved against the directory of ``source`` first, then against
    the working directory (pandoc's default resource path, as used when the source is
    converted by pandoc directly, e.g. to PDF). If it resolves to an existing file:

    - inside one of ``files_folders`` (copied to the output as is): the URL is rewritten
      relative to ``out_dir``;
    - elsewhere, for an image: the file is copied next to the page (see :func:`copy_media`).

    Anything else, e.g. links to other pages written as output URLs, is left untouched.

    Args:
        source: path of the source file, relative to the site root (the working directory).
        out_dir: output directory of the page.
        output_dir: output directory of the site.
        files_folders: input directory -> output sub-directory, see ``Config.files_folders``.
        image_extension: pandoc's ``--default-image-extension`` for images without one.
        convert_pdf: convert copied PDF images to SVG.
        claim: told each file copied into the output.
    """
    folders = {Path(in_dir): output_dir / out_sub_dir for in_dir, out_sub_dir in files_folders.items()}

    def resolve(url_path: str, is_image: bool) -> Optional[tuple[Path, Path]]:
        """Return (path as written, existing file) for the first base the URL resolves in."""
        for base in (source.parent.as_posix(), "."):
            path = Path(posixpath.normpath(posixpath.join(base, url_path)))
            candidates = [path]
            if is_image and not path.suffix and image_extension:
                candidates.append(path.with_name(path.name + image_extension))
            for candidate in candidates:
                if candidate.is_file():
                    return path, candidate
        return None

    def rebase(url: str, is_image: bool) -> Optional[str]:
        parts = urlsplit(url)
        if parts.scheme or parts.netloc or not parts.path or parts.path.startswith("/"):
            return None
        url_path = unquote(parts.path)
        resolved = resolve(url_path, is_image)
        if resolved is None:
            return None
        path, file = resolved
        for in_dir, out_sub_dir in folders.items():
            if path.is_relative_to(in_dir):
                new = Path(os.path.relpath(out_sub_dir / path.relative_to(in_dir), out_dir)).as_posix()
                break
        else:
            if not is_image:
                return None
            new = copy_media(file, out_dir, convert_pdf=convert_pdf, claim=claim).name
        if new == url_path:
            return None
        # keep the quoting style of the original
        return parts._replace(path=quote(new) if "%" in parts.path else new).geturl()

    def action(elem: Element, doc: Doc) -> None:
        if isinstance(elem, (Image, Link)):
            new = rebase(elem.url, isinstance(elem, Image))
            if new is not None:
                logger.debug("Rebased %s to %s in %s", elem.url, new, source)
                elem.url = new

    return doc.walk(action)
