# Zend Decompiler v28

Экспериментальный **офлайн-инструмент** для исследования ограниченного набора сериализованных Zend Encoder / PHP 5.2-файлов. Восстановленный PHP — **непроверенный кандидат**, а не гарантированно эквивалентный исходник. Не исполняйте ни защищённые входные файлы, ни восстановленный код, ни неизвестные загрузчики Zend. Синтаксическая проверка `php -n -l` сама по себе не доказывает эквивалентность.

## Структура проекта

```text
src/zend_decompiler/        Python-пакет: весь актуальный исполняемый код
  __main__.py               python -m zend_decompiler
  cli.py, engine.py         CLI и публичный API восстановления
  restore_core.py           единое ядро генерации кандидатов
  serial_parser.py          разбор сериализованного формата
  prefix_restore.py         инструкции, выражения и временные значения
  cfg.py, crossblock.py     граф управления и межблочные связи
  structure.py, state.py    структурирование и консервативная эмиссия
  batch.py                  пакетная обработка
  assets.py, calibrate.py   источники данных и карта opcode
  *_audit.py, triage.py,
  readonly_dataflow.py,
  ir_evidence.py, fuzz.py   независимая диагностика и исследования
data/opcodes/              активная таблица opcode, evidence и метаданные
data/research/             сохранённые read-only исследования
tests/                     автоматическая проверка текущего Python-пакета
golden/reference/          неизменяемые регрессионные эталоны
sample_inputs/             11 исходных закодированных образцов
corpus/, schemas/          исследовательский корпус и JSON-схемы
research/fragments/       12 уникальных экспериментальных PHP-фрагментов
research/diagnostics/     сохранённые read-only частичные разборы
results/                  независимые исторические исследовательские артефакты
reference_headers_*/       Zend-заголовки разного уровня достоверности
docs/PROJECT_STATUS.md     действующее техническое состояние и roadmap
pyproject.toml             сборка/установка и entry-point
```

Корень проекта содержит конфигурацию, документацию и тестовые артефакты, но **не содержит рабочих Python-скриптов**. Внутренние импорты пакета относительные; старые имена верхнеуровневых модулей `zend_*.py` удалены. Исходники доступны в `src/zend_decompiler/`.

## Установка и тестирование

Python **3.10+**, `networkx>=2.8`.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m zend_decompiler validate
python -m zend_decompiler --version
```

Команда после установки в editable-режиме: `zend-decompiler`. Полная проверка `validate` требует исходное дерево с `tests/` и `golden/reference/`; при их отсутствии команда должна завершаться отказом, а не сообщать об успехе.

## Использование

Команды запускаются из корня checkout, с выводом **за пределами** `sample_inputs/`:

```bash
python -m zend_decompiler batch sample_inputs -o /tmp/zend_batch --isolate-parser
python -m zend_decompiler restore sample_inputs/basket.php \
  -o /tmp/basket_candidate.php --audit /tmp/basket_audit.json --isolate-parser
python -m zend_decompiler audit sample_inputs/basket.php
python -m zend_decompiler dataflow sample_inputs/fun_all.php -o /tmp/fun_all_dataflow.json
python -m zend_decompiler.triage sample_inputs/fun_all.php 'sample_inputs/links_fun(1).php' -o /tmp/triage.json
python -m zend_decompiler.ir_evidence sample_inputs/fun_all.php -o /tmp/ir_evidence.json
```

`--isolate-parser` — ограниченная Linux-изоляция парсера, не общая песочница. `batch` возвращает код **2**, если встречается `unsupported`; это ожидаемо для текущего набора. Проверенный результат: **11 входов → 8 candidate_generated, 2 unsupported, 1 not_encoded**. Для двух неподдерживаемых файлов готовый PHP не создаётся.

## Данные и документы

- `data/opcodes/opcode_map.json` и `opcode_evidence.json` — неизменённые эмпирические данные, защищённые SHA-256. Метаданные `opcode_map.json.meta.json` содержат контрольные суммы и гипотезы; **наличие записи в карте не означает независимого подтверждения**.
- `data/research/{alignment,analysis,header_audits}.json` — read-only свидетельства; это не активные правила декомпиляции.
- `tests/`, `golden/reference/`, `sample_inputs/` — регрессионная база; не корректировать эталоны только ради прохождения тестов.
- `tests/fixtures/batch_report.json` — один архивный JSON batch для проверки схемы (его пути к прошлым отчётам — исторические, не действующие файлы).
- `research/fragments/` — 12 уникальных **частичных** PHP-кандидатов, не пригодных для запуска; сохранённые read-only тексты лежат в `research/diagnostics/`.
- Старые копии `examples/batch_*`, `generated/`, `user_candidate_v19.php` исключены из рабочей ветки; при необходимости доступны через Git history.
- **[PROJECT_STATUS.md](docs/PROJECT_STATUS.md)** — ограничения, доказательства, нерешённые ключи `1:199` и `140`, безопасные направления развития и полный перечень JSON.
- Старые отчёты, код устаревших версий и прежние корневые скрипты доступны только в Git history.

После очистки сохранено **36 уникальных PHP-файлов**: 11 исходных образцов, 8 неизменяемых golden, 5 собственных фикстур и 12 фрагментов. Удалено 38 дублирующих результатов предыдущих выпусков (отличие только в комментарии версии или точное совпадение).

Проект исследовательский; отсутствие падений тестов и совпадение PHP-кандидатов по байтам **не доказывают** эквивалентности реальному PHP.
