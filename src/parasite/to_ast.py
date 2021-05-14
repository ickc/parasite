from __future__ import annotations

from typing import TYPE_CHECKING
from collections import defaultdict

import panflute as pf

if TYPE_CHECKING:
    from typing import List, Dict
    from .data import Post


def posts_to_index_ast(
    posts: List[Post],
    title: str,
    n_jumbotron: int = 1,
    n_grid: int = 2,
    index_include_jumbotron: bool = True,
) -> pf.elements.Doc:

    def post_to_dict(post: Post) -> dict:
        res = {
            'url': str(post.url),
            'teaser': pf.MetaBlocks(*post.teaser),
        }
        if post.title is not None:
            res['title'] = post.title
        if post.previewimage is not None:
            res['previewimage'] = post.previewimage
        if post.author is not None:
            res['author'] = post.author
        if post.date is not None:
            res['date'] = post.date
        return res

    meta = {
        'title': title,
    }

    temp_index = []
    temp = []
    for post in posts[:n_jumbotron]:
        data = post_to_dict(post)
        temp.append(data)
        if index_include_jumbotron:
            temp_index.append(data)
    meta['index_jumbotron'] = temp

    temp = []
    for post in posts[n_jumbotron:n_jumbotron + n_grid]:
        data = post_to_dict(post)
        temp.append(data)
        if index_include_jumbotron:
            temp_index.append(data)
    meta['index_grid'] = temp

    for post in posts[n_jumbotron + n_grid:]:
        temp_index.append(post_to_dict(post))
    meta['index'] = temp_index

    return pf.elements.Doc(metadata=meta)


def posts_to_tag_ast(
    categories: Dict[str, List[Post]],
    tags: Dict[str, List[Post]],
    font_size_min: int = 70,
    font_size_max: int = 280,
) -> pf.elements.Doc:
    meta = {
        'title': 'Tags and Categories',
    }

    for case, dict_ in (
        ('categories', categories),
        ('tags', tags),
    ):
        counts_dict = {name: len(list_) for name, list_ in dict_.items()}
        counts = counts_dict.values()
        min_ = min(counts)
        max_ = max(counts)
        m = (font_size_max - font_size_min) / (max_ - min_)
        c = font_size_min - m * min_
        temp = []
        meta[f'archive-{case}'] = temp
        for name, count in counts_dict.items():
            font_size = m * count + c
            flat_name = '/'.join(name) if type(name) == tuple else name
            temp.append({
                'name': flat_name,
                'font_size': font_size,
            })
    return pf.elements.Doc(metadata=meta)


def posts_to_archive_ast(
    posts: List[Post],
) -> pf.elements.Doc:
    root = '..'

    meta = {
        'title': 'Archive',
    }

    res = defaultdict(lambda: defaultdict(list))
    for page in posts:
        title = page.title
        url = page.url
        date = page.date
        time = page.time
        res[time.year][time.strftime("%B")].append((date, title, url))

    contents = []
    for year, datas in res.items():
        contents.append(pf.Header(pf.Str(str(year)), level=1))
        for month, data in datas.items():
            contents.append(pf.Header(pf.Str(month), level=2))
            lis = []
            for (date, title, url) in data:
                lis.append(
                    pf.ListItem(
                        pf.Plain(
                            pf.Link(
                                pf.Str(f'{date} — {title}'),
                                url=f'{root}/{url}',
                            )
                        )
                    )
                )
            contents.append(pf.BulletList(*lis))

    return pf.elements.Doc(
        *contents,
        metadata=meta,
    )
