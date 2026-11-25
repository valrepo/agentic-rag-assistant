"""Build a minimal, valid multi-page PDF from plain text (standard library only).

Pages are separated by a form feed character (\\f) in the source text; an empty page gives a
blank page. Used for the sample knowledge PDF and for test PDFs.

Usage:
    uv run python scripts/make_sample_pdf.py SOURCE.txt OUTPUT.pdf
    uv run python scripts/make_sample_pdf.py --blank OUTPUT.pdf
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

PAGE_WIDTH, PAGE_HEIGHT = 612, 792
MARGIN_X, TOP_Y, LEADING, FONT_SIZE = 56, 736, 15, 11
WRAP_COLUMNS = 92
LINES_PER_PAGE = 44


def _escape(text: str) -> str:
    text = text.encode("latin-1", "replace").decode("latin-1")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _layout(page_text: str) -> list[str]:
    lines: list[str] = []
    for paragraph in page_text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, WRAP_COLUMNS) or [""])
    if len(lines) > LINES_PER_PAGE:
        raise ValueError("page text too long; split it with a form feed")
    return lines


def _content_stream(page_text: str) -> bytes:
    lines = _layout(page_text)
    if not any(line.strip() for line in lines):
        return b""
    parts = ["BT", f"/F1 {FONT_SIZE} Tf", f"{LEADING} TL", f"{MARGIN_X} {TOP_Y} Td"]
    for line in lines:
        parts.append(f"({_escape(line)}) Tj T*")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1")


def build_pdf(pages: list[str]) -> bytes:
    if not pages:
        pages = [""]
    objects: list[bytes] = []
    page_count = len(pages)
    first_page_obj = 4
    kids = " ".join(f"{first_page_obj + 2 * i} 0 R" for i in range(page_count))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for index, page_text in enumerate(pages):
        content_obj = first_page_obj + 2 * index + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj} 0 R >>"
            ).encode()
        )
        stream = _content_stream(page_text)
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return bytes(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", nargs="?", type=Path, help="UTF-8 text, pages split by \\f")
    parser.add_argument("output", type=Path)
    parser.add_argument("--blank", action="store_true", help="write one blank page")
    args = parser.parse_args()
    if args.blank:
        pages = [""]
    elif args.source is None:
        parser.error("SOURCE is required unless --blank is given")
    else:
        pages = args.source.read_text(encoding="utf-8").split("\f")
    args.output.write_bytes(build_pdf(pages))
    print(f"wrote {args.output} ({len(pages)} page(s))")


if __name__ == "__main__":
    main()
