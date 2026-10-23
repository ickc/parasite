"""Links checked after a build, by lychee (https://lychee.cli.rs), offline.

Every link and media reference from the site's files to the site's files must resolve:
it guards what the build copies by reference (see :mod:`para.media`), and the links
pages make to each other. lychee reads the HTML (and the CSS of its <style> elements) as
written, raw HTML included; links out of the site are not checked, nor are
``style`` attributes and CSS files.
"""

from __future__ import annotations

import json
import shutil
import subprocess  # nosec
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Sequence

logger = getLogger(__name__)


def check_links(output_dir: Path, exclude: Sequence[str] = (), exclude_path: Sequence[str] = ()) -> int:
    """The broken links in ``output_dir``, logged; how many. ``exclude`` are regular
    expressions of links (``file://`` URLs, for the site's files) not to check,
    ``exclude_path`` of files not to read."""
    lychee = shutil.which("lychee")
    if lychee is None:
        logger.warning("links not checked: lychee is not installed (https://lychee.cli.rs)")
        return 0
    root = Path(output_dir).resolve()
    cmd = [lychee, "--offline", "--no-progress", "--format", "json", "--root-dir", str(root)]
    for pattern in exclude:
        cmd += ["--exclude", pattern]
    for pattern in exclude_path:
        cmd += ["--exclude-path", pattern]
    res = subprocess.run([*cmd, "--", str(root)], capture_output=True, text=True)  # nosec
    # 0: none broken, 2: some broken; anything else is lychee failing
    if res.returncode not in (0, 2):
        raise RuntimeError(f"lychee failed ({res.returncode}): {res.stderr.strip()}")
    errors = json.loads(res.stdout).get("error_map", {})
    n = 0
    for source in sorted(errors):
        page = Path(source).relative_to(root) if Path(source).is_relative_to(root) else source
        for error in errors[source]:
            url = error["url"].removeprefix(root.as_uri() + "/")
            logger.error("broken link in %s: %s", page, url)
            n += 1
    logger.info("links: %s broken", n)
    return n
