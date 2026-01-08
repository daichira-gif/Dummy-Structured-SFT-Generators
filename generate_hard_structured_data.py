#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate hard SFT samples for StructEval‑T weak areas:
- JSON -> XML (nested dicts + arrays, mixed types)
- XML  -> YAML (same as above, deeper nesting preserved)
- Text -> TOML (extraction, array-of-tables, nested subtables)
- Text -> YAML (extraction, nested objects)

Assistant outputs are deterministically serialized to guarantee syntax
validity. A strict smoke test validates generated answers.

Example:
  python -m tools.generate_hard_structured_data \
    --out outputs/dummy_structured_sft_hard.jsonl \
    --n_json_to_xml 1000 --n_xml_to_yaml 1000 \
    --n_text_to_toml 1000 --n_text_to_yaml 1000
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, List, Tuple

try:
    import yaml as _yaml  # type: ignore
except Exception:
    _yaml = None

try:
    from xml.etree import ElementTree as _ET
except Exception:
    _ET = None

_TOML_LOADER = None  # tomllib / tomli resolved lazily


# ----------------------------- Validators -----------------------------

def _ensure_toml_loader():
    global _TOML_LOADER
    if _TOML_LOADER is not None:
        return
    try:
        import tomllib as _tomllib_local  # type: ignore
        _TOML_LOADER = _tomllib_local
    except Exception:
        try:
            import tomli as _tomli_local  # type: ignore
            _TOML_LOADER = _tomli_local
        except Exception:
            _TOML_LOADER = None


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
        return False
    try:
        _yaml.safe_load(s)
        return True
    except Exception:
        return False


def validate_toml(s: str) -> bool:
    _ensure_toml_loader()
    if _TOML_LOADER is None:
        return False
    try:
        _TOML_LOADER.loads(s)
        return True
    except Exception:
        return False


# ----------------------------- Prompts -----------------------------

def p_json_to_xml(js: str) -> str:
    return (
        "Convert the following JSON into well-formed XML.\n"
        "Constraints:\n"
        "- Use child elements only (no XML attributes).\n"
        "- Preserve key names and their letter case exactly.\n"
        "- Represent lists by repeating child elements in order.\n"
        "Return ONLY XML.\n\nJSON:\n" + js
    )


def p_xml_to_yaml(xml_s: str) -> str:
    return (
        "Convert the following XML into YAML.\n"
        "Constraints:\n"
        "- Preserve original tag names exactly (no renaming to snake_case).\n"
        "- Child elements become mapping keys; repeated elements become lists.\n"
        "- Keep ordering and nesting as in XML.\n"
        "Return ONLY YAML.\n\nXML:\n" + xml_s
    )


def p_text_to_toml(text: str, attrs: List[str]) -> str:
    return (
        "Extract the following attributes from text and output TOML.\n"
        "Constraints:\n"
        "- Output ONLY the requested attributes (no extra keys).\n"
        "- Preserve key paths and nesting exactly as specified.\n"
        "- Use dotted tables and arrays-of-tables to represent nested objects and lists.\n"
        "- Do NOT use TOML inline tables (curly braces like { ... }).\n"
        "- Do NOT wrap values in JSON/HCL-style objects. Use [tables] / [[tables]] only.\n"
        "Return ONLY TOML.\n\nATTRIBUTES:\n"
        + ", ".join(attrs)
        + "\n\nTEXT:\n" + text
    )


def p_text_to_yaml(text: str, attrs: List[str]) -> str:
    return (
        "Extract the following attributes from text and output YAML.\n"
        "Constraints:\n"
        "- Output ONLY the requested attributes (no extra keys).\n"
        "- Preserve key paths and nesting exactly as specified.\n"
        "Return ONLY YAML.\n\nATTRIBUTES:\n"
        + ", ".join(attrs)
        + "\n\nTEXT:\n" + text
    )


# --------------------------- Hard object builder ---------------------------

WORDS = [
    "alpha", "beta", "gamma", "delta", "omega", "zephyr", "lumen",
    "nova", "aurora", "ember", "terra", "eon", "atlas", "velox",
]


def _w() -> str:
    return random.choice(WORDS)


def _key() -> str:
    a, b = _w(), _w()
    return f"{a}_{b}" if random.random() < 0.5 else f"{a}{b.title()}"


def _scalar() -> Any:
    r = random.random()
    if r < 0.20:
        return random.randint(0, 9999)
    if r < 0.40:
        return round(random.uniform(0, 9999) + random.random(), 2)
    if r < 0.60:
        return bool(random.getrandbits(1))
    if r < 0.80:
        return "" if random.random() < 0.3 else _w().title()
    return _w()


def _flat_item(kmin=5, kmax=9) -> Dict[str, Any]:
    n = random.randint(kmin, kmax)
    d = { _key(): _scalar() for _ in range(n) }
    # Insert structured sub-objects
    if random.random() < 0.9:
        d["dimensions"] = {
            "height_cm": round(random.uniform(1.0, 300.0), 1),
            "width_cm": round(random.uniform(1.0, 300.0), 1),
            "depth_cm": round(random.uniform(0.5, 100.0), 1),
        }
    if random.random() < 0.8:
        d["flags"] = {"featured": bool(random.getrandbits(1)), "archived": bool(random.getrandbits(1))}
    if random.random() < 0.8:
        d["tags"] = [_w(), _w(), _w()][: random.randint(1, 3)]
    if random.random() < 0.7:
        d["meta"] = [{"key": "origin", "value": _w().title()}, {"key": "year", "value": random.randint(1900, 2025)}]
    return d


def gen_hard_object() -> Dict[str, Any]:
    n_items = random.randint(3, 6)
    items = []
    for i in range(n_items):
        it = _flat_item()
        # Occasionally add nested arrays-of-dicts
        if random.random() < 0.5:
            it["components"] = [
                {"name": _w().title(), "qty": random.randint(1, 5)},
                {"name": _w().title(), "qty": random.randint(1, 5)},
            ]
        # Sometimes add sparse/empty fields
        if random.random() < 0.3:
            it["notes"] = "" if random.random() < 0.5 else _w().title()
        items.append(it)
    return {"items": items}


# --------------------------- Serializers (hard) ---------------------------

def _xml_sanitize_tag(k: str) -> str:
    k = (k or "").strip()
    if not k or not (k[0].isalpha() or k[0] == "_"):
        return "field"
    # avoid xml* reserved
    if k.lower().startswith("xml"):
        return "field"
    return k


def dict_to_xml_recursive(obj: Any, root_name: str = "root") -> str:
    if _ET is None:
        return "<root/>"
    root = _ET.Element(root_name)

    def build(parent, x):
        if isinstance(x, dict):
            # preserve insertion order to minimize evaluation mismatches
            for k in x.keys():
                tag = _xml_sanitize_tag(str(k))
                child = _ET.SubElement(parent, tag)
                build(child, x[k])
        elif isinstance(x, list):
            for it in x:
                child = _ET.SubElement(parent, "item")
                build(child, it)
        else:
            parent.text = "" if x is None else str(x)

    build(root, obj)
    return _ET.tostring(root, encoding="unicode")


def dict_to_yaml(obj: Any) -> str:
    if _yaml is None:
        # Fallback: JSON text to keep format shape; validation will fail if strict.
        return json.dumps(obj, ensure_ascii=False)
    return _yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)


def dict_to_toml(obj: Dict[str, Any]) -> str:
    # Array-of-tables for items; nested dicts as dotted tables when suitable
    lines: List[str] = []

    def emit_scalar(k: str, v: Any):
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, int):
            lines.append(f"{k} = {v}")
        elif isinstance(v, float):
            lines.append(f"{k} = {v}")
        else:
            s = str(v).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k} = "{s}"')

    def emit_table(prefix: List[str], d: Dict[str, Any]):
        scalars, nested_dicts, list_dicts, list_scalars = {}, {}, {}, {}
        for k, v in d.items():
            if isinstance(v, dict):
                nested_dicts[k] = v
            elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                list_dicts[k] = v
            elif isinstance(v, list):
                list_scalars[k] = v
            else:
                scalars[k] = v

        for k in sorted(scalars.keys()):
            emit_scalar(k, scalars[k])

        for k in sorted(list_scalars.keys()):
            arr_vals = []
            for x in list_scalars[k][:20]:
                if isinstance(x, (dict, list)):
                    continue
                if isinstance(x, bool):
                    arr_vals.append('true' if x else 'false')
                elif isinstance(x, (int, float)):
                    arr_vals.append(str(x))
                else:
                    s = str(x).replace("\\", "\\\\").replace('"', '\\"')
                    arr_vals.append(f'"{s}"')
            lines.append(f"{k} = [{', '.join(arr_vals)}]")

        for k in sorted(nested_dicts.keys()):
            sect = prefix + [k]
            lines.append("")
            lines.append(f"[{'.'.join(sect)}]")
            emit_table(sect, nested_dicts[k])

        for k in sorted(list_dicts.keys()):
            sect = prefix + [k]
            for item in list_dicts[k][:10]:
                lines.append("")
                lines.append(f"[[{'.'.join(sect)}]]")
                emit_table(sect, item)

    items = obj.get("items") if isinstance(obj, dict) else None
    if isinstance(items, list) and items:
        for it in items:
            lines.append("")
            lines.append("[[items]]")
            if isinstance(it, dict):
                emit_table(["items"], it)
    else:
        emit_table([], obj if isinstance(obj, dict) else {"value": obj})

    s = "\n".join(lines).strip() + "\n"
    return s


# --------------------------- Sample builders ---------------------------

def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _make_sample(cat: str, sub: str, task: str, prompt: str, answer: str) -> Dict[str, Any]:
    sid = _sha1(prompt + "\n\n" + answer)
    return {
        "id": sid,
        "category": cat,
        "subcategory": sub,
        "task": task,
        "seed": "dummy_hard",
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ],
    }


def build_json_to_xml(n: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for _ in range(n):
        obj = gen_hard_object()
        js = json.dumps(obj, ensure_ascii=False)
        prompt = p_json_to_xml(js)
        ans = dict_to_xml_recursive(obj, root_name="root")
        if validate_xml(ans):
            out.append(_make_sample("C_XML", "json_to_xml", "transform", prompt, ans))
    return out


def build_xml_to_yaml(n: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for _ in range(n):
        obj = gen_hard_object()
        xml_in = dict_to_xml_recursive(obj, root_name="root")
        yml = dict_to_yaml(obj)
        prompt = p_xml_to_yaml(xml_in)
        if validate_yaml(yml):
            out.append(_make_sample("C_XML", "xml_to_yaml", "transform", prompt, yml))
    return out


def _attrs_from_first_item(obj: Dict[str, Any]) -> List[str]:
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list) or not items:
        return ["name", "value"]
    first = items[0]
    if not isinstance(first, dict):
        return ["name", "value"]
    # prefer a mix of scalar and nested keys
    keys = list(first.keys())
    random.shuffle(keys)
    return keys[: min(8, len(keys))] or ["name", "value"]


def _text_from_attrs(first: Dict[str, Any], attrs: List[str]) -> str:
    pairs = []
    for k in attrs:
        v = first.get(k, "") if isinstance(first, dict) else ""
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        pairs.append(f"{k}: {v}")
    return " | ".join(pairs)


def _tokenize_attr_path(path: str) -> List[Any]:
    # Split dot and bracket notation, e.g., "a.b[1].c" -> ["a","b",1,"c"]
    out: List[Any] = []
    buf = ""
    i = 0
    while i < len(path):
        ch = path[i]
        if ch == '.':
            if buf:
                out.append(buf)
                buf = ""
            i += 1
            continue
        if ch == '[':
            if buf:
                out.append(buf)
                buf = ""
            j = path.find(']', i+1)
            if j == -1:
                # malformed -> treat rest as token
                out.append(path[i:])
                break
            idx = path[i+1:j]
            try:
                out.append(int(idx))
            except Exception:
                out.append(idx)
            i = j + 1
            continue
        buf += ch
        i += 1
    if buf:
        out.append(buf)
    return out


def _resolve_path(d: Any, path: str) -> Any:
    cur = d
    for tok in _tokenize_attr_path(path):
        if isinstance(tok, int):
            if not isinstance(cur, list) or tok >= len(cur):
                return ""
            cur = cur[tok]
        else:
            if not isinstance(cur, dict):
                return ""
            cur = cur.get(tok, "")
    if isinstance(cur, (dict, list)):
        return cur
    return cur


def _project_only_attrs(first: Dict[str, Any], attrs: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    def set_path(root: Dict[str, Any], path: str, value: Any):
        cur = root
        toks = _tokenize_attr_path(path)
        for i, tok in enumerate(toks):
            last = i == len(toks) - 1
            if isinstance(tok, int):
                # list index under current
                # ensure current is a list
                if not isinstance(cur, list):
                    # replace dict with list at this point if needed
                    # find the previous token holder to attach list
                    raise ValueError("Invalid path leading to list without container")
            if isinstance(tok, str):
                if last:
                    # assign scalar or structure at leaf
                    parent = cur
                    if isinstance(parent, dict):
                        parent[tok] = value
                    else:
                        # cannot assign into non-dict
                        return
                else:
                    nxt = toks[i+1]
                    if isinstance(nxt, int):
                        # need a list at tok
                        node = cur.get(tok, []) if isinstance(cur, dict) else []
                        if not isinstance(node, list):
                            node = []
                        # ensure size
                        cur.setdefault(tok, node) if isinstance(cur, dict) else None
                        cur = node
                    else:
                        # need a dict at tok
                        node = cur.get(tok, {}) if isinstance(cur, dict) else {}
                        if not isinstance(node, dict):
                            node = {}
                        if isinstance(cur, dict):
                            cur[tok] = node
                        cur = node
            else:  # integer index
                idx = tok
                # ensure list length
                while len(cur) <= idx:
                    cur.append("")
                if last:
                    cur[idx] = value
                else:
                    nxt = toks[i+1]
                    if isinstance(nxt, int):
                        if not isinstance(cur[idx], list):
                            cur[idx] = []
                        cur = cur[idx]
                    else:
                        if not isinstance(cur[idx], dict):
                            cur[idx] = {}
                        cur = cur[idx]

    # Root is one-item array-of-tables under 'items' to match prior style
    payload: Dict[str, Any] = {}
    for a in attrs:
        v = _resolve_path(first, a)
        set_path(payload, a, v)
    return {"items": [payload]}


def _enumerate_attr_paths(d: Dict[str, Any], max_depth: int = 2) -> List[str]:
    paths: List[str] = []

    def rec(prefix: List[str], x: Any, depth: int):
        if depth > max_depth:
            return
        if isinstance(x, dict):
            for k, v in x.items():
                rec(prefix + [k], v, depth + 1)
        elif isinstance(x, list):
            # sample first two indices to keep brevity
            for i, v in enumerate(x[:2]):
                rec(prefix + [f"[{i}]"] , v, depth + 1)
        else:
            # scalar
            # build path string
            comp: List[str] = []
            for t in prefix:
                if t.startswith("["):
                    comp[-1] = comp[-1] + t
                else:
                    comp.append(t)
            paths.append(".".join(comp))

    rec([], d, 0)
    # de-dup
    uniq = []
    seen = set()
    for p in paths:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def _pick_attrs_for_first(first: Dict[str, Any], k: int = 8) -> List[str]:
    cand = _enumerate_attr_paths(first, max_depth=2)
    random.shuffle(cand)
    # prefer including some nested (with '.') and some list indices ('[')
    nested = [p for p in cand if ('.' in p) or ('[' in p)]
    scalar = [p for p in cand if ('.' not in p) and ('[' not in p)]
    out = []
    out.extend(nested[: k // 2])
    out.extend(scalar[: k - len(out)])
    if not out:
        out = cand[:k]
    return out[:k]


def build_text_to_toml(n: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for _ in range(n):
        obj = gen_hard_object()
        items = obj.get("items") if isinstance(obj, dict) else None
        first = items[0] if isinstance(items, list) and items else {}
        attrs = _pick_attrs_for_first(first, k=8)
        # Build text strictly from requested attrs
        pairs = [f"{a}: {json.dumps(_resolve_path(first, a), ensure_ascii=False) if isinstance(_resolve_path(first, a), (dict, list)) else _resolve_path(first, a)}" for a in attrs]
        text = " | ".join(pairs)
        prompt = p_text_to_toml(text, attrs)
        reduced = _project_only_attrs(first, attrs)
        ans = dict_to_toml(reduced)
        if validate_toml(ans):
            out.append(_make_sample("C_TOML", "text_to_toml", "extract", prompt, ans))
    return out


def build_text_to_yaml(n: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for _ in range(n):
        obj = gen_hard_object()
        items = obj.get("items") if isinstance(obj, dict) else None
        first = items[0] if isinstance(items, list) and items else {}
        attrs = _pick_attrs_for_first(first, k=8)
        pairs = [f"{a}: {json.dumps(_resolve_path(first, a), ensure_ascii=False) if isinstance(_resolve_path(first, a), (dict, list)) else _resolve_path(first, a)}" for a in attrs]
        text = " | ".join(pairs)
        prompt = p_text_to_yaml(text, attrs)
        reduced = _project_only_attrs(first, attrs)
        yml = dict_to_yaml(reduced)
        if validate_yaml(yml):
            out.append(_make_sample("C_YAML", "text_to_yaml", "extract", prompt, yml))
    return out


def _write_jsonl(path: str, rows: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _smoke(path: str) -> Tuple[int, int, int]:
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
            if sub.endswith("_to_xml"):
                ok_flag = validate_xml(ans)
            elif sub in ("xml_to_yaml", "text_to_yaml"):
                ok_flag = validate_yaml(ans)
            elif sub == "text_to_toml":
                ok_flag = validate_toml(ans)
            if ok_flag:
                ok += 1
            else:
                ng += 1
    return n, ok, ng


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/dummy_structured_sft_hard.jsonl")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n_json_to_xml", type=int, default=1000)
    ap.add_argument("--n_xml_to_yaml", type=int, default=1000)
    ap.add_argument("--n_text_to_toml", type=int, default=1000)
    ap.add_argument("--n_text_to_yaml", type=int, default=1000)
    ap.add_argument("--require_validators", type=int, default=1, help="If 1, fail when YAML/TOML validators are unavailable")
    args = ap.parse_args()

    random.seed(args.seed)

    if args.require_validators:
        missing = []
        if _yaml is None:
            missing.append("PyYAML")
        _ensure_toml_loader()
        if _TOML_LOADER is None:
            missing.append("tomllib/tomli")
        if missing:
            raise RuntimeError(f"Missing validators: {', '.join(missing)}. Install them or pass --require_validators 0 to bypass.")

    rows: List[Dict[str, Any]] = []
    rows += build_json_to_xml(args.n_json_to_xml)
    rows += build_xml_to_yaml(args.n_xml_to_yaml)
    rows += build_text_to_toml(args.n_text_to_toml)
    rows += build_text_to_yaml(args.n_text_to_yaml)

    _write_jsonl(args.out, rows)
    n, ok, ng = _smoke(args.out)
    print(f"Wrote {len(rows)} samples -> {args.out}")
    print(f"[SMOKE] checked={n} ok={ok} ng={ng} pass_rate={(ok/max(1,n)):.3f}")
    if ng > 0:
        print("NOTE: Some answers failed strict parsing. Consider reducing counts or adjusting generators.")


if __name__ == "__main__":
    main()
