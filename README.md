# Zend Decompiler v28

Экспериментальный **офлайн-декомпилятор Zend Encoder / PHP 5.2**. Читает поддерживаемые сериализованные данные и создаёт **непроверенные PHP-кандидаты** и JSON-аудиты. Это исследовательский инструмент, а не универсальный декодер и не средство получения готового к эксплуатации PHP.

**Важно:** восстановленный PHP не доказан эквивалентным оригиналу. Не исполняйте защищённые исходные PHP, полученные PHP-кандидаты или неизвестные Zend/PHP loaders. Для проверки синтаксиса применим только внешний PHP-линтер `-n -l`; это не доказывает семантическую корректность.

## Установка

Требуется Python **3.10+** и `networkx>=2.8`.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python zend_cli.py validate
python zend_cli.py --version
```

`validate` работает в исходном дереве с `tests/` и `golden/reference/`; установочный wheel не содержит эти эталоны и должен отказывать в полной валидации без них.

## Команды

Запускайте из корня репозитория; выходные пути указывайте **за пределами** `sample_inputs/`.

```bash
python zend_cli.py batch sample_inputs -o /tmp/zend_batch --isolate-parser
python zend_cli.py restore sample_inputs/basket.php \
  -o /tmp/basket_candidate.php --audit /tmp/basket_audit.json --isolate-parser
python zend_cli.py audit sample_inputs/basket.php
python zend_cli.py dataflow sample_inputs/fun_all.php -o /tmp/fun_all_dataflow.json
python zend_triage.py sample_inputs/fun_all.php 'sample_inputs/links_fun(1).php' -o /tmp/triage.json
python zend_ir_evidence.py sample_inputs/fun_all.php -o /tmp/ir_evidence.json
```

`--isolate-parser` — дополнительная Linux-изоляция первичного разбора. Команда `batch` возвращает код **2**, если хотя бы один вход не поддерживается. Для 11 включённых образцов проверенная регрессия — **8 candidate_generated / 2 unsupported / 1 not_encoded**; для неподдерживаемых файлов PHP-вывод не создаётся.

## Где находится код

- `zend_cli.py` — интерфейс командной строки; `zend_engine.py` — единственная публичная точка восстановления, `RestoreResult` и статусы.
- `zend_serial_parser.py`, `zend_parser_isolated.py` — разбор входного формата и опциональная изоляция.
- `zend_restore_core.py` — единое ядро восстановления; `zend_prefix_restore.py`, `zend_cfg.py`, `zend_crossblock.py`, `zend_structure.py`, `zend_state.py` — выражения, CFG, межблочные связи и эмиссия.
- `zend_calibrate.py`, `zend_assets.py` — эмпирическая карта опкодов и пути к данным.
- `zend_batch.py` — пакетная обработка и запись.
- `zend_readonly_dataflow.py`, `zend_triage.py`, `zend_ir_evidence.py` и другие `zend_*audit.py` — **диагностика**, не альтернативный декомпилятор.

Исходные образцы: `sample_inputs/`; неизменяемые регрессионные эталоны: `golden/reference/`; тесты: `tests/`; подтверждающие исследовательские артефакты: `corpus/`, `schemas/` и JSON-файлы в корне. Исторические метки `vNN` в именах **данных** фиксируют происхождение, а не вторые реализации Python.

## Текущее состояние и дальнейшая разработка

**[PROJECT_STATUS.md](docs/PROJECT_STATUS.md)** — единая техническая документация: архитектура, ограничения достоверности, измеренные регрессии, нерешённые случаи `fun_all.php` / `links_fun(1).php`, исследовательские данные, приоритеты и критерии приёмки. Она заменяет исторические отчёты `REPORT_*.md`, `README_V*.md` и документы отдельных итераций. Их прежние версии доступны в истории Git; отдельные устаревшие отчёты больше не являются действующей документацией.

Пожалуйста, не меняйте эмпирическую таблицу opcode и golden-эталоны только ради прохождения тестов: регрессия по байтам сама по себе **не** доказывает корректность декомпиляции.
