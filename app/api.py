"""Functions the desktop window calls."""

from __future__ import annotations

import os

from app.runner import launch, list_sources, status
from app.store import (
    append_chat,
    check_bilibili,
    create_topic,
    get_item,
    get_topic,
    import_inbox,
    list_items,
    list_topics,
    pick_item,
    read_chat,
    review_item,
    save_topic,
)


class Api:
    def list_topics(self) -> dict:
        return _ok(topics=list_topics())

    def create_topic(self, name: str) -> dict:
        return _call(lambda: {"topic": create_topic(name), "topics": list_topics()})

    def get_topic(self, name: str) -> dict:
        return _call(lambda: {"topic": get_topic(name)})

    def save_topic(self, name: str, interest: str, keywords: str, questions: str, bilibili: str) -> dict:
        return _call(
            lambda: {
                "topic": save_topic(
                    name,
                    {
                        "interest": interest,
                        "keywords": keywords,
                        "questions": questions,
                        "bilibili": bilibili,
                    },
                )
            }
        )

    def check_bilibili(self, text: str) -> dict:
        return _ok(**check_bilibili(text))

    def list_sources(self) -> dict:
        found = list_sources()
        return _ok(sources=found["sources"], errors=found["errors"])

    def launch_source(self, name: str, source_id: str, interest: str, keywords: str, questions: str, bilibili: str) -> dict:
        def run() -> dict:
            if source_id == "bilibili":
                checked = check_bilibili(bilibili)
                if not checked["ok"]:
                    raise ValueError(checked["summary"])
            topic = save_topic(
                name,
                {
                    "interest": interest,
                    "keywords": keywords,
                    "questions": questions,
                    "bilibili": bilibili,
                },
            )
            run_status = launch(name, source_id)
            return {"topic": topic, "status": run_status}

        return _call(run)

    def source_status(self, name: str, source_id: str) -> dict:
        return _call(lambda: {"status": status(name, source_id), "topic": get_topic(name)})

    def import_inbox(self, name: str) -> dict:
        return _call(lambda: {"result": import_inbox(name), "items": list_items(name), "topic": get_topic(name)})

    def list_items(self, name: str) -> dict:
        return _call(lambda: {"items": list_items(name)})

    def get_item(self, name: str, item_id: str) -> dict:
        return _call(lambda: {"item": get_item(name, item_id)})

    def pick_item(self, name: str, current: str) -> dict:
        return _call(lambda: {"item": pick_item(name, current or None)})

    def review_item(self, name: str, item_id: str, status: str, judgment: str) -> dict:
        return _call(lambda: {"item": review_item(name, item_id, status, judgment), "topic": get_topic(name)})

    def read_chat(self, name: str) -> dict:
        return _call(lambda: {"messages": read_chat(name)})

    def send_chat(self, name: str, text: str) -> dict:
        def run() -> dict:
            message = str(text).strip()
            if not message:
                raise ValueError("先写问题")
            append_chat(name, "user", message)
            append_chat(name, "desk", "模型接口还没接上。这句话已经记在本主题的 chat.md。")
            return {"messages": read_chat(name)}

        return _call(run)

    def open_url(self, url: str) -> dict:
        def run() -> dict:
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise ValueError("只能打开 http 链接")
            os.startfile(url)  # noqa: S606 - user asked to open the video page
            return {}

        return _call(run)


def _ok(**payload: object) -> dict:
    return {"ok": True, **payload}


def _call(fn) -> dict:
    try:
        return _ok(**fn())
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
