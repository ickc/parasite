"""The theme's own words, by language (see :func:`para.lang.lookup`); English otherwise."""

from __future__ import annotations

from .lang import lookup

VOCABULARIES: dict[str, dict[str, str]] = {
    "zh-Hant": {
        "Tags and Categories": "標籤和分類",
        "Categories": "分類",
        "Tags": "標籤",
        "Categories links": "分類連結",
        "Tags links": "標籤連結",
        "Archive": "彙整",
    },
    "zh-Hans": {
        "Tags and Categories": "标签和分类",
        "Categories": "分类",
        "Tags": "标签",
        "Categories links": "分类链接",
        "Tags links": "标签链接",
        "Archive": "汇整",
    },
}
# Nikola's code, before tags were BCP 47: Traditional Chinese
VOCABULARIES["zh-TW"] = VOCABULARIES["zh-Hant"]


def translate(text: str, lang: str) -> str:
    vocabulary = lookup(VOCABULARIES, lang)
    return text if vocabulary is None else vocabulary.get(text, text)
