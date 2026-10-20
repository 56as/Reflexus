"""Start a source command and keep its latest output for the window."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from app.paths import SOURCES
from app.store import import_inbox, topic_dir

_LOCK = threading.Lock()
_RUNS: dict[tuple[str, str], dict] = {}


def list_sources() -> dict:
    SOURCES.mkdir(parents=True, exist_ok=True)
    sources = []
    errors = []
    for file in sorted(SOURCES.glob("*.json")):
        try:
            sources.append(_load_source(file))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{file.name}: {exc}")
    return {"sources": sources, "errors": errors}


def launch(name: str, source_id: str) -> dict:
    source = _source_by_id(source_id)
    key = (name, source_id)
    with _LOCK:
        current = _RUNS.get(key)
        if current and current["state"] == "running":
            raise ValueError("这个子功能正在运行")
    cwd = Path(source["cwd"])
    if not cwd.is_dir():
        raise ValueError(f"找不到启动目录 {cwd}")
    folder = topic_dir(name)
    env = os.environ.copy()
    env.update(source["env"])
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = env.get("PYTHONIOENCODING", "utf-8")
    env["RESEARCH_TOPIC"] = name
    env["RESEARCH_TOPIC_DIR"] = str(folder)
    env["RESEARCH_INBOX"] = str(folder / "inbox")
    env["RESEARCH_TOPIC_FILE"] = str(folder / "topic.md")
    started = datetime.now().astimezone()
    try:
        process = subprocess.Popen(
            source["command"],
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except OSError as exc:
        raise ValueError(f"无法启动：{exc}") from exc
    state = {
        "state": "running",
        "exit_code": None,
        "tail": "",
        "lines": [],
        "created": 0,
        "updated": 0,
        "errors": [],
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": "",
        "message": "运行中",
    }
    with _LOCK:
        _RUNS[key] = state
    _persist(name, source_id, state)
    thread = threading.Thread(
        target=_watch,
        args=(name, source_id, process, started),
        daemon=True,
        name=f"reflexus-{source_id}",
    )
    thread.start()
    return status(name, source_id)


def status(name: str, source_id: str) -> dict:
    key = (name, source_id)
    with _LOCK:
        current = _RUNS.get(key)
        if current:
            return _public(current)
    file = topic_dir(name) / "logs" / f"{source_id}.json"
    if file.is_file():
        try:
            saved = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        if isinstance(saved, dict) and saved.get("state"):
            return _public(saved)
    return _public(
        {
            "state": "idle",
            "exit_code": None,
            "tail": "",
            "created": 0,
            "updated": 0,
            "errors": [],
            "started_at": "",
            "finished_at": "",
            "message": "还没有运行",
        }
    )


def _watch(name: str, source_id: str, process: subprocess.Popen[str], started: datetime) -> None:
    key = (name, source_id)
    assert process.stdout is not None
    for line in process.stdout:
        with _LOCK:
            state = _RUNS[key]
            state["lines"].append(line.rstrip("\n"))
            state["lines"] = state["lines"][-40:]
            state["tail"] = "\n".join(state["lines"])
        _persist(name, source_id, _RUNS[key])
    code = process.wait()
    imported = import_inbox(name, since=started)
    message = _finish_message(code, imported)
    with _LOCK:
        state = _RUNS[key]
        state["state"] = "done" if code == 0 and not imported["errors"] else "error"
        state["exit_code"] = code
        state["created"] = imported["created"]
        state["updated"] = imported["updated"]
        state["errors"] = imported["errors"]
        state["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        state["message"] = message
        snapshot = dict(state)
    _persist(name, source_id, snapshot)


def _finish_message(code: int | None, imported: dict) -> str:
    taken = imported["created"] + imported["updated"]
    if code == 0 and not imported["errors"]:
        return f"已结束，导入 {taken} 条"
    detail = f"退出码 {code}"
    if imported["errors"]:
        detail += "，有条目没能导入"
    if taken:
        detail += f"，仍导入 {taken} 条"
    return detail


def _persist(name: str, source_id: str, state: dict) -> None:
    folder = topic_dir(name) / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / f"{source_id}.json"
    payload = _public(state)
    file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _public(state: dict) -> dict:
    return {
        "state": state.get("state", "idle"),
        "exit_code": state.get("exit_code"),
        "tail": state.get("tail", ""),
        "created": state.get("created", 0),
        "updated": state.get("updated", 0),
        "errors": list(state.get("errors", [])),
        "started_at": state.get("started_at", ""),
        "finished_at": state.get("finished_at", ""),
        "message": state.get("message", ""),
    }


def _source_by_id(source_id: str) -> dict:
    for source in list_sources()["sources"]:
        if source["id"] == source_id:
            return source
    raise ValueError(f"没有子功能「{source_id}」")


def _load_source(file: Path) -> dict:
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("清单必须是 JSON 对象")
    source_id = data.get("id")
    command = data.get("command")
    cwd = data.get("cwd", "")
    env = data.get("env", {})
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("缺少 id")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        raise ValueError("command 必须是字符串数组")
    if not isinstance(cwd, str):
        raise ValueError("cwd 必须是字符串")
    if not isinstance(env, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in env.items()):
        raise ValueError("env 的键和值都必须是字符串")
    label = data.get("label", source_id)
    if not isinstance(label, str) or not label.strip():
        label = source_id
    return {
        "id": source_id.strip(),
        "label": label.strip(),
        "cwd": cwd,
        "command": command,
        "env": env,
        "cwd_ready": Path(cwd).is_dir() if cwd else False,
    }
