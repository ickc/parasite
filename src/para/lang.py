"""Languages: BCP 47 tags, and values by language.

A tag names the written language: ``en``, ``zh-Hant`` (Traditional Chinese),
``zh-Hans`` (Simplified). Written in any case and with ``_`` (``zh_tw``, Nikola's), it
is normalised (``zh-TW``). A value by language is looked up from the most specific tag
to the least: ``zh-Hant-HK``, then ``zh-Hant``, then ``zh``.
"""

from __future__ import annotations

import re
import threading
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import panflute as pf

if TYPE_CHECKING:
    from typing import Mapping, Optional

    from panflute import Doc, Element

# a language's own name, for the links between a page's translations
NAMES = {
    "en": "English",
    "zh": "中文",
    "zh-Hant": "繁體中文",
    "zh-Hans": "简体中文",
    "ja": "日本語",
    "ko": "한국어",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
}


def tag(value: str) -> str:
    """``value`` as a BCP 47 tag in its usual case: ``zh_hant`` is ``zh-Hant``,
    ``zh_tw`` is ``zh-TW``."""
    parts = re.split(r"[-_]", str(value).strip())
    res = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            res.append(part.title())
        elif (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit()):
            res.append(part.upper())
        else:
            res.append(part.lower())
    return "-".join(res)


def fallbacks(lang: str) -> list[str]:
    """``lang``, then less specific: ``zh-Hant-HK``, ``zh-Hant``, ``zh``."""
    parts = tag(lang).split("-")
    return ["-".join(parts[:i]) for i in range(len(parts), 0, -1)]


def lookup(table: Mapping[str, Any], lang: str, default_lang: str = "") -> Optional[Any]:
    """The value of ``table`` (keys are tags, in any case) for ``lang``, else for
    ``default_lang``, from the most specific tag to the least; None if there is none."""
    by_tag = {tag(key): value for key, value in table.items()}
    for wanted in (lang, default_lang):
        if not wanted:
            continue
        for candidate in fallbacks(wanted):
            if candidate in by_tag:
                return by_tag[candidate]
    return None


def matches(lang: str, wanted: str) -> bool:
    """Whether ``lang`` is ``wanted`` or more specific: ``zh-Hant-HK`` is ``zh-Hant``."""
    return tag(wanted) in fallbacks(lang)


def name(lang: str) -> str:
    """The language's own name, else its tag."""
    res = lookup(NAMES, lang)
    return tag(lang) if res is None else res


_LOCK = threading.Lock()


@lru_cache(maxsize=None)
def _opencc(conversion: str) -> Any:
    try:
        import opencc
    except ImportError:
        raise RuntimeError(f"[translations] convert = {conversion!r} needs OpenCC: install para[opencc]") from None
    return opencc.OpenCC(conversion if conversion.endswith(".json") else f"{conversion}.json")


def convert_text(text: str, conversion: str) -> str:
    """``text`` converted by OpenCC's ``conversion``."""
    converter = _opencc(conversion)
    with _LOCK:
        return converter.convert(text)


def convert(doc: Doc, conversion: str) -> Doc:
    """``doc``'s text, and its metadata's, converted by OpenCC's ``conversion``
    (``hk2s``: Traditional Chinese as in Hong Kong to Simplified). Code, URLs,
    identifiers and raw HTML are left as they are."""
    converter = _opencc(conversion)

    def action(elem: Element, doc: Doc) -> None:
        if isinstance(elem, (pf.Str, pf.MetaString)):
            # one converter for every page: its use is not known to be thread safe
            with _LOCK:
                text = converter.convert(elem.text)
            if text != elem.text:
                elem.text = text

    return doc.walk(action)
