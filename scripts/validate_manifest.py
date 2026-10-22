#!/usr/bin/env python3
"""Validate a local runtime manifest and its files without changing data or using the network."""
import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

WORD_COUNT = 77429


def validate(root: Path, manifest_path: Path | None = None) -> dict:
    root = root.resolve()
    manifest = json.loads((manifest_path or root / 'manifest.json').read_text())
    modules = manifest['modules']
    ids = set()
    counts = {}
    for module in modules:
        module_id = module['id']
        assert re.fullmatch(r'[A-Za-z0-9_-]{1,100}', module_id), f'Unsafe ID: {module_id}'
        assert module_id not in ids, f'Duplicate ID: {module_id}'
        ids.add(module_id)
        relative = Path(module['path'])
        assert not relative.is_absolute() and '..' not in relative.parts, f'Unsafe path: {relative}'
        path = (root / relative).resolve()
        assert path.is_relative_to(root), f'Path escapes data root: {relative}'
        data = path.read_bytes()
        assert len(data) == module['size_bytes'], f'Size mismatch: {module_id}'
        assert hashlib.sha256(data).hexdigest() == module['sha256'], f'Hash mismatch: {module_id}'
        assert module['language'] and module['title'] and module['version'], f'Missing metadata: {module_id}'
        explicit_url = module.get('download_url', module.get('url'))
        if explicit_url:
            url = urlparse(explicit_url)
            assert url.scheme == 'https' and url.netloc, f'Invalid URL: {module_id}'
        kind = module['type']
        if kind == 'word_by_word':
            assert module['format'] == 'json'
            assert module['entry_count'] == WORD_COUNT and module['word_index'] == 'quran-77429-v1'
            values = json.loads(data)
            assert set(values) == {str(i) for i in range(1, WORD_COUNT + 1)}, f'Word index mismatch: {module_id}'
            assert all(isinstance(v, str) and v.strip() for v in values.values()), f'Empty/invalid word: {module_id}'
            assert sum(v == '[[MISSING]]' for v in values.values()) == module['missing_count']
            assert module.get('missing_policy', 'none') in ('none', 'previous_in_ayah')
        elif kind in ('translation', 'tafsir'):
            assert module['format'] == 'sqlite'
            with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
                assert connection.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                # Retain compatibility with the legacy Indonesian module.
                table = 'word_translation' if module_id == 'translation_id_word_by_word' else kind
                assert table in tables, f'Missing table {table}: {module_id}'
                count = connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                assert count > 0
                if table != 'word_translation':
                    assert count == 6236, f'Ayah count mismatch: {module_id}'
        else:
            raise AssertionError(f'Unsupported runtime type: {kind}')
        counts[kind] = counts.get(kind, 0) + 1
    return {'modules': len(ids), 'types': counts, 'status': 'valid',
            'note': 'Local content checks only; publication permissions and live download URLs are separate.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='Data directory containing manifest.json')
    args = parser.parse_args()
    print(json.dumps(validate(args.root), ensure_ascii=False, indent=2))
