#!/usr/bin/env python3
"""
Generate high-quality dummy SFT samples for structured output tasks,
focusing on XML/TOML generation where models tend to fail. The assistant
outputs are created via deterministic serialization to guarantee syntax
validity, and a smoke test validates outputs with strict parsers.

Outputs a JSONL at ./outputs/dummy_structured_sft.jsonl by default.

Usage:
  python -m tools.generate_dummy_structured_data \
    --out outputs/dummy_structured_sft.jsonl \
    --n_json_to_xml 400 --n_yaml_to_xml 400 --n_xml_to_yaml 200 \
    --n_json_to_toml 200 --n_yaml_to_toml 200 --n_text_to_toml 200

All counts are optional and can be tuned.
"""
import argparse
import hashlib
import json
import os
import random
from typing import Any, Dict, List, Tuple

# Local, dependency-light helpers (avoid pandas/lxml hard deps)
import json as _json
import csv as _csv
from io import StringIO

# Defer TOML library import to runtime to work on Py<=3.10 without tomli installed
_TOML_LOADER = None  # will be set to a module providing loads()

try:
    import yaml as _yaml  # type: ignore
except Exception:
    _yaml = None

try:
    from xml.etree import ElementTree as _ET
except Exception:
    _ET = None


def safe_json_sized(obj: Dict[str, Any], max_chars: int) -> str:
    s = _json.dumps(obj, ensure_ascii=False)
    return s[:max_chars]


def dict_to_toml(obj: Dict[str, Any]) -> str:
    # Minimal TOML for {'items': [{...}, ...]} as arrays-of-tables
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        items = []
    lines: List[str] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        lines.append("[[items]]")
        for k, v in it.items():
            sval = str(v).replace("\n", " ")
            # Minimal escaping for TOML basic strings
            sval = sval.replace("\\", "\\\\").replace('"', '\\"')
            # Quote always (dummy pack); keep syntax strictly valid
            lines.append(f'{k} = "{sval}"')
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def dict_to_yaml(obj: Dict[str, Any]) -> str:
    if _yaml is None:
        # Fallback: JSON as YAML-like (not strict). Prefer installing PyYAML.
        return _json.dumps(obj, ensure_ascii=False)
    return _yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)


def _etree_from_obj(obj: Dict[str, Any]) -> "_ET.Element":
    root = _ET.Element("root")
    items_el = _ET.SubElement(root, "items")
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        items = []
    for it in items:
        item_el = _ET.SubElement(items_el, "item")
        if not isinstance(it, dict):
            continue
        for k, v in it.items():
            # Tag names: fallback to 'field' if invalid
            tag = k if k and k[0].isalpha() else "field"
            child = _ET.SubElement(item_el, tag)
            child.text = str(v)
    return root


def dict_to_xml_sized(obj: Dict[str, Any], root_name: str = "root") -> str:
    if _ET is None:
        # Best-effort fallback
        return "<root/>"
    root = _etree_from_obj(obj)
    return _ET.tostring(root, encoding="unicode")


def validate_toml(s: str) -> bool:
    global _TOML_LOADER
    if _TOML_LOADER is None:
        try:
            import tomllib as _tomllib_local  # type: ignore
            _TOML_LOADER = _tomllib_local
        except Exception:
            try:
                import tomli as _tomli_local  # type: ignore
                _TOML_LOADER = _tomli_local
            except Exception:
                _TOML_LOADER = None
    if _TOML_LOADER is None:
        # No parser available -> treat as invalid to avoid poisoning the dataset
        return False
    try:
        _TOML_LOADER.loads(s)
        return True
    except Exception:
        return False


def validate_xml(s: str) -> bool:
    try:
        if _ET is None:
            return False
        _ET.fromstring(s)
        return True
    except Exception:
        return False


def validate_yaml(s: str) -> bool:
    if _yaml is None:
        # No parser available -> treat as invalid to avoid poisoning the dataset
        return False
    try:
        _yaml.safe_load(s)
        return True
    except Exception:
        return False


def prompt_json_to_xml(js: str) -> str:
    return (
        "Convert the following JSON into well-formed XML.\n"
        "Return ONLY XML.\n\nJSON:\n" + js
    )


def prompt_yaml_to_xml(yml: str) -> str:
    return (
        "Convert the following YAML into well-formed XML.\n"
        "Return ONLY XML.\n\nYAML:\n" + yml
    )


def prompt_csv_to_xml(csv: str) -> str:
    return (
        "Convert the following CSV into well-formed XML.\n"
        "Return ONLY XML.\n\nCSV:\n" + csv
    )


def prompt_text_to_xml(text: str, attrs: List[str]) -> str:
    return (
        "Extract the following attributes from text and output well-formed XML.\n"
        "Return ONLY XML.\n\nATTRIBUTES:\n"
        + ", ".join(attrs)
        + "\n\nTEXT:\n" + text
    )


def prompt_xml_to_yaml(xml_s: str) -> str:
    return (
        "Convert the following XML into YAML.\n"
        "Return ONLY YAML.\n\nXML:\n" + xml_s
    )


def prompt_json_to_toml(js: str) -> str:
    return (
        "Convert the following JSON into TOML.\n"
        "Constraints:\n"
        "- Use dotted tables and arrays-of-tables where appropriate.\n"
        "- Do NOT use TOML inline tables (curly braces like { ... }).\n"
        "- Use native TOML types: numbers/bools unquoted.\n"
        "Return ONLY TOML.\n\nJSON:\n" + js
    )


def prompt_yaml_to_toml(yml: str) -> str:
    return (
        "Convert the following YAML into TOML.\n"
        "Constraints:\n"
        "- Use dotted tables and arrays-of-tables where appropriate.\n"
        "- Do NOT use TOML inline tables (curly braces like { ... }).\n"
        "- Use native TOML types: numbers/bools unquoted.\n"
        "Return ONLY TOML.\n\nYAML:\n" + yml
    )


def prompt_text_to_toml(text: str, attrs: List[str]) -> str:
    return (
        "Extract the following attributes from text and output TOML.\n"
        "Constraints:\n"
        "- Use dotted tables and arrays-of-tables where appropriate.\n"
        "- Do NOT use TOML inline tables (curly braces like { ... }).\n"
        "- Use native TOML types: numbers/bools unquoted.\n"
        "Return ONLY TOML.\n\nATTRIBUTES:\n"
        + ", ".join(attrs)
        + "\n\nTEXT:\n" + text
    )


# --------------------------- Random object builders ---------------------------

WORDS = [
    "alpha", "beta", "gamma", "delta", "omega", "zephyr", "lumen",
    "nova", "aurora", "ember", "terra", "eon", "atlas", "velox",
]


def _rand_word() -> str:
    return random.choice(WORDS)


def _rand_int(a=0, b=9999) -> int:
    return random.randint(a, b)


def _rand_bool() -> bool:
    return bool(random.randint(0, 1))


def _rand_scalar() -> Any:
    r = random.random()
    if r < 0.25:
        return _rand_word().title()
    if r < 0.50:
        return _rand_int()
    if r < 0.75:
        return _rand_bool()
    return _rand_word()


def _rand_key() -> str:
    # Mix snake/camel a bit to diversify keys
    w1, w2 = _rand_word(), _rand_word()
    if random.random() < 0.5:
        return f"{w1}_{w2}"
    return f"{w1}{w2.title()}"


def gen_flat_item(n_keys: int = 4) -> Dict[str, Any]:
    n = max(2, n_keys)
    keys = { _rand_key(): _rand_scalar() for _ in range(n) }
    # ensure strings for XML text friendliness when needed
    return { k: (str(v) if isinstance(v, bool) else v) for k, v in keys.items() }


def gen_object(items_min=2, items_max=5, keys_min=3, keys_max=6) -> Dict[str, Any]:
    n_items = random.randint(items_min, items_max)
    obj = {
        "items": [gen_flat_item(random.randint(keys_min, keys_max)) for _ in range(n_items)]
    }
    return obj


# --------------------------- Sample construction -----------------------------

def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def make_sample(cat: str, sub: str, task: str, prompt: str, answer: str) -> Dict[str, Any]:
    sid = _sha1(prompt + "\n\n" + answer)
    return {
        "id": sid,
        "category": cat,
        "subcategory": sub,
        "task": task,
        "seed": "dummy",
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ],
    }


def build_json_to_xml(n: int) -> List[Dict[str, Any]]:
    out = []
    for _ in range(n):
        obj = gen_object()
        js = safe_json_sized(obj, 1800)
        prompt = prompt_json_to_xml(js)
        ans = dict_to_xml_sized(obj, root_name="root")
        if validate_xml(ans):
            out.append(make_sample("C_XML", "json_to_xml", "transform", prompt, ans))
    return out


def build_yaml_to_xml(n: int) -> List[Dict[str, Any]]:
    out = []
    for _ in range(n):
        obj = gen_object()
        yml = dict_to_yaml(obj)
        prompt = prompt_yaml_to_xml(yml)
        ans = dict_to_xml_sized(obj, root_name="root")
        if validate_xml(ans):
            out.append(make_sample("C_XML", "yaml_to_xml", "transform", prompt, ans))
    return out


def _csv_from_items(obj: Dict[str, Any]) -> str:
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list) or not items:
        items = [{}]
    # columns from union of keys
    cols = []
    for it in items:
        if isinstance(it, dict):
            for k in it.keys():
                if k not in cols:
                    cols.append(k)
    buf = StringIO()
    writer = _csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for it in items:
        if isinstance(it, dict):
            writer.writerow({k: str(it.get(k, "")) for k in cols})
    return buf.getvalue()


def build_csv_to_xml(n: int) -> List[Dict[str, Any]]:
    out = []
    for _ in range(n):
        obj = gen_object()
        csv_s = _csv_from_items(obj)
        prompt = prompt_csv_to_xml(csv_s)
        ans = dict_to_xml_sized(obj, root_name="root")
        if validate_xml(ans):
            out.append(make_sample("C_XML", "csv_to_xml", "transform", prompt, ans))
    return out


def build_text_to_xml(n: int) -> List[Dict[str, Any]]:
    out = []
    for _ in range(n):
        obj = gen_object()
        # Build a small text block describing up to first 2 items
        items = obj.get("items") if isinstance(obj, dict) else None
        if not isinstance(items, list) or not items:
            items = [gen_flat_item()]
        # attributes from union of first item keys (cap to 6)
        attrs = list(items[0].keys())[: min(6, len(items[0]))] or ["name", "value"]
        text_lines = []
        for it in items[:2]:
            pairs = [f"{k}: {str(it.get(k, ''))}" for k in attrs]
            text_lines.append(" | ".join(pairs))
        text = "\n".join(text_lines)
        prompt = prompt_text_to_xml(text, attrs)
        ans = dict_to_xml_sized(obj, root_name="root")
        if validate_xml(ans):
            out.append(make_sample("C_XML", "text_to_xml", "extract", prompt, ans))
    return out


def build_xml_to_yaml(n: int) -> List[Dict[str, Any]]:
    out = []
    for _ in range(n):
        obj = gen_object()
        xml_in = dict_to_xml_sized(obj, root_name="root")
        yml = dict_to_yaml(obj)
        prompt = prompt_xml_to_yaml(xml_in)
        if validate_yaml(yml):
            out.append(make_sample("C_XML", "xml_to_yaml", "transform", prompt, yml))
    return out


def build_json_to_toml(n: int) -> List[Dict[str, Any]]:
    out = []
    for _ in range(n):
        obj = gen_object()
        js = safe_json_sized(obj, 1800)
        prompt = prompt_json_to_toml(js)
        ans = dict_to_toml(obj)
        if validate_toml(ans):
            out.append(make_sample("C_TOML", "json_to_toml", "transform", prompt, ans))
    return out


def build_yaml_to_toml(n: int) -> List[Dict[str, Any]]:
    out = []
    for _ in range(n):
        obj = gen_object()
        yml = dict_to_yaml(obj)
        prompt = prompt_yaml_to_toml(yml)
        ans = dict_to_toml(obj)
        if validate_toml(ans):
            out.append(make_sample("C_TOML", "yaml_to_toml", "transform", prompt, ans))
    return out


def build_text_to_toml(n: int) -> List[Dict[str, Any]]:
    """Generate light text→TOML tasks.

    We produce a minimal text snippet listing key: value pairs for the first
    item, and expect TOML with items array-of-tables for the full object.
    """
    out = []
    for _ in range(n):
        obj = gen_object()
        # attributes = keys from the first item (small set)
        first = obj["items"][0] if obj.get("items") else {}
        attrs = list(first.keys())[: min(6, len(first))] or ["name", "value"]
        # make a short text block: key: value | key: value
        pairs = [f"{k}: {str(first.get(k, ''))}" for k in attrs]
        text = " | ".join(pairs)
        prompt = prompt_text_to_toml(text, attrs)
        ans = dict_to_toml(obj)
        if validate_toml(ans):
            out.append(make_sample("C_TOML", "text_to_toml", "extract", prompt, ans))
    return out


def _write_jsonl(path: str, rows: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _smoke(path: str) -> Tuple[int, int, int]:
    """Smoke-validate assistant outputs per format using strict validators."""
    import io
    n = ok = ng = 0
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            n += 1
            obj = json.loads(ln)
            msgs = obj.get("messages", [])
            if not msgs or msgs[-1].get("role") != "assistant":
                ng += 1
                continue
            ans = msgs[-1].get("content", "")
            sub = obj.get("subcategory", "")
            ok_flag = True
            if sub.endswith("_to_xml") or sub == "xml_to_yaml":
                # if assistant is XML: validate_xml; if assistant is YAML: validate_yaml
                if sub.endswith("_to_xml"):
                    ok_flag = validate_xml(ans)
                elif sub == "xml_to_yaml":
                    ok_flag = validate_yaml(ans)
            elif sub.endswith("_to_toml") or sub == "text_to_toml":
                ok_flag = validate_toml(ans)
            else:
                # For non-target types, skip strictness
                ok_flag = True

            if ok_flag:
                ok += 1
            else:
                ng += 1
    return n, ok, ng


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/dummy_structured_sft.jsonl")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--require_validators", type=int, default=1,
                    help="If 1, fail when YAML/TOML validators are unavailable")
    ap.add_argument("--n_json_to_xml", type=int, default=300)
    ap.add_argument("--n_yaml_to_xml", type=int, default=300)
    ap.add_argument("--n_csv_to_xml", type=int, default=0)
    ap.add_argument("--n_text_to_xml", type=int, default=0)
    ap.add_argument("--n_xml_to_yaml", type=int, default=150)
    ap.add_argument("--n_json_to_toml", type=int, default=150)
    ap.add_argument("--n_yaml_to_toml", type=int, default=150)
    ap.add_argument("--n_text_to_toml", type=int, default=150)
    args = ap.parse_args()

    random.seed(args.seed)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    # Ensure validators if required
    if args.require_validators:
        missing = []
        if _yaml is None:
            missing.append("PyYAML")
        global _TOML_LOADER
        if _TOML_LOADER is None:
            try:
                import tomllib as _tomllib_local  # type: ignore
                _TOML_LOADER = _tomllib_local
            except Exception:
                try:
                    import tomli as _tomli_local  # type: ignore
                    _TOML_LOADER = _tomli_local
                except Exception:
                    _TOML_LOADER = None
        if _TOML_LOADER is None:
            missing.append("tomllib/tomli")
        if missing:
            raise RuntimeError(
                f"Missing validators: {', '.join(missing)}. Install them or pass --require_validators 0.")

    rows: List[Dict[str, Any]] = []
    rows += build_json_to_xml(args.n_json_to_xml)
    rows += build_yaml_to_xml(args.n_yaml_to_xml)
    rows += build_csv_to_xml(args.n_csv_to_xml)
    rows += build_text_to_xml(args.n_text_to_xml)
    rows += build_xml_to_yaml(args.n_xml_to_yaml)
    rows += build_json_to_toml(args.n_json_to_toml)
    rows += build_yaml_to_toml(args.n_yaml_to_toml)
    rows += build_text_to_toml(args.n_text_to_toml)

    _write_jsonl(args.out, rows)
    n, ok, ng = _smoke(args.out)
    print(f"Wrote {len(rows)} samples -> {args.out}")
    print(f"[SMOKE] checked={n} ok={ok} ng={ng} pass_rate={(ok/max(1,n)):.3f}")

    # Simple hints if failure detected
    if ng > 0:
        print("NOTE: Some assistant outputs failed strict parsing. Consider lowering counts\n"
              "for the failing subgroup or adjusting generators.")


if __name__ == "__main__":
    main()
