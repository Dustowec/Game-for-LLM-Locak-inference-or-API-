#!/usr/bin/env python3
"""
translate_cyrillic.py — замена кириллических литералов на английские по dict.json.

Запуск:
    python translate_cyrillic.py -d dict.json -f "burt/*.py" --backup
    python translate_cyrillic.py -d dict.json -f "tests/*.py" --backup
    python translate_cyrillic.py -d dict.json -f config.py conftest.py quests_templates.json --backup

Флаги:
    -d, --dictionary   путь к JSON-словарю (по умолчанию dict.json)
    -f, --files        файлы / glob / директории
    --backup           создавать .bak перед изменением
    --dry-run          показать, что будет заменено, без записи

Особенности:
- длинные фразы заменяются первыми (sort by len desc);
- сохранение регистра (Привет -> Hello, ПРИВЕТ -> HELLO);
- границы слов через lookaround (кириллица/латиница/цифры/_);
- не трогает .bak, HANDOFF*.md, CyrDict.md, replicas.json (контент NPC);
- автоопределение кодировки UTF-8 / CP1251.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


# Файлы, которые НЕ обрабатываем (контент для игрока / документация)
SKIP_NAMES = {"CyrDict.md", "replicas.json"}


def load_dict(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {k.strip(): v.strip() for k, v in data.items() if k.strip() and v.strip()}


def collect_targets(patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for p in patterns:
        candidates: list[Path]
        if any(c in p for c in "*?["):
            candidates = list(Path(".").glob(p))
        else:
            candidates = [Path(p)]
        for path in candidates:
            if not path.is_file():
                continue
            if path.suffix == ".bak":
                continue
            if path.name in SKIP_NAMES:
                continue
            if path.name.startswith("HANDOFF"):
                continue
            rp = path.resolve()
            if rp in seen:
                continue
            seen.add(rp)
            files.append(path)
    return sorted(files)


def build_regex(dictionary: dict[str, str]) -> re.Pattern:
    keys = sorted(dictionary.keys(), key=len, reverse=True)
    parts = [re.escape(k) for k in keys]
    pattern = (
        r"(?<![А-Яа-яЁёA-Za-z0-9_])"
        + "(?:" + "|".join(parts) + ")"
        + r"(?![А-Яа-яЁёA-Za-z0-9_])"
    )
    return re.compile(pattern, re.IGNORECASE)


def preserve_case(src: str, dst: str) -> str:
    if src.isupper():
        return dst.upper()
    if src.istitle():
        return dst[:1].upper() + dst[1:]
    return dst


def replace_text(text: str, dictionary: dict[str, str], regex: re.Pattern) -> tuple[str, int]:
    lower_map = {k.lower(): v for k, v in dictionary.items()}

    def _sub(m: re.Match) -> str:
        found = m.group(0)
        repl = lower_map.get(found.lower())
        if repl is None:
            repl = dictionary.get(found)
            if repl is None:
                return found
        # для длинных фраз / шаблонов с {} / заголовков [] регистр не трогаем
        if "{" in found or "[" in found or len(found.split()) > 3:
            return repl
        return preserve_case(found, repl)

    new_text, n = regex.subn(_sub, text)
    return new_text, n


def process_file(path: Path, dictionary: dict[str, str], regex: re.Pattern,
                 backup: bool, dry_run: bool) -> int:
    try:
        text = path.read_text(encoding="utf-8")
        enc = "utf-8"
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="cp1251")
            enc = "cp1251"
        except Exception as e:
            print(f"❌ {path}: {e}", file=sys.stderr)
            return 0

    new_text, n = replace_text(text, dictionary, regex)
    if n == 0:
        print(f"ℹ️  {path}: без изменений")
        return 0

    if dry_run:
        print(f"🔍 {path}: {n} замен (dry-run)")
        return n

    if backup:
        bak = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, bak)

    path.write_text(new_text, encoding=enc)
    print(f"✅ {path}: {n} замен")
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--dictionary", default="dict.json")
    ap.add_argument("-f", "--files", nargs="+", required=True)
    ap.add_argument("--backup", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    dpath = Path(args.dictionary)
    if not dpath.is_file():
        print(f"❌ Словарь не найден: {dpath}", file=sys.stderr)
        return 1

    dictionary = load_dict(dpath)
    if not dictionary:
        print("❌ Пустой словарь", file=sys.stderr)
        return 1
    print(f"📚 Слов в словаре: {len(dictionary)}")

    regex = build_regex(dictionary)
    files = collect_targets(args.files)
    if not files:
        print("❌ Файлы не найдены", file=sys.stderr)
        return 1

    total = 0
    for f in files:
        total += process_file(f, dictionary, regex, args.backup, args.dry_run)

    print(f"\n📊 Итого: {total} замен в {len(files)} файлах")
    return 0


if __name__ == "__main__":
    sys.exit(main())