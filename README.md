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
examples/, generated/      примеры и сохранённые результаты
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

Команда после обычной установки: `zend-decompiler`. Установленный wheel не содержит `tests/` и `golden/reference/`: поэтому `validate` без исходного дерева должен возвращать отказ, а не сообщать об успехе.

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
- **[PROJECT_STATUS.md](docs/PROJECT_STATUS.md)** — ограничения, доказательства, нерешённые ключи `1:199` и `140`, безопасные направления развития и полный перечень JSON.
- Старые отчёты, код устаревших версий и прежние корневые скрипты доступны только в Git history.

Проект исследовательский; отсутствие падений тестов и совпадение PHP-кандидатов по байтам **не доказывают** эквивалентности реальному PHP.
