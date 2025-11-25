import concurrent.futures
import datetime
import html
import json
import re
from pathlib import Path

import requests


MAIN_PRODUCTS = [
    "annotation",
    "assembly",
    "classification",
    "comparison",
    "conversion",
    "editor",
    "markdown",
    "merger",
    "metadata",
    "parser",
    "redaction",
    "search",
    "signature",
    "total",
    "viewer",
    "watermark",
]

# Derived .NET-only products (package_id: display_name)
DERIVED_PRODUCTS = {
    "GroupDocs.Viewer.UI": "Viewer.UI",
    "GroupDocs.Editor.UI.Api": "Editor.UI",
    "GroupDocs.Comparison.UI": "Comparison.UI",
    "GroupDocs.Conversion-CLI": "Conversion-CLI",
    "GroupDocs.Viewer-CLI": "Viewer-CLI",
    "GroupDocs.Metadata-CLI": "Metadata-CLI",
}

USER_AGENT = "groupdocs-product-grid/1.0 (+https://releases.groupdocs.com/)"
TIMEOUT = 15


def to_display_name(product: str) -> str:
    return product[:1].upper() + product[1:]


def safe_get_json(url: str):
    try:
        res = requests.get(
            url,
            headers={"user-agent": USER_AGENT, "accept": "application/json, text/plain, */*"},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()
    except Exception:
        return None


def safe_get_text(url: str):
    try:
        res = requests.get(
            url,
            headers={"user-agent": USER_AGENT, "accept": "text/html, */*"},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.text
    except Exception:
        return None


def get_net_latest(product: str, package_id: str = None):
    if package_id is None:
        package_id = f"groupdocs.{product}"
    normalized_package_id = package_id.lower()
    url = f"https://api.nuget.org/v3-flatcontainer/{normalized_package_id}/index.json"
    data = safe_get_json(url)
    if not data:
        return None
    versions = data.get("versions") or []
    return versions[-1] if versions else None


_re_ver_dir = re.compile(r">(\d{2}\.\d{1,2}(?:\.\d+)?)[/</]")


def parse_releases_versions_from_html(html_text: str):
    versions = set()
    for m in _re_ver_dir.finditer(html_text):
        versions.add(html.unescape(m.group(1)))
    return list(versions)


def compare_release_versions_key(ver: str):
    parts = ver.split(".")
    y = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else -1
    m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else -1
    h = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return (y, m, h)


def get_java_latest(product: str):
    url = f"https://releases.groupdocs.com/java/repo/com/groupdocs/groupdocs-{product}/"
    text = safe_get_text(url)
    if not text:
        return None
    versions = parse_releases_versions_from_html(text)
    if not versions:
        return None
    versions.sort(key=compare_release_versions_key)
    return versions[-1]


def get_python_net_latest(product: str):
    pkg = f"groupdocs-{product}-net"
    url = f"https://pypi.org/pypi/{pkg}/json"
    data = safe_get_json(url)
    if not data:
        return None
    info = data.get("info") or {}
    return info.get("version")


_split_semverish = re.compile(r"[.\-]")


def _semverish_key(ver: str):
    tokens = _split_semverish.split(ver)
    key = []
    for t in tokens:
        if t.isdigit():
            key.append((0, int(t)))
        else:
            key.append((1, t))
    return tuple(key)


def get_nodejs_java_latest(product: str):
    # encoded @groupdocs/groupdocs.{product} => @groupdocs%2Fgroupdocs.{product}
    url = f"https://registry.npmjs.org/@groupdocs%2Fgroupdocs.{product}"
    data = safe_get_json(url)
    if not data:
        return None
    dist_tags = data.get("dist-tags") or {}
    if "latest" in dist_tags:
        return dist_tags["latest"]
    versions = data.get("versions")
    if isinstance(versions, dict) and versions:
        keys = list(versions.keys())
        keys.sort(key=_semverish_key)
        return keys[-1]
    return None


def markdown_table(rows):
    header = [
        "Product",
        ".NET",
        "Java",
        "Python via .NET",
        "Node.js via Java",
    ]
    lines = []
    lines.append(f"| {' | '.join(header)} |")
    # First column left-aligned, rest center-aligned
    separators = ["---"] + [":---:"] * (len(header) - 1)
    lines.append(f"| {' | '.join(separators)} |")
    for r in rows:
        net_ver = r.get("net")
        java_ver = r.get("java")
        python_net_ver = r.get("python-net")
        nodejs_java_ver = r.get("nodejs-java")
        # Use custom package_id if provided, otherwise use default format
        net_package_id = r.get("net_package_id") or f"groupdocs.{r['product'].lower()}"
        net_cell = f"[{net_ver}](https://www.nuget.org/packages/{net_package_id}/{net_ver})" if net_ver else ""
        java_cell = f"[{java_ver}](https://releases.groupdocs.com/java/repo/com/groupdocs/groupdocs-{r['product'].lower()}/{java_ver}/)" if java_ver else ""
        python_net_pkg = f"groupdocs-{r['product'].lower()}-net"
        python_net_cell = f"[{python_net_ver}](https://pypi.org/project/{python_net_pkg}/{python_net_ver}/)" if python_net_ver else ""
        nodejs_java_cell = f"[{nodejs_java_ver}](https://www.npmjs.com/package/@groupdocs/groupdocs.{r['product'].lower()}/v/{nodejs_java_ver})" if nodejs_java_ver else ""
        lines.append(f"| {r['product']} | {net_cell} | {java_cell} | {python_net_cell} | {nodejs_java_cell} |")
    return "\n".join(lines)


def console_table(rows):
    header = [
        "Product",
        ".NET",
        "Java",
        "Python via .NET",
        "Node.js via Java",
    ]
    # Prepare raw version cells (no links) for console display
    data_rows = []
    for r in rows:
        data_rows.append([
            r["product"],
            r.get("net") or "",
            r.get("java") or "",
            r.get("python-net") or "",
            r.get("nodejs-java") or ""
        ])
    # Compute column widths
    widths = [len(h) for h in header]
    for row in data_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    # Builders
    def fmt_row(cols):
        return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols)) + " |"
    sep = "|-" + "-|-".join("-" * w for w in widths) + "-|"
    lines = [fmt_row(header), sep]
    for row in data_rows:
        lines.append(fmt_row(row))
    return "\n".join(lines)


def build_row(product: str):
    display = to_display_name(product)
    print(f"Checking {display}...", flush=True)
    net = get_net_latest(product)
    java = get_java_latest(product)
    python_net = get_python_net_latest(product)
    nodejs_java = get_nodejs_java_latest(product)
    print(f"Done {display}", flush=True)
    return {
        "product": display,
        "net": net,
        "java": java,
        "python-net": python_net,
        "nodejs-java": nodejs_java,
    }


def build_net_only_row(package_id: str, display_name: str):
    print(f"Checking {display_name} (.NET only)...", flush=True)
    net = get_net_latest("", package_id=package_id)
    print(f"Done {display_name}", flush=True)
    return {
        "product": display_name,
        "net": net,
        "java": None,
        "python-net": None,
        "nodejs-java": None,
        "net_package_id": package_id,
    }


def update_readme(script_dir: Path, main_rows: list, derived_rows: list, timestamp: str):
    """Update README.md with the latest product versions."""
    readme_path = (script_dir / "README.md").resolve()
    if not readme_path.exists():
        print(f"Warning: README.md not found at {readme_path}, skipping update")
        return
    
    # Read the current README content
    readme_content = readme_path.read_text(encoding="utf-8")
    
    # Find the section to replace (from "## Product Versions (Latest)" to next "##")
    start_marker = "## Product Versions (Latest)"
    start_idx = readme_content.find(start_marker)
    
    if start_idx == -1:
        print(f"Warning: Could not find '{start_marker}' in README.md, skipping update")
        return
    
    # Find the next "##" section (Requirements, Usage, Data sources, or Notes)
    next_section_idx = len(readme_content)
    for marker in ["\n## Requirements", "\n## Usage", "\n## Data sources", "\n## Notes"]:
        idx = readme_content.find(marker, start_idx)
        if idx != -1 and idx < next_section_idx:
            next_section_idx = idx
    
    # Generate the new content for the Product Versions section
    main_table = markdown_table(main_rows)
    derived_table = markdown_table(derived_rows)
    
    new_section = (
        f"## Product Versions (Latest)\n\n"
        f"Updated on {timestamp}\n\n"
        f"### Main Products\n\n"
        f"{main_table}\n\n"
        f"### Derived Products\n\n"
        f"{derived_table}\n\n"
    )
    
    # Replace the section
    updated_content = (
        readme_content[:start_idx] + 
        new_section + 
        readme_content[next_section_idx:]
    )
    
    # Write back to file
    readme_path.write_text(updated_content, encoding="utf-8")
    print(f"Updated {readme_path}")


def main():
    main_rows = []
    derived_rows = []
    # Parallelize across products for speed
    main_tasks = {}
    derived_tasks = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(MAIN_PRODUCTS) + len(DERIVED_PRODUCTS) or 1)) as ex:
        # Submit regular products
        for p in MAIN_PRODUCTS:
            main_tasks[ex.submit(build_row, p)] = "main"
        # Submit additional .NET-only products
        for package_id, display_name in DERIVED_PRODUCTS.items():
            derived_tasks[ex.submit(build_net_only_row, package_id, display_name)] = "derived"
        # Collect results
        for fut in concurrent.futures.as_completed(main_tasks):
            main_rows.append(fut.result())
        for fut in concurrent.futures.as_completed(derived_tasks):
            derived_rows.append(fut.result())
    main_rows.sort(key=lambda r: r["product"])
    # Sort additional products: UI first, then CLI, alphabetically within each type
    def derived_sort_key(r):
        product_name = r["product"]
        # Check if it's a UI product (ends with .UI or contains .UI)
        is_ui = ".UI" in product_name or product_name.endswith("UI")
        # Return tuple: (0 for UI, 1 for CLI), then product name for alphabetical sorting
        return (0 if is_ui else 1, product_name)
    derived_rows.sort(key=derived_sort_key)

    now = datetime.datetime.now(datetime.UTC).isoformat() + "Z"
    heading = (
        "# GroupDocs Product Versions (Latest)\n\n"
        f"Generated on {now}\n\n"
    )
    
    # Generate two separate tables with headers
    main_table = markdown_table(main_rows)
    derived_table = markdown_table(derived_rows)
    
    content = heading + "## Main Products\n\n" + main_table + "\n\n## Derived Products\n\n" + derived_table + "\n"

    script_dir = Path(__file__).resolve().parent
    out_path = (script_dir / "PRODUCT_VERSIONS.md").resolve()
    out_path.write_text(content, encoding="utf-8")
    print(f"Wrote {out_path}")

    # Also print console-friendly tables
    print("\nMain Products:\n")
    print(console_table(main_rows))
    print("\nDerived Products:\n")
    print(console_table(derived_rows))

    # Write JSON state for automation workflows (combined for change detection)
    all_rows = main_rows + derived_rows
    versions_map = {r["product"]: {"net": r.get("net"), "java": r.get("java"), "python-net": r.get("python-net"), "nodejs-java": r.get("nodejs-java")} for r in all_rows}
    json_state = {"generatedAt": now, "versions": versions_map}
    json_path = (script_dir / "product_versions.json").resolve()
    json_path.write_text(json.dumps(json_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {json_path}")
    
    # Update README.md with latest product versions
    update_readme(script_dir, main_rows, derived_rows, now)


if __name__ == "__main__":
    main()


