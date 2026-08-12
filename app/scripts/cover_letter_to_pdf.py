#!/usr/bin/env python3
"""Convert cover letter text (Markdown or plain) to PDF via WeasyPrint."""

import sys, os, argparse
from weasyprint import HTML

HEADER_CSS = """
@page { margin: 2.5cm 2cm; }
body {
  font-family: 'DejaVu Sans', sans-serif;
  font-size: 11pt;
  line-height: 1.5;
  color: #1a1a1a;
}
.signature { margin-top: 2em; }
"""

DEFAULT_TITLE = "Carta de Apresentação"


def markdown_to_html(text: str, title: str = DEFAULT_TITLE) -> str:
    lines = text.strip().split("\n")
    html_parts = [f"<html><head><meta charset='utf-8'><title>{title}</title><style>{HEADER_CSS}</style></head><body>"]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_parts.append("<br>")
        elif stripped.startswith("# "):
            html_parts.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            html_parts.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            html_parts.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            html_parts.append(f"<li>{stripped[2:]}</li>")
        elif stripped == "---":
            html_parts.append("<hr>")
        else:
            html_parts.append(f"<p>{stripped}</p>")

    html_parts.append("</body></html>")
    return "\n".join(html_parts)


def main():
    parser = argparse.ArgumentParser(description="Convert cover letter text to PDF")
    parser.add_argument("input", nargs="?", help="Input file (text/markdown). Omit for stdin.")
    parser.add_argument("-o", "--output", default="outputs/carta_apresentacao.pdf",
                        help="Output PDF path")
    parser.add_argument("-t", "--title", default=DEFAULT_TITLE,
                        help="PDF title")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    html = markdown_to_html(text, args.title)

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    HTML(string=html).write_pdf(args.output)
    print(f"PDF generated: {args.output}")


if __name__ == "__main__":
    main()
