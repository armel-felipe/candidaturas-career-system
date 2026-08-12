#!/usr/bin/env python3
import argparse
import csv
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from notion_sync import notion_config, normalize_text, prop_text, query_all_database_pages, retrieve_database


DEFAULT_COLUMNS = [
    "ID",
    "Vaga",
    "empresa_int",
    "tipo de empresa_int",
    "Etapa Funil",
    "Tipo de Vaga",
    "Data Aplicação",
    "Canal de aplicacao",
    "URL",
    "Avaliacao de aderencia claude",
    "Descricao da Vaga",
]


PROPERTY_SOURCE_MAP = {
    "ID": ["ID"],
    "Vaga": ["Vaga"],
    "empresa_int": ["empresa_int", "Empresa"],
    "tipo de empresa_int": ["tipo de empresa_int", "Tipo de Empresa"],
    "Etapa Funil": ["Etapa Funil"],
    "Tipo de Vaga": ["Tipo de vaga"],
    "Data Aplicação": ["Data Aplicação", "Data Aplicacao"],
    "Canal de aplicacao": ["Canal de aplicacao"],
    "URL": ["URL"],
    "Avaliacao de aderencia claude": ["avaliação de aderencia claude"],
    "Descricao da Vaga": ["Descrição da Vaga"],
}


def first_prop(props: dict, names: list[str]) -> dict:
    for name in names:
        if name in props:
            return props[name]
    return {}


def property_value(props: dict, logical_name: str) -> str:
    names = PROPERTY_SOURCE_MAP.get(logical_name, [logical_name])
    return prop_text(first_prop(props, names)).strip()


def parse_where_clause(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise SystemExit(f"Invalid --where clause '{raw}'. Use the format \"Campo=Valor\".")
    field, value = raw.split("=", 1)
    field = field.strip()
    value = value.strip()
    if not field or not value:
        raise SystemExit(f"Invalid --where clause '{raw}'. Field and value are required.")
    return field, value


def parse_contains_any_clause(raw: str) -> tuple[str, list[str]]:
    if "=" not in raw:
        raise SystemExit(
            f"Invalid --contains-any clause '{raw}'. Use the format \"Campo=valor1|valor2|valor3\"."
        )
    field, value = raw.split("=", 1)
    field = field.strip()
    terms = [term.strip() for term in value.split("|") if term.strip()]
    if not field or not terms:
        raise SystemExit(
            f"Invalid --contains-any clause '{raw}'. Field and at least one term are required."
        )
    return field, terms


def ensure_filter_fields_exist(
    schema: dict,
    filters: list[tuple[str, str]],
    contains_any_filters: list[tuple[str, list[str]]],
) -> None:
    properties = schema.get("properties", {})
    missing = [field for field, _ in filters if field not in properties]
    missing.extend(field for field, _ in contains_any_filters if field not in properties)
    if missing:
        raise SystemExit(
            "The following filter fields do not exist in the Notion schema: "
            + ", ".join(sorted(missing))
        )


def page_matches_filters(
    props: dict,
    filters: list[tuple[str, str]],
    contains_any_filters: list[tuple[str, list[str]]],
) -> bool:
    for field, expected in filters:
        actual = prop_text(props.get(field, {})).strip()
        if normalize_text(actual) != normalize_text(expected):
            return False
    for field, expected_terms in contains_any_filters:
        actual = normalize_text(prop_text(props.get(field, {})).strip())
        normalized_terms = [normalize_text(term) for term in expected_terms]
        if not any(term and term in actual for term in normalized_terms):
            return False
    return True


def col_name(n: int) -> str:
    label = ""
    while n:
        n, rem = divmod(n - 1, 26)
        label = chr(65 + rem) + label
    return label


def inline_cell(ref: str, text: str, style: int = 0) -> str:
    safe = escape("" if text is None else str(text))
    return f'<c r="{ref}" t="inlineStr" s="{style}"><is><t xml:space="preserve">{safe}</t></is></c>'


def write_xlsx(path: Path, headers: list[str], rows: list[dict]) -> None:
    sheet_rows: list[str] = []
    header_cells = "".join(inline_cell(f"{col_name(i)}1", header, 1) for i, header in enumerate(headers, start=1))
    sheet_rows.append(f'<row r="1" ht="22" customHeight="1">{header_cells}</row>')

    for row_idx, row in enumerate(rows, start=2):
        cells = [
            inline_cell(f"{col_name(col_idx)}{row_idx}", row.get(header, ""), 0)
            for col_idx, header in enumerate(headers, start=1)
        ]
        sheet_rows.append(f'<row r="{row_idx}" ht="54" customHeight="1">{"".join(cells)}</row>')

    widths = [
        (1, 1, 8),
        (2, 2, 42),
        (3, 3, 22),
        (4, 4, 26),
        (5, 5, 22),
        (6, 6, 14),
        (7, 7, 14),
        (8, 8, 22),
        (9, 9, 55),
        (10, 10, 14),
        (11, 11, 100),
    ]
    cols_xml = "".join(
        f'<col min="{start}" max="{end}" width="{width}" customWidth="1"/>'
        for start, end, width in widths
    )
    last_ref = f"{col_name(len(headers))}{len(rows) + 1}"
    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>{cols_xml}</cols>
  <sheetData>{"".join(sheet_rows)}</sheetData>
  <autoFilter ref="A1:{last_ref}"/>
  <pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="10"/><name val="Arial"/></font>
    <font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="1">
    <border><left/><right/><top/><bottom/><diagonal/></border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="2">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

    workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Vagas" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>'''

    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a filtered Notion applications view to JSON, CSV, XLSX, and a report."
    )
    parser.add_argument(
        "--where",
        action="append",
        default=[],
        help='Exact-match filter in the format "Campo=Valor". Repeat for multiple filters (AND).',
    )
    parser.add_argument(
        "--contains-any",
        action="append",
        default=[],
        help='Contains-any filter in the format "Campo=valor1|valor2|valor3". Repeat for multiple filters (AND).',
    )
    parser.add_argument(
        "--output-base",
        required=True,
        help="Base path for the generated files, without extension. Example: outputs/minha_exportacao",
    )
    args = parser.parse_args()

    filters = [parse_where_clause(raw) for raw in args.where]
    contains_any_filters = [parse_contains_any_clause(raw) for raw in args.contains_any]
    if not filters and not contains_any_filters:
        raise SystemExit("At least one --where or --contains-any filter is required.")

    token, database_id = notion_config()
    schema = retrieve_database(token, database_id)
    ensure_filter_fields_exist(schema, filters, contains_any_filters)

    rows: list[dict] = []
    pages = query_all_database_pages(token, database_id)
    for page in pages:
        props = page.get("properties", {})
        if not page_matches_filters(props, filters, contains_any_filters):
            continue

        row = {header: property_value(props, header) for header in DEFAULT_COLUMNS}
        rows.append(row)

    rows.sort(key=lambda item: (int(item["ID"]) if str(item["ID"]).isdigit() else 10**9, item["Vaga"]))

    output_base = Path(args.output_base)
    output_base.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_base.with_suffix(".json")
    csv_path = output_base.with_suffix(".csv")
    xlsx_path = output_base.with_suffix(".xlsx")
    report_path = output_base.with_name(output_base.name + "_report").with_suffix(".json")

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DEFAULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    write_xlsx(xlsx_path, DEFAULT_COLUMNS, rows)

    report = {
        "matched_rows": len(rows),
        "filters": [{"field": field, "value": value} for field, value in filters],
        "contains_any_filters": [
            {"field": field, "terms": terms} for field, terms in contains_any_filters
        ],
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "xlsx_path": str(xlsx_path),
        "columns": DEFAULT_COLUMNS,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
