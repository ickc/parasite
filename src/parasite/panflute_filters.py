from __future__ import annotations

from pathlib import Path
from functools import partial
from logging import getLogger
from typing import TYPE_CHECKING
from itertools import chain
import string
import random

from urlpath import URL as Url
from panflute.elements import Image, Div, Link, Plain, MetaBlocks, RawBlock, MetaList

if TYPE_CHECKING:
    from typing import Optional, List

    from panflute.containers import ListContainer
    from panflute.base import Block
    from panflute.elements import Doc, MetaMap

logger = getLogger('parasite')


def meta_append(meta: MetaMap, key: str, value: str):
    '''Append or create key in meta with value in-place.
    '''
    raw_block = MetaBlocks(RawBlock(value))
    if key in meta:
        temp = meta[key]
        if type(temp) == MetaList:
            temp.append(raw_block)
        else:
            meta[key] = MetaList(temp, raw_block)
    else:
        meta[key] = raw_block


def extract_image(
    elem: ListContainer[Block],
    doc: Doc,
    outputs: list = [],
):
    '''Append Image to outputs.

    This filter does nothing to the elem/doc.
    '''
    if type(elem) == Image:
        outputs.append(elem)


def lightgallery(
    elem: ListContainer[Block],
    doc: Doc,
    cls: str = 'lightgallery',
    include_after: str = """<script>
lightGallery(document.getElementById('{identifier}'), {{
plugins: [lgThumbnail,],
thumbnail: true,
}});
$("#{identifier}").justifiedGallery();
</script>""",
) -> Optional[ListContainer[Block]]:
    """Transform contents of Div with class lightgallery to that lightgallery needs.
    """
    if type(elem) == Div and cls in elem.classes:
        images: List[Image] = []
        elem.walk(partial(extract_image, outputs=images))
        res = [Link(image, url=image.url) for image in images]

        identifier: str = elem.identifier
        if not identifier:
            identifier = ''.join(random.choices(string.ascii_uppercase + string.digits, k=44))
            logger.info(f'Created random identifier {identifier} for lightgallery in {doc.get_metadata("title")}.')

        meta_append(doc.metadata, 'include-after', include_after.format(identifier=identifier))
        div = Div(
            Plain(*res),
            identifier=identifier,
            classes=elem.classes,
            attributes=elem.attributes,
        )

        return div
    else:
        return None


def lightgallery_from_dir(
    elem: ListContainer[Block],
    doc: Doc,
    attribute: str = 'lightgallery',
    suffices: List[str] = ['.jpg'],
    script_include_after: str = """lightGallery(document.getElementById('{identifier}'), {{
plugins: [lgThumbnail,],
thumbnail: true,
}});
$("#{identifier}").justifiedGallery();""",
) -> Optional[ListContainer[Block]]:
    """Create lightgallery Div from directory.
    """
    if type(elem) == Div and attribute in elem.attributes:
        root = doc.get_metadata('root', '/')
        res = [
            Link(Image(url=(url := str(root / Url(path)))), url=url)
            for path in chain(*(Path(elem.attributes[attribute]).glob(f'**/*{suffix}') for suffix in suffices))
        ]

        identifier = ''.join(random.choices(string.ascii_uppercase + string.digits, k=44))
        logger.info(f'Created random identifier {identifier} for lightgallery in {doc.get_metadata("title")}.')

        meta_append(doc.metadata, 'script-include-after', script_include_after.format(identifier=identifier))
        div = Div(
            Plain(*res),
            identifier=identifier,
            classes=elem.classes,
            attributes=elem.attributes,
        )

        return div
    else:
        return None
