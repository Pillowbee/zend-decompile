# Zend Decompiler 28 — единственная актуальная реализация

Экспериментальный **офлайн**-инструмент для анализа поддерживаемых сериализованных
PHP 5.2-файлов Zend Encoder. Выдаёт *кандидат* исходного PHP и диагностический отчёт,
но **не доказывает поведенческой эквивалентности** восстановленного кода.
Для production-развёртывания сгенерированные кандидаты не предназначены.

## Установка и проверка

Требуется Python 3.10+ и `networkx>=2.8`.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python zend_cli.py validate
python zend_cli.py --version
```

`validate` требует исходный каталог с `tests/` и `golden/reference/`;
установленное колесо не содержит тестовых входов и не должно имитировать
успешную валидацию без эталонов.

## Работа с файлами

Запускайте из корня репозитория, а выходные каталоги выбирайте **вне** `sample_inputs/`:

```bash
python zend_cli.py batch sample_inputs -o /tmp/zend_batch --isolate-parser
python zend_cli.py restore sample_inputs/basket.php \
    -o /tmp/basket_candidate.php --audit /tmp/basket_audit.json --isolate-parser
python zend_cli.py dataflow sample_inputs/fun_all.php -o /tmp/fun_all_dataflow.json
python zend_triage.py sample_inputs/fun_all.php 'sample_inputs/links_fun(1).php' -o /tmp/triage.json
python zend_ir_evidence.py sample_inputs/fun_all.php -o /tmp/ir_evidence.json
```

При наличии неподдерживаемых входов `batch` возвращает код `2`.
Для 11 включённых образцов ожидается: **8 кандидатов, 2 unsupported и 1 not_encoded**.
Не включайте произвольные исходные PHP-файлы в выполнение при проверке;
для синтаксиса разрешён исключительно внешний линтер с флагами `-n -l`.
Исходные данные, записанные golden-эталоны и PHP-кандидаты не исполняются.

## Актуальная архитектура

```text
zend_cli.py                   команда CLI (restore / batch / audit / validate)
  zend_engine.py              публичная точка входа; fail-closed обработка
    zend_restore_core.py      единый генератор PHP
      zend_prefix_restore.py  обработка выражений, операндов и инструкций
      zend_cfg.py             граф управления
      zend_crossblock.py      доказанные межблочные связи
      zend_structure.py       структурирование блоков
      zend_state.py           консервативная fallback-эмиссия
    zend_serial_parser.py     двоичный формат и распаковка
    zend_calibrate.py         отображение эмпирических opcode
  zend_batch.py               массовая обработка и безопасная запись
  zend_readonly_dataflow.py   независимый анализ TMP/VAR без вывода PHP
  zend_assets.py              единые пути к активным данным и golden-эталонам
```

Отдельные исследовательские утилиты остаются **частями текущего инструмента**:
`zend_block_previews.py`, `zend_research.py`, `zend_triage.py`,
`zend_ir_evidence.py`, `zend_fuzz.py`, `zend_alignment_audit.py`,
`zend_compiler_oracle.py` и `zend_header_audit.py`.
Они не содержат параллельных восстановителей PHP.

В активном исходном дереве **нет Python-скриптов с суффиксами версий**.
Старые точки входа и версии декодера удалены; история доступна через Git.
Наличие версионного номера в названиях **неизменённых исследовательских данных**
не означает присутствия альтернативной реализации.

## Эталонные данные и тесты

- `sample_inputs/` — неизменённые входные PHP-образцы.
- `opcode_map_observed_v20.json`, `opcode_evidence_v21.json`, их метаданные
  и `zend_verified_dictionary.bin` — неизменённый комплект подтверждающих данных.
- `golden/reference/` — оригинальные эталонные PHP-кандидаты, отчёты и SHA-256;
  **все файлы перенесены без изменения содержимого** из старого каталога golden.
- `tests/` — проверки **единственной текущей реализации**, без импорта старых API.
  Тесты допускают изменение номера версии программы в заголовке результата,
  но требуют полного совпадения PHP-кода с эталоном, неизменности полей
  golden-аудитов и отсутствия отката на ранее поддерживаемых блоках.
- `tests/fixtures/preview_completed_blocks.json` — SHA-256 ранее восстановленных
  блоков из исходного Git-состояния для проверки монотонности декодера.
- `corpus/`, `examples/`, `schemas/legacy/`, `REPORT_*.md` — сохранённая
  исследовательская история, **не вторые исполняемые версии**.

Часть внешних проверок (PHP 5.2 native oracle, сохранённые сторонние трассы)
может пропускаться при отсутствии подходящего окружения. Все три пропуска
и ограничения описываются соответствующими тестами. Не стоит считать успешное
выполнение Python-тестов доказательством эквивалентности PHP.

## Известные ограничения

- `fun_all.php`: неизвестный эмпирический ключ `1:199`.
- `links_fun(1).php`: семантика opcode 140 и связи временных значений не доказаны.
- Однозначность отображения opcode и корректность восстановленного управления
  потоком проверены только в пределах включённого набора свидетельств.
- Безопасное завершение с `unsupported` предпочтительнее непроверенного PHP.

Изменения после аудита v28 и результаты сравнения оформлены в
[`CONSOLIDATION_REPORT_2026-10-22.md`](CONSOLIDATION_REPORT_2026-10-22.md).
Исторические отчёты `REPORT_*.md` описывают **прошлые** состояния проекта.
