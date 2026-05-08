"""Promote the ``[Unreleased]`` section in ``CHANGELOG.md`` to a release.

Used by ``just release`` to keep the changelog and the GitHub Releases
page in sync with what's actually being shipped.

Usage:
    python scripts/release_changelog.py promote X.Y.Z

What it does:

1. Renames the existing ``## [Unreleased]`` heading to
   ``## [X.Y.Z] - YYYY-MM-DD`` (today's local date).
2. Inserts a fresh empty ``## [Unreleased]`` block above the new
   versioned section so the next dev cycle has somewhere to land.
3. Updates the link-reference list at the bottom of the file:
   - rewrites the ``[Unreleased]`` link to compare ``vX.Y.Z...HEAD``;
   - adds a new ``[X.Y.Z]: ...compare/<prev>...vX.Y.Z`` entry, where
     ``<prev>`` is parsed from the *previous* ``[Unreleased]`` link's
     ``compare/<tag>...HEAD`` segment.

Aborts with a non-zero exit if:

- ``CHANGELOG.md`` lacks a ``## [Unreleased]`` heading (nothing to
  promote);
- a ``## [X.Y.Z]`` section already exists (idempotency guard — running
  twice would create duplicates);
- the ``[Unreleased]`` link reference is missing (the file is malformed
  by Keep-a-Changelog conventions).
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

# Trailing whitespace patterns use ``[ \t]*`` instead of ``\s*`` so the
# regex never consumes the trailing newline of the matched line — which
# would collapse the blank line that follows the heading / link line.
_UNRELEASED_HEADING_RE = re.compile(r"^## \[Unreleased\][ \t]*$", re.MULTILINE)
_UNRELEASED_LINK_RE = re.compile(
    r"^\[Unreleased\]:[ \t]+(\S+?)/compare/(?P<prev>\S+?)\.\.\.HEAD[ \t]*$",
    re.MULTILINE,
)


def _versioned_heading_re(version: str) -> re.Pattern[str]:
    # Require a space or end-of-line after ``]`` so ``0.7.3`` doesn't
    # accidentally match an existing ``[0.7.30]`` heading. ``\b`` won't
    # work here — there's no word/non-word boundary between ``]`` and
    # a following space.
    return re.compile(rf"^## \[{re.escape(version)}\](?=[ \t\n])", re.MULTILINE)


def promote(version: str) -> None:
    """Promote ``[Unreleased]`` to ``[version] - <today>`` in CHANGELOG.md."""
    txt = CHANGELOG.read_text()

    if _versioned_heading_re(version).search(txt):
        sys.exit(
            f"CHANGELOG.md already contains a [{version}] section. "
            "Refusing to promote a second time."
        )

    if not _UNRELEASED_HEADING_RE.search(txt):
        sys.exit("CHANGELOG.md is missing the '## [Unreleased]' heading.")

    link_match = _UNRELEASED_LINK_RE.search(txt)
    if link_match is None:
        sys.exit(
            "CHANGELOG.md is missing the '[Unreleased]: .../compare/<tag>...HEAD' "
            "link reference. Cannot determine the previous release tag."
        )

    base_url = link_match.group(1)
    prev_tag = link_match.group("prev")
    today = date.today().isoformat()
    new_tag = f"v{version}"

    # 1. Heading: insert the new versioned section above the existing
    #    [Unreleased] heading. The blank line above ### Added (or
    #    whatever the first section is) is preserved by the regex
    #    leaving the trailing newline of the [Unreleased] line intact.
    txt = _UNRELEASED_HEADING_RE.sub(
        f"## [Unreleased]\n\n## [{version}] - {today}",
        txt,
        count=1,
    )

    # 2. Link refs: rewrite [Unreleased] to point at the new tag and
    #    insert a [version] entry directly below it.
    new_unreleased_link = f"[Unreleased]: {base_url}/compare/{new_tag}...HEAD"
    new_release_link = f"[{version}]: {base_url}/compare/{prev_tag}...{new_tag}"
    txt = _UNRELEASED_LINK_RE.sub(
        f"{new_unreleased_link}\n{new_release_link}",
        txt,
        count=1,
    )

    CHANGELOG.write_text(txt)
    print(f"Promoted [Unreleased] -> [{version}] - {today} (prev: {prev_tag})")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: release_changelog.py promote X.Y.Z")
    cmd = sys.argv[1]
    if cmd == "promote":
        if len(sys.argv) != 3:
            sys.exit("Usage: release_changelog.py promote X.Y.Z")
        promote(sys.argv[2])
    else:
        sys.exit(f"Unknown command: {cmd!r}")


if __name__ == "__main__":
    main()
