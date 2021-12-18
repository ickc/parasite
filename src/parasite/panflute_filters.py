from __future__ import annotations

import random
import string
from functools import partial
from itertools import chain
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

from panflute.elements import Div, Image, Link, MetaBlocks, MetaList, Plain, RawBlock
from urlpath import URL as Url

if TYPE_CHECKING:
    from typing import Callable, List, Optional, Sequence, TypeVar, Union

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
    cls: str = "lightgallery",
    script_include_after: str = """lightGallery(document.getElementById('{identifier}'), {{
plugins: [lgThumbnail,],
thumbnail: true,
}});
$("#{identifier}").justifiedGallery();""",
) -> Optional[ListContainer[Block]]:
    """Transform contents of Div with class lightgallery to that lightgallery needs."""
    if isinstance(elem, Div) and cls in elem.classes:
        images: List[Image] = []
        elem.walk(partial(extract_image, outputs=images))
        res = [Link(image, url=image.url) for image in images]

        identifier: str = elem.identifier
        if not identifier:
            identifier = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=44)
            )
            logger.info(
                f"Created random identifier {identifier} for lightgallery in"
                f' {doc.get_metadata("title")}.'
            )

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
    attribute: str = "lightgallery",
    suffices: Sequence[str] = [".jpg"],
    script_include_after: str = """lightGallery(document.getElementById('{identifier}'), {{
plugins: [lgThumbnail,],
thumbnail: true,
}});
$("#{identifier}").justifiedGallery();""",
) -> Optional[ListContainer[Block]]:
    """Create lightgallery Div from directory."""
    if isinstance(elem, Div) and attribute in elem.attributes:
        root = doc.get_metadata("root", "/")
        res = [
            Link(Image(url=(url := str(root / Url(path)))), url=url)
            for path in sorted(
                chain(
                    *(
                        Path(elem.attributes[attribute]).glob(f"**/*{suffix}")
                        for suffix in suffices
                    )
                )
            )
        ]

        identifier = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=44)
        )
        logger.info(
            f"Created random identifier {identifier} for lightgallery in"
            f' {doc.get_metadata("title")}.'
        )

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
