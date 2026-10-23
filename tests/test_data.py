from __future__ import annotations

from pathlib import Path

import panflute as pf
import pytest

from para.data import Page, Post, format_years
from para.record import Record, by_category, site_years

from conftest import make_page


def make(cls: type[Page], path: str, **metadata: str) -> Page:
    return make_page(cls, path, pf.Doc(metadata=metadata))


@pytest.mark.parametrize(
    "years,expected",
    [(None, ""), ((2016, 2016), "2016"), ((2012, 2026), "2012–2026")],
)
def test_format_years(years, expected):
    assert format_years(years) == expected


def test_years_from_own_dates():
    assert make(Post, "a.md", date="2016-04-29").years == (2016, 2016)
    assert make(Post, "a.md", date="2016-04-29", **{"date-modified": "2019-01-02"}).years == (2016, 2019)
    assert make(Page, "about.md").years is None


def test_iso_dates():
    page = make(Post, "a.md", date="2016-04-29T10:00:00+01:00")
    assert page.published.year == 2016
    assert page.published.utcoffset().total_seconds() == 3600


def record(cls: type[Page], path: str, **metadata: str) -> Record:
    return Record.from_page(make(cls, path, **metadata), cls is Post)


def test_site_years_widen_with_an_old_post():
    records = [record(Post, "a.md", date="2016-01-01"), record(Page, "about.md")]
    assert site_years(records) == (2016, 2016)
    records.append(record(Post, "old.md", date="2012-05-05", **{"date-modified": "2026-01-01"}))
    assert site_years(records) == (2012, 2026)


def test_category_tree():
    records = [
        record(Post, "so-uk/meetings/a.md", date="2023-01-01"),
        record(Post, "so-uk/b.md", date="2023-01-02"),
        record(Post, "c.md", date="2023-01-03"),
        record(Post, "x/d.md", date="2023-01-04", category="so-uk/meetings"),
    ]
    categories = {name: [Path(post.source).name for post in posts] for name, posts in by_category(records).items()}
    assert categories == {
        "so-uk": ["a.md", "b.md", "d.md"],
        "so-uk/meetings": ["a.md", "d.md"],
    }


def test_record_round_trips_through_json():
    import json

    rec = record(Post, "x/a.md", date="2020-01-01", title="A", tags=["t"])
    assert Record.from_json(json.loads(json.dumps(rec.to_json()))) == rec
    assert rec.url == "x/a/" and rec.out_path == "x/a/index.html" and rec.years == (2020, 2020)


def test_a_post_needs_a_date():
    with pytest.raises(ValueError):
        record(Post, "a.md")


def test_summary_falls_back_to_the_subtitle():
    assert make(Post, "a.md", subtitle="S").summary == "S"
    assert make(Post, "a.md", subtitle="S", description="D").summary == "D"
    assert make(Post, "a.md").summary is None


def test_a_document_chooses_its_profiles():
    page = make_page(Post, "x/a.md", pf.Doc(metadata={"date": "2020-01-01", "format": ["html", "slides"]}))
    assert [(profile.name, path.as_posix()) for profile, path in page.outputs] == [
        ("html", "x/a/index.html"),
        ("slides", "x/a/present.html"),
    ]
    assert page.url == "x/a/"
    with pytest.raises(ValueError):
        make_page(Post, "x/b.md", pf.Doc(metadata={"date": "2020-01-01", "format": ["nope"]}))


def test_404_is_not_a_folder():
    assert make(Page, "404.md").out_path.as_posix() == "404.html"
    assert make(Page, "404.md").url == "404.html"
