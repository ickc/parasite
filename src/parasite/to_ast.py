from __future__ import annotations

from typing import TYPE_CHECKING

import panflute as pf

if TYPE_CHECKING:
    from typing import List
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
