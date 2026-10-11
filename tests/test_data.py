from __future__ import annotations

from pathlib import Path

import panflute as pf
import pytest

from parasite.data import Page, Post, Posts, format_years, site_years


def make(cls: type[Page], path: str, **metadata: str) -> Page:
    page = cls(Path("posts") / path, Path("posts"), Path(""), None)
    page.ast = pf.Doc(metadata=metadata)
    return page


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


def test_site_years_widen_with_an_old_post():
    pages = [make(Post, "a.md", date="2016-01-01"), make(Page, "about.md")]
    assert site_years(pages) == (2016, 2016)
    pages.append(make(Post, "old.md", date="2012-05-05", **{"date-modified": "2026-01-01"}))
    assert site_years(pages) == (2012, 2026)


def test_category_tree():
    posts = Posts(
        [
            make(Post, "so-uk/meetings/a.md", date="2023-01-01"),
            make(Post, "so-uk/b.md", date="2023-01-02"),
            make(Post, "c.md", date="2023-01-03"),
            make(Post, "x/d.md", date="2023-01-04", category="so-uk/meetings"),
        ]
    )
    categories = {name: [post.path.name for post in posts] for name, posts in posts.categories.items()}
    assert categories == {
        "so-uk": ["a.md", "b.md", "d.md"],
        "so-uk/meetings": ["a.md", "d.md"],
    }


def test_summary_falls_back_to_the_subtitle():
    assert make(Post, "a.md", subtitle="S").summary == "S"
    assert make(Post, "a.md", subtitle="S", description="D").summary == "D"
    assert make(Post, "a.md").summary is None
