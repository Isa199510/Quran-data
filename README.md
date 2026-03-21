# Quran Data

Репозиторий с данными для приложения QuranApp.

## Структура

```text
translations/
  en/
  ru/

tafsirs/
  ar/
  en/
  ru/

manifest.json

scripts/
  validate_tafsir_sqlite.py
```

## Проверка tafsir баз перед публикацией

```bash
python3 scripts/validate_tafsir_sqlite.py
```

Скрипт проверяет:
- схему таблицы `tafsir`
- межсурные связи (`ayah_key` vs `group_ayah_key` / `from_ayah` / `to_ayah` / `ayah_keys`)
- количество строк с пустым `text`

Код возврата:
- `0` — всё ок
- `1` — есть ошибки в данных/схеме
- `2` — не найдены `.db` файлы
