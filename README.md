# Dummy Structured SFT Generators

This folder contains two lightweight, dependency‑minimal generators for high‑quality, fully‑synthetic SFT datasets targeting structured outputs (XML/TOML/YAML). All samples are emitted in OpenAI "messages" JSONL format and are strictly validated for syntax.

- `generate_dummy_structured_data.py` — general‑purpose synthetic pack
- `generate_hard_structured_data.py` — harder, deeply‑nested structures and constraints

Both scripts produce deterministic assistant outputs via handcrafted serializers, then run strict smoke checks (XML/YAML/TOML parsers) before writing JSONL.

## Output Schema (per line)

Each line is one JSON object with the following shape:

```
{
  "id": "<sha12>",
  "category": "C_XML" | "C_TOML" | "C_YAML",
  "subcategory": "json_to_xml" | "yaml_to_xml" | "csv_to_xml" | "text_to_xml" | "xml_to_yaml" | "json_to_toml" | "yaml_to_toml" | "text_to_toml" | "text_to_yaml",
  "task": "transform" | "extract",
  "seed": "dummy" | "dummy_hard",
  "messages": [
    {"role": "user", "content": "<prompt>"},
    {"role": "assistant", "content": "<expected structured output>"}
  ]
}
```

- `id`: first 12 chars of SHA‑1 over `prompt + "\n\n" + answer` (stable across runs with same seed).
- `messages`: always ends with an assistant turn; no explanations, only the target format.

## 1) generate_dummy_structured_data.py

General pack focused on correctness and breadth.

Supported subcategories:

- XML out: `json_to_xml`, `yaml_to_xml`, `csv_to_xml`, `text_to_xml`
- YAML out: `xml_to_yaml`
- TOML out: `json_to_toml`, `yaml_to_toml`, `text_to_toml`

Key design points:

- Random small objects of shape `{ "items": [ {key: scalar, ...}, ... ] }` with mixed snake/camel keys.
- Deterministic serializers:
  - XML via `xml.etree.ElementTree` (`<root><items><item>...</item></items></root>`)
  - TOML as array‑of‑tables (`[[items]]`) with safe quoting
  - YAML via `yaml.safe_dump` if available; otherwise JSON‑like fallback
- Strict smoke validation per subgroup:
  - XML → `ET.fromstring`
  - YAML → `yaml.safe_load` (if PyYAML present)
  - TOML → `tomllib`/`tomli`. If unavailable, validation for TOML returns True in the general pack.

CLI:

```
python -m tools.generate_dummy_structured_data \
  --out outputs/dummy_structured_sft.jsonl \
  --seed 42 \
  --n_json_to_xml 300 --n_yaml_to_xml 300 --n_csv_to_xml 0 --n_text_to_xml 0 \
  --n_xml_to_yaml 150 --n_json_to_toml 150 --n_yaml_to_toml 150 --n_text_to_toml 150
```

Generate a text_to_xml‑only pack (useful for targeted upsampling):

```
python -m tools.generate_dummy_structured_data \
  --out outputs/dummy_structured_sft_text_to_xml.jsonl \
  --n_text_to_xml 800 --n_json_to_xml 0 --n_yaml_to_xml 0 --n_csv_to_xml 0 \
  --n_xml_to_yaml 0 --n_json_to_toml 0 --n_yaml_to_toml 0 --n_text_to_toml 0
```

## 2) generate_hard_structured_data.py

Harder pack emphasizing deep nesting, arrays of dicts, mixed scalar types, and explicit constraints in the prompt.

Supported subcategories:

- `json_to_xml`, `xml_to_yaml`, `text_to_toml`, `text_to_yaml`

Key design points:

- "Hard" object generator inserts nested dicts (`dimensions`, `flags`), lists (`tags`, `components`), optional empties, and mixed numeric/string/boolean types.
- XML serializer is recursive and preserves nesting; lists become repeated `<item>` elements.
- TOML uses dotted tables for nested dicts and array‑of‑tables for lists of dicts.
- Validation is strict for all formats; missing validators can be enforced to fail with `--require_validators 1`.

CLI:

```
python -m tools.generate_hard_structured_data \
  --out outputs/dummy_structured_sft_hard.jsonl \
  --seed 42 \
  --n_json_to_xml 1000 --n_xml_to_yaml 1000 --n_text_to_toml 1000 --n_text_to_yaml 1000
```

## Prompts and Answers

- Prompts specify conversion or extraction instructions (e.g., "Return ONLY XML").
- Answers are strictly the target format; no prose.

## Reproducibility

- Set `--seed` to control the random object builder.
- `id` generation is content‑based; identical inputs produce identical IDs.

## Dependencies

- Always: Python 3.9+ standard libs; `xml.etree.ElementTree`.
- Optional: `PyYAML` for YAML validation/serialization; `tomllib` (Py3.11+) or `tomli` for TOML validation.

Install helpers:

```
pip install pyyaml tomli
```

## File Size and Splitting

JSONL files can grow large. Consider generating separate packs per subtask or uploading multiple JSONL files (e.g., `dummy_structured_sft.jsonl`, `dummy_structured_sft_text_to_xml.jsonl`, `dummy_structured_sft_hard.jsonl`).

## License

Unless otherwise noted, code in this repository and the generated synthetic datasets are provided under the Apache License 2.0 (see `/LICENSE`).

