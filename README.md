# Dummy Structured SFT (Synthetic) — Dataset Card

High‑quality, fully synthetic SFT datasets for structured output learning. Prompts cover conversion and extraction tasks; answers are deterministically
serialized and strictly validated for syntax. All samples use OpenAI "messages" JSONL format and end with a single assistant turn containing only the target
structure.

## Summary
- Focus: XML / TOML / YAML generation from JSON/YAML/CSV/Text and cross‑format conversions.
- Files:
  - dummy_structured_sft.jsonl (general pack)
  - dummy_structured_sft_text_to_xml.jsonl (targeted text→XML)
  - dummy_structured_sft_hard.jsonl (hard / deeply nested)
  - dummy_structured_sft_toml_aug.jsonl (TOML強化: ネイティブ型・ネスト・配列テーブル)
  - sft_toml_focus.jsonl (TOML集中: 既存＋ハードの混合)

## Tasks and Subcategories
- XML out: json_to_xml, yaml_to_xml, csv_to_xml, text_to_xml
- YAML out: xml_to_yaml, text_to_yaml
- TOML out: json_to_toml, yaml_to_toml, text_to_toml

## Data Fields (per JSONL line)
{
  "id": "<sha12>",
  "category": "C_XML" | "C_TOML" | "C_YAML",
  "subcategory": "...",
  "task": "transform" | "extract",
  "seed": "dummy" | "dummy_hard" | "toml_aug",
  "messages": [
    {"role": "user", "content": "<prompt>"},
    {"role": "assistant", "content": "<target structure only>"}
  ]
}

## Usage
from datasets import load_dataset, concatenate_datasets
ds_general = load_dataset("json", data_files=["dummy_structured_sft.jsonl"], split="train")
ds_text2xml = load_dataset("json", data_files=["dummy_structured_sft_text_to_xml.jsonl"], split="train")
ds_hard    = load_dataset("json", data_files=["dummy_structured_sft_hard.jsonl"], split="train")
ds_toml_aug = load_dataset("json", data_files=["dummy_structured_sft_toml_aug.jsonl"], split="train")
ds_toml_focus = load_dataset("json", data_files=["sft_toml_focus.jsonl"], split="train")

## TOML強化の趣旨
- Inline tables の禁止: TOMLの `{ ... }` (inline table) は曖昧性や改行誤用で壊れやすいため使用禁止。
- ネイティブ型の利用: 数値/真偽値はクォートしない。配列は `[]`、配列テーブルは `[[...]]` を使用。
- ネスト維持: 階層は `[a.b]` のようなテーブルヘッダで表現し、入れ子構造を明確化。
- 本強化パック（toml_aug）は、数値・浮動小数・真偽値・配列・ネストを高頻度に含むよう設計。

## 学習プラン（配合・アップサンプル）
目標: Text→TOML の安定性と render 精度を改善しつつ、json/yaml→TOML の型・構造取り扱いも強化。

推奨配合（エポックあたりの目安比率）:
- text_to_toml: 40%（hard + toml_aug を主に）
- json_to_toml: 30%（toml_aug を主に）
- yaml_to_toml: 30%（toml_aug を主に）
- その他（XML/YAML 変換）は現行水準を維持

推奨アップサンプル設定（例）:
```
{
  "json_to_xml": 1.8,
  "csv_to_xml": 1.4,
  "yaml_to_xml": 1.8,
  "text_to_xml": 1.6,
  "csv_to_json": 1.6,
  "xml_to_yaml": 1.6,
  "text_to_yaml": 1.6,
  "text_to_toml": 2.3,
  "json_to_toml": 1.8,
  "yaml_to_toml": 1.8
}
```
- 既存の `text_to_toml: 2.0` を 2.3 に引き上げ、json/yaml→toml も 1.8 を付与。
- 実際のサンプル数に応じて微調整してください（text_to_toml の比率が 35–45% に収まるように）。

環境変数例:
- bash/zsh: `export SFT_UPSAMPLE_RULES='{"json_to_xml":1.8,"csv_to_xml":1.4,"yaml_to_xml":1.8,"text_to_xml":1.6,"csv_to_json":1.6,"xml_to_yaml":1.6,"text_to_yaml":1.6,"text_to_toml":2.3,"json_to_toml":1.8,"yaml_to_toml":1.8}'`
- PowerShell: `$env:SFT_UPSAMPLE_RULES = '{"json_to_xml":1.8,"csv_to_xml":1.4,"yaml_to_xml":1.8,"text_to_xml":1.6,"csv_to_json":1.6,"xml_to_yaml":1.6,"text_to_yaml":1.6,"text_to_toml":2.3,"json_to_toml":1.8,"yaml_to_toml":1.8}'`

## Generation Process (Provenance)
- Deterministic serializers for answers (XML/TOML/YAML) with strict validators.
- Hard/toml_aug packs focus on deep nesting, arrays of dicts, native types, and explicit constraints（inline table禁止 等）。

## License
Apache-2.0 (see LICENSE). Fully synthetic; no third‑party content embedded.
