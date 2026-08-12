#!/usr/bin/env python3
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

REQUIRED_PARTS = [
    "[Content_Types].xml",
    "word/document.xml",
    "word/styles.xml",
]


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"File not found: {path}"]
    if path.suffix.lower() != ".docx":
        errors.append("File extension is not .docx")

    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            for part in REQUIRED_PARTS:
                if part not in names:
                    errors.append(f"Missing DOCX part: {part}")

            for xml_part in [name for name in names if name.endswith(".xml")]:
                try:
                    root = ElementTree.fromstring(zf.read(xml_part))
                    if xml_part == "word/document.xml":
                        for section_type in root.findall(".//w:sectPr/w:type", NS):
                            value = section_type.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
                            if value == "A4":
                                errors.append("Invalid Word section type: w:type=\"A4\". Use page size, not section type.")
                except Exception as exc:
                    errors.append(f"Invalid XML in {xml_part}: {exc}")

            if "word/theme/theme1.xml" not in names:
                errors.append("Missing Arial theme part: word/theme/theme1.xml")
            else:
                theme_text = zf.read("word/theme/theme1.xml").decode("utf-8", errors="replace")
                if 'typeface="Arial"' not in theme_text:
                    errors.append("Arial theme is not applied")
    except zipfile.BadZipFile:
        errors.append("File is not a valid zip/docx package")

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        outputs = Path("outputs")
        candidates = sorted(outputs.glob("*.docx"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidates:
            print("Usage: validate_docx.py <file.docx>", file=sys.stderr)
            return 2
        path = candidates[0]
    else:
        path = Path(sys.argv[1])
    errors = validate(path)
    if errors:
        print("DOCX validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"DOCX validation passed: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
