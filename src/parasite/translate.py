from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict

VOCABULARIES: Dict[str, Dict[str, str]] = {
    'zh_tw': {
        'Tags and Categories': '標籤和分類',
        'Categories': '分類',
        'Tags': '標籤',
        'Categories links': '分類連結',
        'Tags links': '標籤連結',
        'Archive': '彙整',
    }
}


def translate(text: str, lang: str) -> str:
    if lang == 'en':
        return text
    else:
        return VOCABULARIES[lang][text]
