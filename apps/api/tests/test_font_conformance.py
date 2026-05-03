"""Cross-stack conformance test: BOT_FONTS (Python) ↔ WIDGET_FONTS (TypeScript).

The widget bundles its own font catalog in `packages/widget/src/fonts.ts`.
The API's Pydantic ``Literal[BotFont]`` allow-list must list exactly the
same keys, otherwise the dashboard could save a font value the widget
can't render (or vice versa).

This test reads the TS file, regex-extracts the keys of the
``WIDGET_FONTS`` const, and asserts the set equals ``BOT_FONTS``.

Skipped (with a clear note) if the TS file does not exist — keeps the
backend test suite green when the widget package hasn't been authored
yet on a feature branch.
"""

import re
from pathlib import Path

import pytest

from src.models.bot import BOT_FONTS

# Repo root resolved relative to this test file.
_FONTS_TS_PATH = Path(__file__).resolve().parents[3] / "packages" / "widget" / "src" / "fonts.ts"

# Match the start of `export const WIDGET_FONTS = { ... }`. We grab the
# matching brace block via balanced-paren walk to keep the regex simple.
_DECL_PATTERN = re.compile(
    r"export\s+const\s+WIDGET_FONTS\s*(?::\s*[^=]+)?=\s*\{",
    re.MULTILINE,
)

# Top-level keys are at depth 1 of the WIDGET_FONTS object literal — quoted
# or unquoted ident, followed by `:`.
_KEY_PATTERN = re.compile(r'^\s*["\']?([a-z][a-z0-9_-]*)["\']?\s*:', re.MULTILINE)


def _extract_widget_fonts_keys(source: str) -> set[str]:
    """Parse keys from `export const WIDGET_FONTS = { ... }`."""
    decl = _DECL_PATTERN.search(source)
    if decl is None:
        raise AssertionError("Could not locate `export const WIDGET_FONTS = { ... }` in fonts.ts")
    # Walk braces from the opening `{` to find the matching `}`.
    start = decl.end() - 1
    depth = 0
    end = -1
    for i in range(start, len(source)):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise AssertionError("Unbalanced braces in WIDGET_FONTS literal")

    body = source[start + 1 : end]
    # Filter to keys at the top level of `body` only — child object braces
    # would otherwise pollute. Track depth inside `body`.
    keys: set[str] = set()
    depth = 0
    line_start = 0
    for i, ch in enumerate(body):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "\n":
            if depth == 0:
                line = body[line_start:i]
                m = _KEY_PATTERN.match(line)
                if m:
                    keys.add(m.group(1))
            line_start = i + 1
    # Tail line (no trailing newline).
    if depth == 0:
        line = body[line_start:]
        m = _KEY_PATTERN.match(line)
        if m:
            keys.add(m.group(1))
    return keys


@pytest.mark.unit
def test_widget_fonts_matches_bot_fonts() -> None:
    """The TS WIDGET_FONTS keys must exactly equal Python BOT_FONTS values."""
    if not _FONTS_TS_PATH.exists():
        pytest.skip(
            f"{_FONTS_TS_PATH} not present yet — landing in widget rendering "
            "commit (#88). This test enforces alignment once it exists."
        )

    source = _FONTS_TS_PATH.read_text(encoding="utf-8")
    ts_keys = _extract_widget_fonts_keys(source)
    py_keys = set(BOT_FONTS)

    assert ts_keys == py_keys, (
        f"Font catalog drift detected.\n"
        f"  Only in TS (packages/widget/src/fonts.ts): {ts_keys - py_keys}\n"
        f"  Only in Py (apps/api/src/models/bot.py BOT_FONTS): {py_keys - ts_keys}\n"
        "Update both sides to keep them in sync."
    )
