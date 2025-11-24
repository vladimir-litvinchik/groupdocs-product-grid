import argparse
import json
from pathlib import Path


def load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def build_change_markdown(old: dict, new: dict) -> str:
    old_versions = (old.get("versions") or {})
    new_versions = (new.get("versions") or {})
    products = sorted(set(old_versions.keys()) | set(new_versions.keys()))
    lines = []
    for p in products:
        o = old_versions.get(p) or {}
        n = new_versions.get(p) or {}
        changes = []
        for src in ["net", "java", "python-net", "nodejs-java"]:
            ov = o.get(src) or None
            nv = n.get(src) or None
            if ov != nv:
                changes.append(f"- {src}: {ov or '∅'} -> {nv or '∅'}")
        if changes:
            lines.append(f"### {p}")
            lines.extend(changes)
            lines.append("")
    if not lines:
        return "# Product version changes\n\nNo changes detected."
    return "# Product version changes\n\n" + "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="Path to previous product_versions.json")
    ap.add_argument("--new", required=True, help="Path to current product_versions.json")
    ap.add_argument("--out", required=True, help="Path to write markdown summary")
    args = ap.parse_args()

    old = load_json(Path(args.old))
    new = load_json(Path(args.new))
    body = build_change_markdown(old, new)
    Path(args.out).write_text(body, encoding="utf-8")


if __name__ == "__main__":
    main()


