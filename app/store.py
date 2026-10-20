"""Topic folders, inbox import, and the markdown each topic keeps."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime
from pathlib import Path

from app.paths import LIBRARY

SECTIONS = ("兴趣", "关键词", "未决问题", "bilibili")
ITEM_FIELDS = ("source", "external_id", "title", "url", "summary", "body", "extra")
REVIEW_STATES = ("unread", "kept", "dropped", "unsure")
_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def ensure_library() -> None:
    LIBRARY.mkdir(parents=True, exist_ok=True)


def topic_dir(name: str) -> Path:
    return LIBRARY / name


def list_topics() -> list[dict]:
    ensure_library()
    topics = []
    for path in sorted(LIBRARY.iterdir(), key=lambda item: item.name):
        if path.is_dir() and (path / "topic.md").is_file():
            topics.append(_topic_brief(path.name))
    return topics


def create_topic(name: str) -> dict:
    cleaned = _clean_name(name)
    path = topic_dir(cleaned)
    if path.exists():
        raise ValueError(f"已经有主题「{cleaned}」")
    path.mkdir(parents=True)
    (path / "inbox").mkdir()
    (path / "items").mkdir()
    (path / "logs").mkdir()
    (path / "memory.md").write_text("# 长期记忆\n", encoding="utf-8")
    (path / "chat.md").write_text("", encoding="utf-8")
    _write_topic(cleaned, {section: "" for section in SECTIONS}, [])
    return get_topic(cleaned)


def get_topic(name: str) -> dict:
    path = _require_topic(name)
    text = (path / "topic.md").read_text(encoding="utf-8")
    sections, extras = _parse_topic(text)
    inbox = path / "inbox"
    items = _list_item_files(path)
    unread = sum(1 for item in items if item["status"] == "unread")
    return {
        "name": name,
        "interest": sections.get("兴趣", ""),
        "keywords": sections.get("关键词", ""),
        "questions": sections.get("未决问题", ""),
        "bilibili": sections.get("bilibili", ""),
        "extras": extras,
        "dir": str(path),
        "inbox": str(inbox),
        "file": str(path / "topic.md"),
        "inbox_count": len(list(inbox.glob("*.json"))) if inbox.is_dir() else 0,
        "item_count": len(items),
        "unread_count": unread,
    }


def save_topic(name: str, fields: dict) -> dict:
    path = _require_topic(name)
    text = (path / "topic.md").read_text(encoding="utf-8")
    _sections, extras = _parse_topic(text)
    sections = {
        "兴趣": str(fields.get("interest", "")),
        "关键词": str(fields.get("keywords", "")),
        "未决问题": str(fields.get("questions", "")),
        "bilibili": str(fields.get("bilibili", "")),
    }
    _write_topic(name, sections, extras)
    return get_topic(name)


def check_bilibili(text: str) -> dict:
    kinds: set[str] = set()
    errors: list[str] = []
    count = 0
    for index, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        kind = _bilibili_kind(line)
        if kind is None:
            errors.append(f"第 {index} 行无法识别：{line}")
            continue
        kinds.add(kind)
        count += 1
    if len(kinds) > 1:
        errors.append("链接、UP、清单这三种不要写在同一节里。")
    if errors:
        summary = errors[0]
    elif count:
        label = {"url": "条链接", "up": "条 UP", "items": "份清单"}[next(iter(kinds))]
        summary = f"{count} {label}"
    else:
        summary = "这一节是空的"
    return {"ok": not errors, "errors": errors, "summary": summary, "count": count}


def import_inbox(name: str, *, since: datetime | None = None) -> dict:
    path = _require_topic(name)
    inbox = path / "inbox"
    items = path / "items"
    inbox.mkdir(exist_ok=True)
    items.mkdir(exist_ok=True)
    created = 0
    updated = 0
    unchanged = 0
    errors: list[str] = []
    for file in sorted(inbox.glob("*.json")):
        if since is not None:
            modified = datetime.fromtimestamp(file.stat().st_mtime).astimezone()
            if modified < since:
                continue
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
            outcome = _import_payload(items, payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{file.name}: {exc}")
            continue
        if outcome == "created":
            created += 1
        elif outcome == "updated":
            updated += 1
        else:
            unchanged += 1
    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "errors": errors,
    }


def list_items(name: str) -> list[dict]:
    path = _require_topic(name)
    return _list_item_files(path)


def get_item(name: str, item_id: str) -> dict:
    file = _item_file(name, item_id)
    return _read_item(file)


def review_item(name: str, item_id: str, status: str, judgment: str) -> dict:
    if status not in REVIEW_STATES:
        raise ValueError("未知的审阅状态")
    file = _item_file(name, item_id)
    item = _read_item(file)
    item["status"] = status
    item["judgment"] = judgment
    _write_item(file, item)
    return _read_item(file)


def pick_item(name: str, current: str | None = None) -> dict | None:
    items = list_items(name)
    if not items:
        return None
    unread = [item for item in items if item["status"] == "unread" and item["id"] != current]
    pool = unread or [item for item in items if item["id"] != current] or items
    return get_item(name, random.choice(pool)["id"])


def read_chat(name: str) -> list[dict]:
    path = _require_topic(name) / "chat.md"
    if not path.is_file():
        return []
    messages = []
    role = None
    stamp = ""
    buffer: list[str] = []

    def flush() -> None:
        if role is None:
            return
        messages.append({"role": role, "at": stamp, "text": "\n".join(buffer).strip()})

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            flush()
            buffer = []
            heading = line[3:].strip()
            if heading.endswith(" 用户"):
                role = "user"
                stamp = heading[: -len(" 用户")].strip()
            elif heading.endswith(" 平台"):
                role = "desk"
                stamp = heading[: -len(" 平台")].strip()
            else:
                role = "desk"
                stamp = heading
            continue
        if role is not None:
            buffer.append(line)
    flush()
    return [message for message in messages if message["text"]]


def append_chat(name: str, role: str, text: str) -> None:
    path = _require_topic(name)
    chat = path / "chat.md"
    label = "用户" if role == "user" else "平台"
    stamp = _now_text()
    block = f"## {stamp} {label}\n\n{text.strip()}\n\n"
    with chat.open("a", encoding="utf-8") as handle:
        handle.write(block)


def _topic_brief(name: str) -> dict:
    data = get_topic(name)
    return {
        "name": name,
        "interest": data["interest"],
        "unread_count": data["unread_count"],
        "item_count": data["item_count"],
    }


def _require_topic(name: str) -> Path:
    path = topic_dir(name)
    if not path.is_dir() or not (path / "topic.md").is_file():
        raise ValueError(f"没有主题「{name}」")
    return path


def _clean_name(name: str) -> str:
    cleaned = " ".join(str(name).strip().split())
    if not cleaned or cleaned in {".", ".."} or _INVALID_NAME.search(cleaned):
        raise ValueError("主题名不能为空，也不能包含 \\ / : * ? \" < > |")
    return cleaned


def _parse_topic(text: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    sections: dict[str, str] = {}
    extras: list[tuple[str, str]] = []
    current = None
    buffer: list[str] = []

    def flush() -> None:
        if current is None:
            return
        value = "\n".join(buffer).strip()
        if current in SECTIONS and current not in sections:
            sections[current] = value
        else:
            extras.append((current, value))

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current = line[3:].strip()
            buffer = []
            continue
        if current is None:
            continue
        buffer.append(line)
    flush()
    return sections, extras


def _write_topic(name: str, sections: dict[str, str], extras: list[tuple[str, str]]) -> None:
    parts = [f"# {name}", ""]
    for section in SECTIONS:
        parts.extend([f"## {section}", "", sections.get(section, "").strip(), ""])
    for title, body in extras:
        parts.extend([f"## {title}", "", body.strip(), ""])
    topic_dir(name).joinpath("topic.md").write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def _bilibili_kind(line: str) -> str | None:
    if line.startswith(("http://", "https://")):
        return "url"
    if line.startswith("up "):
        return "up"
    if line.startswith("items "):
        return "items"
    return None


def _import_payload(items: Path, payload: object) -> str:
    if not isinstance(payload, dict):
        raise ValueError("条目必须是一个 JSON 对象")
    for field in ("source", "external_id", "title", "url", "body"):
        if not isinstance(payload.get(field), str) or not str(payload.get(field)).strip():
            raise ValueError(f"缺少 {field}")
    source = payload["source"].strip()
    external_id = payload["external_id"].strip()
    if _INVALID_NAME.search(source) or _INVALID_NAME.search(external_id):
        raise ValueError("source 或 external_id 含有不能用于文件名的字符")
    extra = payload.get("extra", {})
    if extra is None:
        extra = {}
    if not isinstance(extra, dict):
        raise ValueError("extra 必须是对象")
    summary = payload.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("summary 必须是字符串")
    incoming = {
        "source": source,
        "external_id": external_id,
        "title": payload["title"].strip(),
        "url": payload["url"].strip(),
        "summary": summary.strip(),
        "body": payload["body"].strip(),
        "extra": extra,
        "status": "unread",
        "judgment": "",
        "collected_at": _now_stamp(),
    }
    file = items / f"{source}_{external_id}.md"
    if file.is_file():
        previous = _read_item(file)
        incoming["status"] = previous["status"]
        incoming["judgment"] = previous["judgment"]
        if _same_item(previous, incoming):
            return "unchanged"
        _write_item(file, incoming)
        return "updated"
    _write_item(file, incoming)
    return "created"


def _same_item(previous: dict, incoming: dict) -> bool:
    keys = ("source", "external_id", "title", "url", "summary", "body", "extra", "status", "judgment")
    return all(previous.get(key) == incoming.get(key) for key in keys)


def _list_item_files(path: Path) -> list[dict]:
    folder = path / "items"
    if not folder.is_dir():
        return []
    found = []
    for file in sorted(folder.glob("*.md")):
        item = _read_item(file)
        found.append(
            {
                "id": file.stem,
                "source": item["source"],
                "external_id": item["external_id"],
                "title": item["title"],
                "url": item["url"],
                "status": item["status"],
                "summary": item["summary"],
            }
        )
    return found


def _item_file(name: str, item_id: str) -> Path:
    path = _require_topic(name) / "items" / f"{item_id}.md"
    if not path.is_file():
        raise ValueError("没有这条材料")
    return path


def _read_item(file: Path) -> dict:
    meta, rest = _split_front_matter(file.read_text(encoding="utf-8"))
    summary = _section(rest, "摘要", "我的判断")
    judgment = _section(rest, "我的判断", "全文")
    body = _section(rest, "全文", None)
    return {
        "id": file.stem,
        "source": meta.get("source", ""),
        "external_id": meta.get("external_id", ""),
        "title": meta.get("title", ""),
        "url": meta.get("url", ""),
        "status": meta.get("status", "unread"),
        "collected_at": meta.get("collected_at", ""),
        "extra": meta.get("extra", {}),
        "summary": summary,
        "judgment": judgment,
        "body": body,
    }


def _write_item(file: Path, item: dict) -> None:
    meta = {
        "source": item["source"],
        "external_id": item["external_id"],
        "title": item["title"],
        "url": item["url"],
        "status": item["status"],
        "collected_at": item["collected_at"],
        "extra": item["extra"],
    }
    front = json.dumps(meta, ensure_ascii=False, indent=2)
    text = (
        f"---\n{front}\n---\n\n"
        f"## 摘要\n\n{item['summary'].strip()}\n\n"
        f"## 我的判断\n\n{item['judgment'].strip()}\n\n"
        f"## 全文\n\n{item['body'].strip()}\n"
    )
    file.write_text(text, encoding="utf-8")


def _split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    return json.loads(text[4:end]), text[end + 5 :].lstrip("\n")


def _section(text: str, name: str, until: str | None) -> str:
    marker = f"## {name}\n"
    start = text.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    if until is None:
        return text[start:].strip()
    end = text.find(f"## {until}\n", start)
    chunk = text[start:] if end < 0 else text[start:end]
    return chunk.strip()


def _now_stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
