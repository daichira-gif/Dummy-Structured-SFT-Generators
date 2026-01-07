# Dummy Structured SFT (Synthetic) — Dataset Card

High‑quality, fully synthetic SFT datasets for structured output learning. Prompts cover conversion and extraction tasks; answers are deterministically serialized and strictly validated for syntax. All samples use OpenAI "messages" JSONL format and end with a single assistant turn containing only the target structure.

## Summary

- Focus: XML / TOML / YAML generation from JSON/YAML/CSV/Text and cross‑format conversions.
- Files to upload (recommended):
  - `outputs/dummy_structured_sft.jsonl` (general pack)
  - `outputs/dummy_structured_sft_text_to_xml.jsonl` (targeted text→XML)
  - `outputs/dummy_structured_sft_hard.jsonl` (hard / deeply nested)

All content is machine‑generated; no third‑party text is embedded.

## Tasks and Subcategories

- XML out: `json_to_xml`, `yaml_to_xml`, `csv_to_xml`, `text_to_xml`
- YAML out: `xml_to_yaml`, `text_to_yaml`
- TOML out: `json_to_toml`, `yaml_to_toml`, `text_to_toml`

`task` is `transform` for conversions and `extract` for text→structure.

## Data Fields (per JSONL line)

```
{
  "id": "<sha12>",
  "category": "C_XML" | "C_TOML" | "C_YAML",
  "subcategory": "...",
  "task": "transform" | "extract",
  "seed": "dummy" | "dummy_hard",
  "messages": [
    {"role": "user", "content": "<prompt>"},
    {"role": "assistant", "content": "<target structure only>"}
  ]
}
```

Notes:

- `id` is stable for identical prompt/answer pairs (SHA‑1 based).
- `messages` always ends with the assistant answer; no rationales.

## Usage

Python (datasets, local JSONL):

```python
from datasets import load_dataset, concatenate_datasets

ds_general = load_dataset("json", data_files=["outputs/dummy_structured_sft.jsonl"], split="train")
ds_text2xml = load_dataset("json", data_files=["outputs/dummy_structured_sft_text_to_xml.jsonl"], split="train")
ds_hard    = load_dataset("json", data_files=["outputs/dummy_structured_sft_hard.jsonl"], split="train")

ds = concatenate_datasets([ds_general, ds_text2xml, ds_hard])
print(ds[0]["messages"][0]["content"])
```

Training example (Qwen3‑4B, local JSONL):

```
python scripts/train_local_qlora_qwen3.py \
  --data outputs/dummy_structured_sft.jsonl \
        outputs/dummy_structured_sft_text_to_xml.jsonl \
        outputs/dummy_structured_sft_hard.jsonl \
  --out_dir ./out_sft_qwen3_local --lora_dir ./out_sft_qwen3_local_lora
```

## Generation Process (Provenance)

- Answers are produced by deterministic serializers (XML via `xml.etree.ElementTree`; TOML via handcrafted emitter; YAML via PyYAML if available).
- Strict validators are used to smoke‑check each sample; only valid outputs are written.
- Hard pack injects deeper nesting, arrays of dicts, sparse/empty fields, and explicit constraints in prompts.

## Languages

- Prompts and keys are synthetic and in English‑like tokens; no natural language passages from external sources are included.

## License

Apache License 2.0. This dataset is fully synthetic; no third‑party content is embedded. See `LICENSE`.

## Citation

If you use this dataset, please cite the repository and include a link to the dataset card on Hugging Face.

