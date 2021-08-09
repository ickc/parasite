from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import panflute as pf

from .translate import translate

if TYPE_CHECKING:
    from typing import Any, Dict, List, Sequence, Union

    from urlpath import URL as Url

    from .data import Post


def posts_to_index_ast(
    posts: Sequence[Post],
    title: str,
    n_jumbotron: int = 1,
    n_grid: int = 2,
    index_include_jumbotron: bool = True,
    lang: str = "en",
) -> pf.elements.Doc:
    def post_to_dict(post: Post) -> dict:
        res = {
            "url": str(post.url),
            "teaser": pf.MetaBlocks(*post.teaser),
        }
        if post.title is not None:
            res["title"] = post.title
        if post.previewimage is not None:
            res["previewimage"] = str(post.previewimage)
        if post.author is not None:
            res["author"] = post.author
        res["date"] = post.date
        return res

    meta: Dict[str, Any] = {
        "title": title,
        "lang": lang,
    }

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
    categories: Dict[str, List[Post]],
    tags: Dict[str, List[Post]],
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
        # tag cloud
        counts_dict = {name: len(list_) for name, list_ in dict_.items()}
        counts = counts_dict.values()
        min_ = min(counts)
        max_ = max(counts)
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
                                url=f"{root / post.url}",
                            )
                        )
                    )
                )
            contents.append(pf.BulletList(*lis))

    return pf.elements.Doc(
        *contents,
        metadata=meta,
    )


def posts_to_archive_ast(
    posts: Sequence[Post],
    root: str = "..",
    lang: str = "en",
) -> pf.elements.Doc:
    meta = {
        "title": translate("Archive", lang),
        "lang": lang,
    }

    res: Dict[int, Dict[str, List[Union[str, Url]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for page in posts:
        title = page.title
        url = page.url
        date = page.date
        time = page.time
        res[time.year][time.strftime("%B")].append((date, title, url))

    contents = []
    for year, datas in res.items():
        contents.append(pf.Header(pf.Str(str(year)), level=1, identifier=str(year)))
        for month, data in datas.items():
            contents.append(
                pf.Header(pf.Str(month), level=2, identifier=f"{year}-{month}")
            )
            lis = []
            for (date, title, url) in data:
                lis.append(
                    pf.ListItem(
                        pf.Plain(
                            pf.Link(
                                pf.Str(f"{date} — {title}"),
                                url=f"{root / url}",
                            )
                        )
                    )
                )
            contents.append(pf.BulletList(*lis))

    return pf.elements.Doc(
        *contents,
        metadata=meta,
    )
