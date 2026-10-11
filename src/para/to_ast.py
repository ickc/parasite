from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import panflute as pf

from .translate import translate
from .util import join_url

if TYPE_CHECKING:
    from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

    from .record import Record


def posts_to_index_ast(
    posts: Sequence[Record],
    title: str,
    n_jumbotron: int = 1,
    n_grid: int = 2,
    index_include_jumbotron: bool = True,
    lang: str = "en",
    length: Optional[int] = None,
    older_url: Optional[str] = None,
) -> pf.elements.Doc:
    """A listing of ``posts``, newest first: the first ``length`` of them, if given, and
    a link to ``older_url`` when there are more."""
    if length is not None and len(posts) > length:
        posts = posts[:length]
    else:
        older_url = None

    def post_to_dict(post: Record) -> dict[str, Any]:
        res = {
            "url": post.url,
        }
        if post.summary:
            res["description"] = post.summary
        if post.title is not None:
            res["title"] = post.title
        if post.image is not None:
            res["image"] = post.image
        if post.author is not None:
            res["author"] = post.author
        res["date"] = post.date
        return res

    meta: Dict[str, Any] = {
        "title": title,
        "lang": lang,
    }
    if older_url is not None:
        meta["older-url"] = older_url

    temp_index = []
    temp = []
    for post in posts[:n_jumbotron]:
        data = post_to_dict(post)
        temp.append(data)
        if index_include_jumbotron:
            temp_index.append(data)
    meta["index_jumbotron"] = temp

    temp = []
    for post in posts[n_jumbotron : n_jumbotron + n_grid]:
        data = post_to_dict(post)
        temp.append(data)
        if index_include_jumbotron:
            temp_index.append(data)
    meta["index_grid"] = temp

    for post in posts[n_jumbotron + n_grid :]:
        temp_index.append(post_to_dict(post))
    meta["index"] = temp_index

    return pf.elements.Doc(metadata=meta)


def posts_to_tag_ast(
    categories: Dict[str, List[Record]],
    tags: Dict[str, List[Record]],
    font_size_min: int = 70,
    font_size_max: int = 280,
    root: str = "..",
    lang: str = "en",
) -> pf.elements.Doc:
    meta: Dict[str, Any] = {
        "title": translate("Tags and Categories", lang),
        "lang": lang,
        "Categories-archive-title": translate("Categories", lang),
        "Tags-archive-title": translate("Tags", lang),
    }
    contents = []
    for case, dict_ in (
        ("Categories", categories),
        ("Tags", tags),
    ):
        # tag cloud (none when no post has a category, or a tag)
        counts_dict = {name: len(list_) for name, list_ in dict_.items()}
        counts = counts_dict.values()
        min_ = min(counts, default=0)
        max_ = max(counts, default=0)
        try:
            m = (font_size_max - font_size_min) / (max_ - min_)
            c = font_size_min - m * min_
        except ZeroDivisionError:
            m = 0
            c = 100
        temp: List[Dict[str, Union[str, float]]] = []
        meta[f"{case}-archive"] = temp
        for name, count in counts_dict.items():
            font_size = m * count + c
            temp.append(
                {
                    "name": name,
                    "font_size": font_size,
                }
            )

        # list of links
        contents.append(
            pf.Header(
                pf.Str(translate(f"{case} links", lang)),
                level=1,
                identifier=f"{case}-links",
            )
        )
        for name, posts in dict_.items():
            contents.append(
                pf.Header(pf.Str(name), level=2, identifier=f"{case}-{name}")
            )
            lis = []
            for post in posts:
                lis.append(
                    pf.ListItem(
                        pf.Plain(
                            pf.Link(
                                pf.Str(f"{post.date} — {post.title}"),
                                url=join_url(root, post.url),
                            )
                        )
                    )
                )
            contents.append(pf.BulletList(*lis))

    return pf.elements.Doc(
        *contents,
        metadata=meta,
    )


def posts_to_archive_index_ast(
    years: Dict[int, List[Record]],
    lang: str = "en",
) -> pf.elements.Doc:
    """The archive's front page: one link per year. A new post changes it only when it
    starts a year."""
    items = [
        pf.ListItem(pf.Plain(pf.Link(pf.Str(f"{year} ({len(posts)})"), url=f"{year}/")))
        for year, posts in years.items()
    ]
    return pf.elements.Doc(
        pf.BulletList(*items),
        metadata={"title": translate("Archive", lang), "lang": lang},
    )


def posts_to_archive_ast(
    posts: Sequence[Record],
    root: str = "..",
    lang: str = "en",
    title: Optional[str] = None,
) -> pf.elements.Doc:
    """The archive of ``posts`` (one year's, in parasite), by month."""
    meta = {
        "title": title or translate("Archive", lang),
        "lang": lang,
    }

    res: Dict[int, Dict[str, List[Tuple[str, Optional[str], str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for page in posts:
        title_ = page.title
        url = page.url
        date = page.date
        time = page.time
        res[time.year][time.strftime("%B")].append((date, title_, url))

    contents = []
    for year, datas in res.items():
        for month, data in datas.items():
            contents.append(
                pf.Header(pf.Str(month), level=2, identifier=f"{year}-{month}")
            )
            lis = []
            for date, title_, url in data:
                lis.append(
                    pf.ListItem(
                        pf.Plain(
                            pf.Link(
                                pf.Str(f"{date} — {title_}"),
                                url=join_url(root, url),
                            )
                        )
                    )
                )
            contents.append(pf.BulletList(*lis))

    return pf.elements.Doc(
        *contents,
        metadata=meta,
    )
