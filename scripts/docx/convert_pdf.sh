#!/usr/bin/env sh
set -eu

docx_path=""
output_dir="outputs"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --docx-path)
      docx_path="$2"
      shift 2
      ;;
    --output-dir)
      output_dir="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$docx_path" ]; then
  echo "Usage: sh scripts/docx/convert_pdf.sh --docx-path outputs/<arquivo>.docx [--output-dir outputs]" >&2
  exit 2
fi

if [ ! -f "$docx_path" ]; then
  echo "DOCX not found: $docx_path" >&2
  exit 1
fi

PATH="$HOME/.local/bin:$PATH"

if command -v libreoffice >/dev/null 2>&1; then
  soffice_cmd="libreoffice"
elif command -v soffice >/dev/null 2>&1; then
  soffice_cmd="soffice"
elif [ -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
  soffice_cmd="/Applications/LibreOffice.app/Contents/MacOS/soffice"
else
  echo "LibreOffice/soffice not found. Install LibreOffice to convert DOCX to PDF." >&2
  echo "macOS: brew install --cask libreoffice" >&2
  exit 1
fi

mkdir -p "$output_dir"
"$soffice_cmd" --headless --convert-to pdf --outdir "$output_dir" "$docx_path"
