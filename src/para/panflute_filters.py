from __future__ import annotations

import hashlib
import re
from functools import partial
from itertools import chain
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

from panflute.elements import Div, Image, Link, Math, MetaBlocks, MetaList, Plain, RawBlock, Span

from .util import join_url

if TYPE_CHECKING:
    from typing import Any, Callable, List, Optional, Sequence, TypeVar, Union

    from panflute.base import Block
    from panflute.containers import ListContainer
    from panflute.elements import Doc, Element, MetaMap

    # panflute types inferred from `panflute.run_filters`
    # panflute actions also accepts **kwargs
    PanfluteAction = Callable[[Element, Doc], Union[None, Element, list[Element]]]
    PanflutePrepare = Optional[Callable[[Doc], None]]
    PanfluteFinalize = PanflutePrepare
    # typically, panflute filter is a main function calling `panflute.run_filters`
    _NoneToNone = Callable[[None], None]
    _DocToDoc = Callable[[Doc], Doc]
    PanfluteFilter = TypeVar("PanfluteFilter", _DocToDoc, _NoneToNone)


logger = getLogger(__name__)
LIGHTGALLERY_NAME: str = "lightgallery"
SCRIPT_INCLUDE_AFTER: str = """lightGallery(document.getElementById('{identifier}'), {{
plugins: [lgThumbnail,],
thumbnail: true,
}});
$("#{identifier}").justifiedGallery();"""


def _gen_identifier(
    links: list[Link],
    doc: Doc,
) -> str:
    h = hashlib.sha1(usedforsecurity=False)
    for link in links:
        logger.debug("Hashing %s", link.url)
        h.update(link.url.encode())
    identifier = h.hexdigest()
    logger.info(
        f"Created hash identifier {identifier} for lightgallery in"
        f' {doc.get_metadata("title")}.'
    )
    return identifier


def meta_append(meta: MetaMap, key: str, value: str) -> None:
    """Append or create key in meta with value in-place."""
    raw_block = MetaBlocks(RawBlock(value))
    if key in meta:
        temp = meta[key]
        if isinstance(temp, MetaList):
            temp.append(raw_block)
        else:
            meta[key] = MetaList(temp, raw_block)
    else:
        meta[key] = raw_block


def extract_image(
    elem: ListContainer[Block],
    doc: Doc,
    outputs: list[Image] = [],
) -> None:
    """Append Image to outputs.

    This filter does nothing to the elem/doc.
    """
    if isinstance(elem, Image):
        outputs.append(elem)


# PanfluteAction
def lightgallery(
    elem: ListContainer[Block],
    doc: Doc,
    cls: str = LIGHTGALLERY_NAME,
    script_include_after: str = SCRIPT_INCLUDE_AFTER,
) -> Optional[ListContainer[Block]]:
    """Transform contents of Div with class lightgallery to that lightgallery needs."""
    if isinstance(elem, Div) and cls in elem.classes:
        images: List[Image] = []
        elem.walk(partial(extract_image, outputs=images))
        res = [Link(image, url=image.url) for image in images]

        identifier: str = elem.identifier or _gen_identifier(res, doc)

        meta_append(
            doc.metadata,
            "script-include-after",
            script_include_after.format(identifier=identifier),
        )
        div = Div(
            Plain(*res),
            identifier=identifier,
            classes=elem.classes,
            attributes=elem.attributes,
        )

        return div
    else:
        return None


# PanfluteAction
def lightgallery_from_dir(
    elem: ListContainer[Block],
    doc: Doc,
    attribute: str = LIGHTGALLERY_NAME,
    suffices: Sequence[str] = [".jpg"],
    script_include_after: str = SCRIPT_INCLUDE_AFTER,
) -> Optional[ListContainer[Block]]:
    """Create lightgallery Div from directory."""
    if isinstance(elem, Div) and attribute in elem.attributes:
        root = doc.get_metadata("root", "/")
        res = [
            Link(Image(url=(url := join_url(root, path.as_posix()))), url=url)
            for path in sorted(
                chain(
                    *(
                        Path(elem.attributes[attribute]).glob(f"**/*{suffix}")
                        for suffix in suffices
                    )
                )
            )
        ]

        identifier = _gen_identifier(res, doc)

        meta_append(
            doc.metadata,
            "script-include-after",
            script_include_after.format(identifier=identifier),
        )
        div = Div(
            Plain(*res),
            identifier=identifier,
            classes=elem.classes,
            attributes=elem.attributes,
        )

        return div
    else:
        return None


def lightgallery_filter(doc: Doc) -> Doc:
    return doc.walk(lightgallery, doc)


def lightgallery_from_dir_filter(doc: Doc) -> Doc:
    return doc.walk(lightgallery_from_dir, doc)


# MathJax has no bold upright ℓ: \mathbf{\ell} renders as a plain ℓ (MathJax 3 and 4),
# and so does \boldsymbol{\ell} in MathJax 4. \pmb (overprinted bold) is bold in both.
# LaTeX sources keep \mathbf{\ell}, bold with unicode-math (texp writes it so).
_MATHJAX_BOLD_ELL = re.compile(r"\\mathbf\{(\\hat\{\\ell\}|\\ell)\}")


def mathjax_bold_ell_action(elem: Element, doc: Doc) -> None:
    if isinstance(elem, Math) and "\\mathbf{" in elem.text:
        elem.text = _MATHJAX_BOLD_ELL.sub(r"\\pmb{\1}", elem.text)


def mathjax_bold_ell_filter(doc: Doc) -> Doc:
    """For HTML with MathJax: a bold ℓ that MathJax can show."""
    return doc.walk(mathjax_bold_ell_action)


def _when(elem: Element, key: str) -> list[str]:
    return elem.attributes[key].split() if key in elem.attributes else []


def select_content(doc: Doc, profile: Any) -> Doc:
    """Content per output profile, in Quarto's syntax: a div or span with class
    ``content-visible`` or ``content-hidden``, and ``when-format`` or ``unless-format``
    naming profiles (or writers). What is visible in ``profile`` is unwrapped, the rest
    removed."""

    def action(elem: Element, doc: Doc) -> Any:
        if not isinstance(elem, (Div, Span)):
            return None
        visible = "content-visible" in elem.classes
        if not visible and "content-hidden" not in elem.classes:
            return None
        when, unless = _when(elem, "when-format"), _when(elem, "unless-format")
        if when:
            selected = any(profile.matches(name) for name in when)
        elif unless:
            selected = not any(profile.matches(name) for name in unless)
        else:
            selected = True
        shown = selected if visible else not selected
        return list(elem.content) if shown else []

    return doc.walk(action)
