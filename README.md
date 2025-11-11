# GroupDocs Product Version Grid

Generates a Markdown table of the latest product versions across:

- NuGet (.NET)
- GroupDocs Releases (Java)
- PyPI (Python via .NET)
- NPM (Node.js via Java)

Products covered: annotation, assembly, classification, comparison, conversion, editor, markdown, merger, metadata, parser, redaction, search, signature, total, viewer, watermark.

## Requirements

- For Python usage: Python 3.8+

## Usage

From the repository root:

1) Install dependencies:

```bash
pip install -r requirements.txt
```

2) Run the generator:

```bash
python build_product_grid.py
```

2. The output file `PRODUCT_VERSIONS.md` will be created/updated at the repository root.

## Data sources

- NuGet package per product: `groupdocs.{product}`
- GroupDocs Releases (Java/Maven): `https://releases.groupdocs.com/java/repo/com/groupdocs/groupdocs-{product}/`
- PyPI package per product: `groupdocs-{product}-net`
- NPM package per product: `@groupdocs/groupdocs.{product}`

If a product is not available for a given source, the corresponding cell remains empty.

## Notes

- GroupDocs Releases versioning follows `YY.M` or `YY.M.H` (e.g., `25.7`, `25.7.1`), where the first part is year, second is month, and third (optional) is the hot-fix number.


