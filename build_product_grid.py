import concurrent.futures
import datetime
import html
import json
import re
from pathlib import Path

import requests


PRODUCTS = [
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

# Additional NuGet-only products (package_id: display_name)
ADDITIONAL_NUGET_PRODUCTS = {
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


def get_nuget_latest(product: str, package_id: str = None):
    if package_id is None:
        package_id = f"groupdocs.{product}"
    url = f"https://api.nuget.org/v3-flatcontainer/{package_id}/index.json"
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


def get_releases_latest(product: str):
    url = f"https://releases.groupdocs.com/java/repo/com/groupdocs/groupdocs-{product}/"
    text = safe_get_text(url)
    if not text:
        return None
    versions = parse_releases_versions_from_html(text)
    if not versions:
        return None
    versions.sort(key=compare_release_versions_key)
    return versions[-1]


def get_pypi_latest(product: str):
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


def get_npm_latest(product: str):
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
        nuget_ver = r.get("nuget")
        releases_ver = r.get("releases")
        pypi_ver = r.get("pypi")
        npm_ver = r.get("npm")
        # Use custom package_id if provided, otherwise use default format
        nuget_package_id = r.get("nuget_package_id") or f"groupdocs.{r['product'].lower()}"
        nuget_cell = f"[{nuget_ver}](https://www.nuget.org/packages/{nuget_package_id}/{nuget_ver})" if nuget_ver else ""
        releases_cell = f"[{releases_ver}](https://releases.groupdocs.com/java/repo/com/groupdocs/groupdocs-{r['product'].lower()}/{releases_ver}/)" if releases_ver else ""
        pypi_pkg = f"groupdocs-{r['product'].lower()}-net"
        pypi_cell = f"[{pypi_ver}](https://pypi.org/project/{pypi_pkg}/{pypi_ver}/)" if pypi_ver else ""
        npm_cell = f"[{npm_ver}](https://www.npmjs.com/package/@groupdocs/groupdocs.{r['product'].lower()}/v/{npm_ver})" if npm_ver else ""
        lines.append(f"| {r['product']} | {nuget_cell} | {releases_cell} | {pypi_cell} | {npm_cell} |")
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
            r.get("nuget") or "",
            r.get("releases") or "",
            r.get("pypi") or "",
            r.get("npm") or ""
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
    nuget = get_nuget_latest(product)
    releases = get_releases_latest(product)
    pypi = get_pypi_latest(product)
    npm = get_npm_latest(product)
    print(f"Done {display}", flush=True)
    return {
        "product": display,
        "nuget": nuget,
        "releases": releases,
        "pypi": pypi,
        "npm": npm,
    }


def build_nuget_only_row(package_id: str, display_name: str):
    print(f"Checking {display_name} (NuGet only)...", flush=True)
    nuget = get_nuget_latest("", package_id=package_id)
    print(f"Done {display_name}", flush=True)
    return {
        "product": display_name,
        "nuget": nuget,
        "releases": None,
        "pypi": None,
        "npm": None,
        "nuget_package_id": package_id,
    }


def main():
    main_rows = []
    additional_rows = []
    # Parallelize across products for speed
    main_tasks = {}
    additional_tasks = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(PRODUCTS) + len(ADDITIONAL_NUGET_PRODUCTS) or 1)) as ex:
        # Submit regular products
        for p in PRODUCTS:
            main_tasks[ex.submit(build_row, p)] = "main"
        # Submit additional NuGet-only products
        for package_id, display_name in ADDITIONAL_NUGET_PRODUCTS.items():
            additional_tasks[ex.submit(build_nuget_only_row, package_id, display_name)] = "additional"
        # Collect results
        for fut in concurrent.futures.as_completed(main_tasks):
            main_rows.append(fut.result())
        for fut in concurrent.futures.as_completed(additional_tasks):
            additional_rows.append(fut.result())
    main_rows.sort(key=lambda r: r["product"])
    # Sort additional products: UI first, then CLI, alphabetically within each type
    def additional_sort_key(r):
        product_name = r["product"]
        # Check if it's a UI product (ends with .UI or contains .UI)
        is_ui = ".UI" in product_name or product_name.endswith("UI")
        # Return tuple: (0 for UI, 1 for CLI), then product name for alphabetical sorting
        return (0 if is_ui else 1, product_name)
    additional_rows.sort(key=additional_sort_key)

    now = datetime.datetime.now(datetime.UTC).isoformat() + "Z"
    heading = (
        "# GroupDocs Product Versions (Latest)\n\n"
        f"Generated on {now}\n\n"
        "Source: https://releases.groupdocs.com/\n\n"
    )
    
    # Generate two separate tables with headers
    main_table = markdown_table(main_rows)
    additional_table = markdown_table(additional_rows)
    
    content = heading + "## Main Products\n\n" + main_table + "\n\n## Derived Products\n\n" + additional_table + "\n"

    script_dir = Path(__file__).resolve().parent
    out_path = (script_dir / "PRODUCT_VERSIONS.md").resolve()
    out_path.write_text(content, encoding="utf-8")
    print(f"Wrote {out_path}")

    # Also print console-friendly tables
    print("\nMain Products:\n")
    print(console_table(main_rows))
    print("\nDerived Products:\n")
    print(console_table(additional_rows))

    # Write JSON state for automation workflows (combined for change detection)
    all_rows = main_rows + additional_rows
    versions_map = {r["product"]: {"nuget": r.get("nuget"), "releases": r.get("releases"), "pypi": r.get("pypi"), "npm": r.get("npm")} for r in all_rows}
    json_state = {"generatedAt": now, "versions": versions_map}
    json_path = (script_dir / "product_versions.json").resolve()
    json_path.write_text(json.dumps(json_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()


