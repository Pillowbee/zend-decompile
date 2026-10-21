# Zend Decompiler v23 — проверяемая инженерная итерация

Экспериментальный offline исследовательский инструмент, не универсальный декомпилятор Zend. **Запрещено считать PHP-кандидаты проверенными программами.** Не исполнять входные защищённые PHP и генерируемый PHP. PHP 5.2 используется лишь с `-n -l` для собственной коллекции примеров и кандидатского синтаксиса.

## Изменения к v22

- `zend_compiler_oracle.py`: анализ *нативного* compile-only `op_array` на **собственных** исходниках; `corpus/manifest.json` и `corpus/metrics.json` фиксируют 5 файлов, 5 именных op_array и нулевую долю *подходящих для round-trip* образцов. Сам round-trip `not_run`.
- `opcode_map_observed_v20.json.meta.json` и `opcode_hypotheses_v23.json`: хеши таблиц, provenance, описание разногласий 140/1:199/49. В исходную mapping-файл не внесено переназначений.
- `Decoder.fired_rules`: реальные сработавшие ветки, новые аудиты отражают употребление правил; v20 audit остаётся идентичен golden.
- `zend_parser_isolated.py` и `--isolate-parser` (Linux, 512MiB/CPU 3s/wall 5s), `zend_fuzz_v23.py` с сохраняемыми падениями и детерминированными seed.
- `schemas/audit_v23.schema.json`, `schemas/batch_report_v23.schema.json`, `schemas/opcode_metadata_v23.schema.json`.
- 28 тестов; 8/2/1 на 11 образцах, восемь кандидатов проходят `php -n -l` PHP 5.2.17.

## Команды

```bash
python -m pip install 'networkx>=2.8'
python -m unittest discover -s tests -v
python zend_cli.py validate
python zend_cli.py restore sample_inputs/basket.php -o /tmp/basket.php --audit /tmp/basket.json --isolate-parser
python zend_cli.py batch sample_inputs -o /tmp/restored --isolate-parser --php-linter /absolute/php52_linter --lib-dir /absolute/php52_libs
```

В пакетном режиме код выхода 2 означает, что не все файлы восстановлены. Исполняемый PHP для неподдерживаемых файлов не создаётся; `_partial_READ_ONLY/*.txt` — только исследовательские фрагменты, использовать на сервере нельзя.

Для недоверенных входов `--isolate-parser` защищает лишь **первичный разбор сериализации**. Сам инструмент рекомендуется дополнительно запускать в контейнере/VM без сети и с ограничениями ОС, например внешним `timeout` + `prlimit` (на Linux). Ни эта схема, ни встроенный режим не являются формальным доказательством безопасности.

**Подробности и команды:** `REPORT_V23.md`. **План ядра:** `IR_MIGRATION_V23.md`. Эталон: `golden/v20/`; тесты `tests/`.
