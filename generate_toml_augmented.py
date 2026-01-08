#!/usr/bin/env python3
"""
Generate TOML-augmented SFT samples with richer types and nesting
for json_to_toml / yaml_to_toml tasks, reusing the hard generator's
object and TOML serializer to preserve native TOML types.

Usage:
  python3 -m StructEvalT.tools.generate_toml_augmented \
    --out outputs/dummy_structured_sft_toml_aug.jsonl \
    --n_json_to_toml 500 --n_yaml_to_toml 500
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from .generate_hard_structured_data import (
    gen_hard_object,
    dict_to_toml,
    dict_to_yaml,
)


def prompt_json_to_toml(js: str) -> str:
    return (
        "Convert the following JSON into TOML.\n"
        "Rules:\n"
        "- Use native TOML types: numbers/bools unquoted.\n"
        "- Use array-of-tables ([[items]]) where appropriate.\n"
        "- Preserve nesting with [a.b] sections.\n"
        "Return ONLY TOML.\n\nJSON:\n" + js
    )


def prompt_yaml_to_toml(yml: str) -> str:
    return (
        "Convert the following YAML into TOML.\n"
        "Rules:\n"
        "- Use native TOML types: numbers/bools unquoted.\n"
        "- Use array-of-tables ([[items]]) where appropriate.\n"
        "- Preserve nesting with [a.b] sections.\n"
        "Return ONLY TOML.\n\nYAML:\n" + yml
    )


def make_sample(cat: str, sub: str, task: str, prompt: str, answer: str) -> Dict[str, Any]:
    import hashlib
    sid = hashlib.sha1((prompt + "\n\n" + answer).encode("utf-8")).hexdigest()[:12]
    return {
        "id": sid,
        "category": cat,
        "subcategory": sub,
        "task": task,
        "seed": "toml_aug",
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ],
    }


def build_json_to_toml(n: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for _ in range(n):
        obj = gen_hard_object()
        js = json.dumps(obj, ensure_ascii=False)
        prompt = prompt_json_to_toml(js)
        ans = dict_to_toml(obj)
        out.append(make_sample("C_TOML", "json_to_toml", "transform", prompt, ans))
    return out


def build_yaml_to_toml(n: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for _ in range(n):
        obj = gen_hard_object()
        yml = dict_to_yaml(obj)
        prompt = prompt_yaml_to_toml(yml)
        ans = dict_to_toml(obj)
        out.append(make_sample("C_TOML", "yaml_to_toml", "transform", prompt, ans))
    return out


def _write_jsonl(path: str, rows: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/dummy_structured_sft_toml_aug.jsonl")
    ap.add_argument("--n_json_to_toml", type=int, default=500)
    ap.add_argument("--n_yaml_to_toml", type=int, default=500)
    args = ap.parse_args()

    rows: List[Dict[str, Any]] = []
    rows += build_json_to_toml(args.n_json_to_toml)
    rows += build_yaml_to_toml(args.n_yaml_to_toml)
    _write_jsonl(args.out, rows)
    print(f"Wrote {len(rows)} samples -> {args.out}")


if __name__ == "__main__":
    main()

