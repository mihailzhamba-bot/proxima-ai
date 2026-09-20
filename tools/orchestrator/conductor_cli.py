#!/usr/bin/env python3
"""Conductor CLI - the only command surface the Hermes brain is allowed to use.

Hermes (on another host) reaches this through an SSH forced command, so every
verb here is deliberately narrow and returns JSON. Judgement lives in Hermes;
this file only does deterministic work: read state, move the queue, dispatch
workers built from the story text, relay answers, report events.

Nothing here can deploy, touch .github/workflows, force-push or call the WB
API - those limits live in the root-owned wrappers under /usr/local/sbin.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(os.environ.get("CONDUCTOR_REPO_CHECKOUT", "/srv/proxima-ai/conductor-repo-checkout"))
STATE_DIR = Path(os.environ.get("CONDUCTOR_STATE_DIR", "/srv/proxima-ai/conductor"))
STATE_FILE = STATE_DIR / "state.json"
TOOLS = Path(__file__).resolve().parent

STORY_RE = re.compile(r"^[0-9]+\.[0-9]+$")
# stories that need WB tokens or write access to the server: never dispatched
CLAUDE_ONLY = {"1.14", "2.6", "3.0", "3.4"}


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "paused": False,
        "workers": {},        # story -> {conversation, branch, profile, fix_rounds, started}
        "events": [],         # queue of things Hermes has not seen yet
        "last_poll": 0,
        "priority": [],       # stories Mike asked for first
        "skipped": [],
    }


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE_FILE)


def emit(payload: dict) -> int:
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def add_event(state: dict, kind: str, story: str, text: str) -> None:
    state["events"].append({
        "ts": int(time.time()),
        "kind": kind,          # question | blocked | ready | ci-red | note
        "story": story,
        "text": text[:2000],
    })


def sprint_status_path() -> Path:
    return REPO / "_bmad-output/implementation-artifacts/sprint-status.yaml"


def read_sprint() -> dict:
    """story key -> status, parsed without a yaml dependency (flat file by design)."""
    out: dict[str, str] = {}
    path = sprint_status_path()
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^  ([0-9]+-[0-9]+-[^:]+): (\S+)$", line)
        if m:
            key, status = m.group(1), m.group(2)
            num = re.match(r"^([0-9]+)-([0-9]+)-", key)
            if num:
                out[f"{num.group(1)}.{num.group(2)}"] = status
    return out


def story_order() -> list[str]:
    """Dependency order taken from the epics, not invented here."""
    return ["1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.11", "1.13",
            "2.2", "2.3", "2.4", "2.5", "3.1"]


def next_story(state: dict) -> str | None:
    statuses = read_sprint()
    for story in state.get("priority", []) + story_order():
        if story in state.get("skipped", []) or story in CLAUDE_ONLY:
            continue
        if statuses.get(story, "backlog") != "backlog":
            continue
        if story in state["workers"]:
            continue
        # every earlier story of the same epic must be done
        epic = story.split(".")[0]
        earlier = [s for s in story_order()
                   if s.split(".")[0] == epic and _num(s) < _num(story)]
        if all(statuses.get(s) == "done" for s in earlier):
            return story
    return None


def _num(story: str) -> tuple[int, int]:
    a, b = story.split(".")
    return int(a), int(b)


def run_tool(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(TOOLS / script), *args],
                          capture_output=True, text=True, timeout=900)


def cmd_status(state: dict, _args) -> int:
    workers = []
    for story, w in state["workers"].items():
        res = run_tool("worker_status.sh", w["conversation"])
        workers.append({
            "story": story,
            "branch": w.get("branch"),
            "profile": w.get("profile"),
            "fix_rounds": w.get("fix_rounds", 0),
            "detail": (res.stdout or res.stderr).strip()[:200],
        })
    return emit({
        "ok": True,
        "paused": state["paused"],
        "workers": workers,
        "pending_events": len(state["events"]),
        "next_story": next_story(state),
        "sprint": read_sprint(),
    })


def cmd_queue(state: dict, _args) -> int:
    statuses = read_sprint()
    return emit({
        "ok": True,
        "order": story_order(),
        "statuses": {s: statuses.get(s, "backlog") for s in story_order()},
        "priority": state.get("priority", []),
        "skipped": state.get("skipped", []),
        "claude_only": sorted(CLAUDE_ONLY),
        "next_story": next_story(state),
        "blocked_by": {s: blocked_by(s) for s in story_order()
                       if statuses.get(s, "backlog") == "backlog" and blocked_by(s)},
    })


def blocked_by(story: str) -> list[str]:
    """Which earlier stories of the same epic are not done yet."""
    statuses = read_sprint()
    epic = story.split(".")[0]
    return [s for s in story_order()
            if s.split(".")[0] == epic and _num(s) < _num(story)
            and statuses.get(s) != "done"]


def cmd_go(state: dict, args) -> int:
    story = args.story
    if not STORY_RE.match(story):
        return emit({"ok": False, "error": "bad story id"})
    if story in CLAUDE_ONLY:
        return emit({"ok": False, "error": f"story {story} requires Mike (WB tokens / server write)"})
    state["priority"] = [story] + [s for s in state.get("priority", []) if s != story]
    state["skipped"] = [s for s in state.get("skipped", []) if s != story]
    save_state(state)
    waiting = blocked_by(story)
    return emit({
        "ok": True,
        "priority": state["priority"],
        "next_story": next_story(state),
        "blocked_by": waiting,
        "note": (f"история {story} в приоритете, но сначала должны закрыться: "
                 + ", ".join(waiting)) if waiting else f"история {story} пойдёт следующей",
    })


def cmd_skip(state: dict, args) -> int:
    story = args.story
    if not STORY_RE.match(story):
        return emit({"ok": False, "error": "bad story id"})
    state["skipped"] = sorted(set(state.get("skipped", []) + [story]))
    state["priority"] = [s for s in state.get("priority", []) if s != story]
    save_state(state)
    return emit({"ok": True, "skipped": state["skipped"], "next_story": next_story(state)})


def cmd_stop(state: dict, _args) -> int:
    state["paused"] = True
    save_state(state)
    return emit({"ok": True, "paused": True, "note": "running workers keep going; nothing new is dispatched"})


def cmd_start(state: dict, _args) -> int:
    state["paused"] = False
    save_state(state)
    return emit({"ok": True, "paused": False, "next_story": next_story(state)})


def cmd_answer(state: dict, args) -> int:
    story = args.story
    worker = state["workers"].get(story)
    if not worker:
        return emit({"ok": False, "error": f"no active worker for story {story}"})
    msg = STATE_DIR / f"answer-{story}-{int(time.time())}.txt"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    msg.write_text("Ответ Mike на твой вопрос:\n\n" + args.text +
                   "\n\nПродолжай работу с этим ответом.\n", encoding="utf-8")
    res = run_tool("send_fix.sh", worker["conversation"], str(msg))
    ok = res.returncode == 0
    if ok:
        add_event(state, "note", story, "ответ Mike передан воркеру")
        save_state(state)
    return emit({"ok": ok, "story": story, "detail": (res.stderr or res.stdout).strip()[:200]})


def cmd_poll(state: dict, _args) -> int:
    events = state.get("events", [])
    state["events"] = []
    state["last_poll"] = int(time.time())
    save_state(state)
    return emit({"ok": True, "events": events, "count": len(events)})


def cmd_report(state: dict, _args) -> int:
    statuses = read_sprint()
    done = [s for s in story_order() if statuses.get(s) == "done"]
    review = [s for s in story_order() if statuses.get(s) == "review"]
    return emit({
        "ok": True,
        "done": done,
        "in_review": review,
        "in_progress": sorted(state["workers"]),
        "paused": state["paused"],
        "waiting_mike": sorted(CLAUDE_ONLY),
        "next_story": next_story(state),
    })


def cmd_dispatch(state: dict, args) -> int:
    """Build the dispatch text from repo files and start a worker."""
    story = args.story
    if not STORY_RE.match(story) or story in CLAUDE_ONLY:
        return emit({"ok": False, "error": "story not dispatchable"})
    if state["paused"]:
        return emit({"ok": False, "error": "queue is paused"})
    if len(state["workers"]) >= 3:
        return emit({"ok": False, "error": "no free slot (3 workers max)"})
    if story in state["workers"]:
        return emit({"ok": False, "error": "already running"})

    text = build_dispatch(story)
    if not text:
        return emit({"ok": False, "error": f"story {story} not found in epics.md"})
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"dispatch-{story}.txt"
    path.write_text(text, encoding="utf-8")

    epic = story.split(".")[0]
    branch = f"feat/{'m01' if epic == '1' else 'm03' if epic == '2' else 'm01b'}-story-{story}"
    profile = args.profile or ("fedor" if len(state["workers"]) % 2 == 0 else "glm")
    res = run_tool("launch_worker.sh", branch, "origin/main", str(path), profile)
    cid = (res.stdout or "").strip().splitlines()[-1] if res.returncode == 0 else ""
    if res.returncode != 0 or not cid:
        return emit({"ok": False, "error": (res.stderr or res.stdout).strip()[:300]})

    state["workers"][story] = {
        "conversation": cid, "branch": branch, "profile": profile,
        "fix_rounds": 0, "started": int(time.time()),
    }
    save_state(state)
    return emit({"ok": True, "story": story, "branch": branch, "profile": profile, "conversation": cid})


def build_dispatch(story: str) -> str:
    """Assemble the worker prompt from epics.md + the spine. No invention here."""
    epics = REPO / "_bmad-output/planning-artifacts/epics.md"
    if not epics.exists():
        return ""
    body = epics.read_text(encoding="utf-8")
    m = re.search(rf"^### Story {re.escape(story)}:(.*?)(?=^### Story |\Z)", body, re.S | re.M)
    if not m:
        return ""
    story_text = f"### Story {story}:{m.group(1).rstrip()}"

    ad_map = {
        "1.3": "AD-2, AD-3, AD-4, AD-11, AD-13", "1.4": "AD-2, AD-3, AD-13",
        "1.5": "AD-2, AD-6", "1.6": "AD-2, AD-7", "1.7": "AD-3, AD-11",
        "1.8": "AD-12", "1.11": "AD-7, AD-9", "1.13": "AD-15",
        "2.2": "AD-9, AD-10", "2.3": "AD-8", "2.4": "AD-9", "2.5": "AD-9",
        "3.1": "AD-5",
    }
    ads = ad_map.get(story, "релевантные AD по таблице ORCHESTRATOR.md")
    return f"""Ты - исполнитель единицы работы Story {story} проекта PROXIMA AI. Работай автономно до конца, вопросов по ходу не задавай - непонятное собери в раздел «Открытые вопросы» финального отчёта.

Окружение подготовлено: репозиторий ./proxima-ai, ветка уже создана от main; сети к GitHub нет. Справочные НЕЗАКОММИЧЕННЫЕ docs/state/ и _bmad-output/ - читать, не стейджить.

Прочитай первым делом: AGENTS.md; текст истории ниже дословно; в _bmad-output/planning-artifacts/architecture/architecture-proxima-ai-2026-08-30/ARCHITECTURE-SPINE.md разделы {ads} (следуй им дословно); docs/state/API-FACTS.md, если история трогает WB API.

{story_text}

Жёсткие правила: существующие db/migrations не менять (только новая, additive, self-checksum); tools/verify_*.py, .github/workflows/*, auth-зону webapp (src/lib/auth*, src/app/api/auth/, src/app/login/, src/lib/db/) и services/control-plane/src/proxima/ не трогать; сеть в тестах запрещена; git add только своих файлов; скрипты bash-3.2-совместимые (без extglob/mapfile/ассоциативных массивов); значения секретов нигде не появляются; **факта нет в документах репо - это вопрос в отчёт, а не выдумка**.

Гейт: PUPPETEER_SKIP_DOWNLOAD=1 make verify зелёный целиком. push и PR не делать.

Финальный отчёт: коммиты (hash + subject), хвост make verify с PASS-строками, список созданных файлов, «Открытые вопросы» (пусто - так и напиши).
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="conductor command surface")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for verb in ("status", "queue", "stop", "start", "poll", "report"):
        sub.add_parser(verb)
    for verb in ("go", "skip"):
        p = sub.add_parser(verb)
        p.add_argument("story")
    p = sub.add_parser("answer")
    p.add_argument("story")
    p.add_argument("text")
    p = sub.add_parser("dispatch")
    p.add_argument("story")
    p.add_argument("--profile", choices=["fedor", "glm"], default=None)
    args = parser.parse_args()

    state = load_state()
    handlers = {
        "status": cmd_status, "queue": cmd_queue, "go": cmd_go, "skip": cmd_skip,
        "stop": cmd_stop, "start": cmd_start, "answer": cmd_answer,
        "poll": cmd_poll, "report": cmd_report, "dispatch": cmd_dispatch,
    }
    try:
        return handlers[args.cmd](state, args)
    except subprocess.TimeoutExpired:
        return emit({"ok": False, "error": "tool timeout"})
    except Exception as exc:  # never leak a traceback to the SSH caller
        return emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]})


if __name__ == "__main__":
    sys.exit(main())
