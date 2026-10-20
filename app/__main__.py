"""Open the Reflexus window. `python -m app ingest <主题>` imports one inbox."""

from __future__ import annotations

import json
import sys

from app.api import Api
from app.paths import UI
from app.store import import_inbox


def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "ingest":
        if len(argv) != 3:
            print("用法: python -m app ingest <主题>", file=sys.stderr)
            return 2
        result = import_inbox(argv[2])
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result["errors"] else 0

    import webview

    webview.create_window(
        "Reflexus",
        str(UI / "index.html"),
        js_api=Api(),
        width=1180,
        height=820,
        min_size=(960, 680),
        text_select=True,
    )
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
