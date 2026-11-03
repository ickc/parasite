from __future__ import annotations

import pytest

from para.lang import fallbacks, lookup, matches, name, tag
from para.translate import translate


@pytest.mark.parametrize(
    "value, expected",
    [("en", "en"), ("zh_tw", "zh-TW"), ("ZH-HANT", "zh-Hant"), ("zh-hant-hk", "zh-Hant-HK"), ("es-419", "es-419")],
)
def test_tag(value, expected):
    assert tag(value) == expected


def test_lookup_from_specific_to_general():
    assert fallbacks("zh-Hant-HK") == ["zh-Hant-HK", "zh-Hant", "zh"]
    table = {"en": "E", "zh_hant": "T"}
    assert lookup(table, "zh-Hant-HK") == "T"
    assert lookup(table, "zh-Hans", "en") == "E"
    assert lookup(table, "fr") is None
    assert matches("zh-Hant-HK", "zh-Hant") and not matches("zh-Hans", "zh-Hant")


def test_names_and_words():
    assert name("zh-Hant-HK") == "繁體中文"
    assert name("xx") == "xx"
    assert translate("Tags", "zh-Hans") == "标签"
    assert translate("Tags", "zh_tw") == "標籤"
    assert translate("Tags", "fr") == "Tags"
