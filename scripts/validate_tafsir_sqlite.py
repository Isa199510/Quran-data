#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = {"ayah_key", "group_ayah_key", "from_ayah", "to_ayah", "ayah_keys", "text"}


@dataclass
class DbReport:
    path: Path
    total_rows: int = 0
    cross_group: int = 0
    cross_from: int = 0
    cross_to: int = 0
    cross_list: int = 0
    empty_text_rows: int = 0
    schema_error: str | None = None
    runtime_error: str | None = None

    @property
    def has_errors(self) -> bool:
        return bool(
            self.schema_error
            or self.runtime_error
            or self.cross_group
            or self.cross_from
            or self.cross_to
            or self.cross_list
        )


def parse_surah(ayah_key: str | None) -> int | None:
    if not ayah_key or ":" not in ayah_key:
        return None
    left = ayah_key.split(":", 1)[0].strip()
    if not left.isdigit():
        return None
    value = int(left)
    return value if value > 0 else None


def split_ayah_keys(value: str | None) -> Iterable[str]:
    if not value:
        return ()
    return (token.strip() for token in value.split(",") if token.strip())


def validate_db(db_path: Path) -> DbReport:
    report = DbReport(path=db_path)
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "tafsir" not in tables:
            report.schema_error = "table 'tafsir' not found"
            return report

        columns = {row[1] for row in cursor.execute("PRAGMA table_info('tafsir')")}
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            report.schema_error = f"missing columns: {', '.join(missing)}"
            return report

        rows = cursor.execute(
            "SELECT ayah_key, group_ayah_key, from_ayah, to_ayah, ayah_keys, text FROM tafsir"
        ).fetchall()
        report.total_rows = len(rows)

        for ayah_key, group_key, from_key, to_key, ayah_keys, text in rows:
            anchor = parse_surah(ayah_key)
            if anchor is None:
                continue

            if text is None or str(text).strip() == "":
                report.empty_text_rows += 1

            if parse_surah(group_key) not in (None, anchor):
                report.cross_group += 1
            if parse_surah(from_key) not in (None, anchor):
                report.cross_from += 1
            if parse_surah(to_key) not in (None, anchor):
                report.cross_to += 1

            for token in split_ayah_keys(ayah_keys):
                if parse_surah(token) not in (None, anchor):
                    report.cross_list += 1
                    break
    except Exception as exc:  # noqa: BLE001
        report.runtime_error = str(exc)
    finally:
        if conn is not None:
            conn.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate tafsir sqlite files for cross-surah linkage issues.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("tafsirs"),
        help="Directory with tafsir sqlite files (default: tafsirs)",
    )
    args = parser.parse_args()

    db_files = sorted(args.root.rglob("*.db"))
    if not db_files:
        print(f"[ERROR] No .db files found under: {args.root}")
        return 2

    reports = [validate_db(path) for path in db_files]

    has_any_error = False
    for report in reports:
        print(f"\n{report.path}")
        if report.schema_error:
            print(f"  schema_error: {report.schema_error}")
            has_any_error = True
            continue
        if report.runtime_error:
            print(f"  runtime_error: {report.runtime_error}")
            has_any_error = True
            continue

        print(f"  rows: {report.total_rows}")
        print(
            "  cross-surah:"
            f" group={report.cross_group}, from={report.cross_from},"
            f" to={report.cross_to}, ayah_keys={report.cross_list}"
        )
        print(f"  empty_text_rows: {report.empty_text_rows}")

        if report.has_errors:
            has_any_error = True

    if has_any_error:
        print("\n[FAIL] Validation found cross-surah or schema/runtime issues.")
        return 1

    print("\n[OK] All tafsir sqlite files passed validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

