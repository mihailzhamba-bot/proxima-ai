#!/usr/bin/env python3
"""verify_public_hygiene.py - гард-рейл Д-сплита (D40).

Публичное дерево не имеет права содержать внутренности: боевые IP, имена
кабинетов/владельцев, внутренние хосты, приватные пути. Скрипт сканирует все
гит-трекнутые файлы и падает с перечислением файл:строка:фрагмент.

Негативный тест: создай файл с `135.106.186.210` и запусти снова - должен быть FAIL.
Запуск: `make hygiene` (входит в `make verify`).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS: list[tuple[str, str]] = [
    # Боевые IP (карта SERVERS, сечение 2026-09)
    (r"135\.106\.\d+\.\d+", "внутренний IP 135.106.x (парк Selectel/Москва)"),
    (r"148\.253\.\d+\.\d+", "внутренний IP 148.253.x (agent-server)"),
    (r"111\.88\.\d+\.\d+", "внутренний IP 111.88.x (Москва)"),
    (r"153\.56\.134\.\d+", "внутренний IP 153.56.134.x (NL home.main)"),
    (r"91\.184\.253\.\d+", "внутренний IP 91.184.253.x (exit)"),
    (r"139\.100\.\d+\.\d+", "внутренний IP 139.100.x (rania)"),
    (r"136\.234\.\d+\.\d+", "внутренний IP 136.234.x (мост)"),
    # Личные имена/кабинеты
    (r"\bBogatova\b", "имя кабинета (Bogatova Belle Robe)"),
    (r"Амирова", "имя владельца кабинета"),
    (r"Amirova", "имя владельца кабинета"),
    (r"amirova-", "tenant id владельца кабинета"),
    # Внутренние хосты и сервисы
    (r"\b(claudette|harper|mckenzie|simone-mj|alecia|corina-iva|jazmin-akadem|rania|tisha-hr|home\.main)\b",
     "внутреннее имя хоста"),
    (r"\b(vpn\.mikez\.ru|loop\.mikez\.ru|prxm-serv\.ru)\b", "внутренний домен"),
    # Приватные деревья, которых не должно быть в публичном индексе
    (r"proxima-ai-ops/(docs|_bmad)", "ссылка внутрь приватных путей ops"),
]

# Файлы, где допустимы ложные срабатывания (сам гард-рейл, его тесты и правила).
ALLOWED_PREFIXES = (
    "tools/verify_public_hygiene.py",
    "docs/",  # отсутствует в публичном дереве; защита для локальных композитных прогонов
)


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def main() -> int:
    if subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True).returncode != 0:
        print("hygiene: SKIP (not a git repository)")
        return 0

    compiled = [(re.compile(pattern), reason) for pattern, reason in PATTERNS]
    violations: list[str] = []
    scanned = 0

    for rel_path in tracked_files():
        path = Path(rel_path)
        if any(rel_path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # pragma: no cover
            violations.append(f"{rel_path}:0: unreadable ({exc})")
            continue
        scanned += 1
        for lineno, line in enumerate(text.splitlines(), start=1):
            for regex, reason in compiled:
                if regex.search(line):
                    fragment = line.strip()[:120]
                    violations.append(
                        f"{rel_path}:{lineno}: {reason} :: {fragment}"
                    )

    if violations:
        print(f"hygiene: FAIL - {len(violations)} нарушений (приватное в публичном):")
        for item in violations[:50]:
            print(f"  {item}")
        if len(violations) > 50:
            print(f"  ... и ещё {len(violations) - 50}")
        return 1

    print(f"hygiene: PASS ({scanned} files scanned, {len(PATTERNS)} rule families)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
