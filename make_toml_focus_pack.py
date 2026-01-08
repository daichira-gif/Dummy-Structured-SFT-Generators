#!/usr/bin/env python3
"""
Create a TOML-focused SFT pack by sampling TOML subtasks from
existing local JSONL files (general and/or hard).

Usage:
  python3 -m StructEvalT.tools.make_toml_focus_pack \
    --inputs outputs/dummy_structured_sft.jsonl outputs/dummy_structured_sft_hard.jsonl \
    --json_to_toml 400 --yaml_to_toml 400 --text_to_toml 800 \
    --out outputs/sft_toml_focus.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
from typing import Any, Dict, List


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", default="outputs/sft_toml_focus.jsonl")
    ap.add_argument("--json_to_toml", type=int, default=300)
    ap.add_argument("--yaml_to_toml", type=int, default=300)
    ap.add_argument("--text_to_toml", type=int, default=600)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    pool: List[Dict[str, Any]] = []
    for p in args.inputs:
        if not os.path.exists(p):
            print(f"WARN: missing input {p}")
            continue
        pool.extend(load_jsonl(p))

    # Bucket by subcategory
    buckets: Dict[str, List[Dict[str, Any]]] = {"json_to_toml": [], "yaml_to_toml": [], "text_to_toml": []}
    for ex in pool:
        sub = ex.get("subcategory", "")
        if sub in buckets:
            buckets[sub].append(ex)

    def sample_from(bucket: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
        if not bucket:
            return []
        if len(bucket) <= k:
            return bucket[:]
        return rng.sample(bucket, k)

    out_rows: List[Dict[str, Any]] = []
    out_rows += sample_from(buckets.get("json_to_toml", []), args.json_to_toml)
    out_rows += sample_from(buckets.get("yaml_to_toml", []), args.yaml_to_toml)
    out_rows += sample_from(buckets.get("text_to_toml", []), args.text_to_toml)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote {len(out_rows)} TOML-focused samples -> {args.out}")
    for sub in ("json_to_toml", "yaml_to_toml", "text_to_toml"):
        print(f"  {sub}: {len([1 for r in out_rows if r.get('subcategory')==sub])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

