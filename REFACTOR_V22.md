# Zend Decompiler v22 — устранение цепочки обёрток

## Диагноз по коду v21

До изменений основной путь проходил через `zend_engine.restore_result()` → `zend_restore_v19.restore()` → `zend_restore_v18.build_group()`; исторический CLI `zend_restore_v20.restore()` дополнительно вызывал v19 и вручную дополнял аудит. При этом `v19` не делегировал полный `restore()` в v18, а использовал конкретно `build_group()` и `function_parameters()`. Поэтому фраза «v20 → v19 → v18» верна для зависимостей, но не для последовательности вызовов функций `restore()`.

## Выполнено

- Создан `zend_restore_core.py` — один модуль, содержащий `restore()`, `function_parameters_after_decode()`, `function_parameters()`, `build_group()` и прямую совместимую с v20 функцию `restore_v20_compat()`.
- `zend_engine.py` вызывает `zend_restore_core.restore()` напрямую и формирует типизированный `RestoreResult`, как и в v21.
- `zend_research_v19.py` использует ядро напрямую, без вызовов v18/v19.
- `zend_restore_v19.py` и `zend_restore_v20.py` оставлены как **совместимые точки CLI/API**, но больше не импортируют предыдущие версии. Их исторические заголовки и аудит сохранены.
- Историческая отдельная реализация v18 перенесена в `legacy/zend_restore_v18.py` и **исключена из wheel**.
- Сборка версии `22.0.0` обновлена в `pyproject.toml`, добавлены тесты прямых импортов и полного golden-сравнения с v20.
- Подмена байтов строки версии не используется. Версия передаётся параметром `version` ядру в момент формирования заголовка.

## Схема вызовов

```text
zend_cli.py
    └── zend_engine.restore_result()
            └── zend_restore_core.restore()
                    ├── zend_restore_core.build_group()
                    ├── zend_restore_core.function_parameters_after_decode()
                    └── zend_state_v19.state_emit() [fallback]

zend_restore_v19.py → zend_restore_core.restore()        [compatibility only]
zend_restore_v20.py → zend_restore_core.restore_v20_compat() [compatibility only]
```

**Ограничение:** модули парсера, декодирования выражений (`zend_prefix_restore_v17.py`), CFG (`zend_cfg_v11.py`), структурирования (`zend_structure_v17.py`) и fallback (`zend_state_v19.py`) остаются отдельными и сохраняют старые имена. Полная консолидация всей архитектуры или создание typed IR **не выполнялись**.

## Проверки

В каталоге проекта:

```bash
python -m unittest discover -s tests -v
python zend_cli.py validate
python zend_cli.py batch sample_inputs -o /tmp/zend-v22-check --php-linter /absolute/path/to/php52_linter --lib-dir /absolute/path/to/php52_libs
python -m pip wheel . --no-build-isolation --no-deps -w build_wheels
```

Результаты в этой рабочей среде:

- Unit / golden / boundary tests: **12 из 12 прошли**.
- Golden: 8 исходных PHP-файлов v20 совпадают **побайтово**, аудиты v20 совпадают после JSON-сериализации (структурно).
- Активный `zend_engine` при импорте не загружает `zend_restore_v18`, `zend_restore_v19`, `zend_restore_v20`.
- Batch: **11 исходников → 8 candidate_generated / 2 unsupported / 1 not_encoded**.
- **8/8** PHP-кандидатов проходят PHP 5.2.17 синтаксическую проверку (`-n -l`).
- `fun_all.php`: 12/23 групп сохраняется в текстовой диагностике; `links_fun(1).php`: 4/6.
- Эквивалентность поведения и opcode round-trip не проверялись.

## Что не исправлено этим рефакторингом

- Нет дополнительной поддержки `foreach`, межблочных временных значений или неопознанных опкодов.
- Число полных кандидатов не изменилось.
- v20-совместимый формат аудита сохранён со старой семантикой флагов. Основной v22-аудит по-прежнему не является доказательством семантической корректности.
- Старые имена модулей `zend_*_vNN.py`, кроме собственно restore-цепочки, ещё присутствуют; их переименование отдельно потребует дополнительных тестов и настройки импорта.
- Wheel объявляет зависимость `networkx>=2.8`, но не включает её внутрь архива. Для запуска она должна быть установлена.

Рабочие PHP-файлы из входов не выполнялись; PHP CLI запускался только для синтаксической проверки сгенерированных кандидатов.
