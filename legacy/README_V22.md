# Zend Decompiler v22 — consolidated restoration entry path

Version 22 is a focused refactor of v21. Production flow is now
`zend_cli.py → zend_engine.restore_result() → zend_restore_core.restore()`.
`zend_restore_core.py` directly owns `function_parameters()`, `build_group()`,
`function_parameters_after_decode()`, and `restore()`. The v19 and v20
CLI names are direct compatibility shims, not stages in the restoration path.
The v18 module is retained only for historical reference and is not imported
by active restoration. The expression decoder, CFG, and state-machine modules
still have historical filenames; a full typed-IR migration was not done.

Golden inputs/candidates are unchanged modulo the version label. The SHA-256
input/mapping/dictionary audit, fail-closed policy, and empirical opcode
limitations remain. **Never execute untrusted source PHP; generated candidates
are not semantically verified and not suitable for production deployment.**

See `REFACTOR_V22.md` for the precise changes and verification commands.

---

## Previous v21 documentation

# Zend Decompiler v21.0.0-experimental

**Experimental, incomplete, not production-ready.** Recognizes samples of Zend Encoder / PHP 5.2 serialized op_arrays using one *empirical* table. Recovered PHP is an unverified candidate, **not** asserted semantically equivalent to its input.

## Setup and commands

Python >= 3.10 with `networkx` (`python -m pip install networkx`). Run from **this checkout**; no web access required. Never execute an encoded input or restored candidate. The PHP 5.2 CLI below is permitted only with `-n -l` for syntax checks.

```bash
python zend_cli.py validate
python zend_cli.py audit 'sample_inputs/links_fun(1).php' > diagnostic.json
python zend_cli.py restore sample_inputs/basket.php -o /tmp/basket_candidate.php --audit /tmp/basket_audit.json
python zend_cli.py batch sample_inputs -o /tmp/zend_batch21 --php-linter /path/to/php-5.2-cli --lib-dir /path/to/php52-shared-libs
```

`restore` exits 2 on unsupported input and only writes an audit, never an incomplete executable PHP file. `batch` exits 2 if any input is unsupported. `--recursive` and external-output-only restrictions remain. Outputs are exclusive-create by default: running twice into the same directory is refused rather than overwriting. Audit and output are written using same-directory temporary files and atomic rename, with rollback of newly created audit on a failed candidate write. This is **not** a multi-file transaction across power failure.

**Important:** `audit` returns exit code 2 if unsupported even though it emits JSON diagnostics.

## Verified regression set

- 11 samples: 8 complete candidates, 2 unsupported, 1 plain PHP skipped.
- Golden baseline stored under `golden/v20`: 8 **byte-for-byte** outputs, their v20 audit JSON, 11 input SHA-256 hashes, mapping/dictionary SHA-256 hashes, and incomplete research reports for `fun_all.php` and `links_fun(1).php`. Only the generated version header changes when comparing v21 to v20.
- Standalone analysis of `links_fun(1).php`: 4/6 groups; `fun_all.php`: 12/23 groups. These are not complete files. Batch writes text-only `.txt` reconstructions under `_partial_READ_ONLY`, with explicit `/* UNRECOVERED */` markers and no `<?php` tags.
- `php -n -l` can validate syntax of outputs without executing their application logic. Behavioral tests from v15–v19 **are not run**, because the current project constraint prohibits executing supplied encoded PHP; the old harnesses are preserved for study, not invoked.

## Evidence and opcode ambiguities

`opcode_map_observed_v20.json` must not be interpreted as a universal substitution cipher. `opcode_evidence_v21.json` binds empirical keys to statuses (`confirmed`, `inferred`, `unknown`) and SHA-256 of the exact mapping. **No key is classified `confirmed`** in v21 because independently validated key-level primary evidence is not bundled. The symbolic opcode `140` is additionally marked `unknown` as to semantics, despite possessing a numeric mapping. `1:199` in the `out_price` and `uc_rus` foreach loops is unmapped. Neither is guessed. `opcode_mapping_confidence_fraction` means *fraction marked confirmed*, NOT completeness or semantic equivalence; this is expected to be zero. `recognition_fraction` instead counts numeric mappings, including mappings with uncertain semantics.

The `zend_compile.h` and `zend_vm_def.h` sources for the **exact** PHP 5.2.17 build are not bundled; no exact-version verification of opcode 140 has been completed. Investigate it with a separately reviewed, compile-only op_array oracle and known small independent source programs before revising the decoder.

## Round-trip, original corpus, IR

- `round_trip.status` is deliberately `not_run`: PHP 5.2 `-l` alone does not produce a trustworthy comparable opcode stream, and the available local probe binaries have not been validated as safe/reliable with the candidates. A syntax pass is **not** an opcode round-trip pass.
- Open-source PHP → compile-only op_array → decoder round-trip with expected reference outputs has **not** been built. The current byte-stream parser is designed for Zend Encoder serialized input, not generic PHP op_array dumps; building an input adapter is a prerequisite.
- The current `Decoder` (`zend_prefix_restore_v17.py`) stores temporaries/expressions as byte strings; `zend_structure_v17.py` uses CFG regions and a legacy `state_emit` while/switch fallback. In one incremental release, **full conversion to a typed IR is unsafe**, because it would perturb all 8 golden outputs. Introduce typed operand/expression nodes behind a compatibility adapter, then migrate per-opcode, add normalized IR tests, and only then move the generator/CFG. The v21 facade retains existing rendering deliberately.
- Loop/foreach reconstruction, inter-block temp dataflow, inferred opcode 140, `list`, complex `isset/empty`, exceptions and generic class methods remain open issues.

## Safety and boundaries

The Python code never evaluates provided PHP source. The optional PHP tool is invoked ONLY with `-n -l` on temporary generated PHP candidate bytes. Source input / decoder classes may raise errors internally; `zend_engine.restore_result` converts these to a structured `unsupported` result. Fuzz tests cover deterministic truncations and 90 bit flips on an actual decoded stream; they are not an exhaustive resource-exhaustion/security audit. Parser size constants apply, but absolute wall-clock and memory limits are not fully enforced; run against untrusted files under OS isolation.

## Audit schemas

- `schemas/audit_v21.schema.json`: v21 audit payload, hashes, rule-usage **encounter counts**, diagnostic windows, confidence status and round-trip `not_run`.
- `schemas/batch_report_v21.schema.json`: batch-level file statuses, counts and partial read-only diagnostic locations.

## Source layout and backwards compatibility

`zend_engine.py` is the typed `RestoreResult` facade and handles hashes, confidence summaries, statuses and diagnostics. `zend_batch.py` owns safe writes. `zend_partial.py` captures per-function text-only fragments. `zend_cli.py` exposes `restore`, `batch`, `validate`, `audit`. The v19/v18/earlier versions are retained **temporarily** as implementations, not merely wrappers; fully merging them needs separate, golden-protected patches. `zend_restore_v19.py` now takes a `version=` argument, eliminating the v20 bytes.replace version patch. The old v20 wrapper remains callable and produces **identical** bytes and audit to the golden baseline.

No historical Git tags were fabricated. The included `pyproject.toml` describes dependencies and a console entry point; running from the checkout is the tested invocation (wheel packaging of bundled dictionaries is still unverified).
