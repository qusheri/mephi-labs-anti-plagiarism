from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile


SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}


def read_source_text(path: str | Path) -> str:
    source_path = Path(path)
    if source_path.suffix.lower() == ".zip":
        return _read_zip_sources(source_path)
    return _read_text_file(source_path)


def _read_text_file(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "cp1251", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _read_zip_sources(path: Path) -> str:
    parts: list[str] = []
    with ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            suffix = Path(name).suffix.lower()
            if suffix not in SOURCE_EXTENSIONS:
                continue
            with archive.open(name) as file:
                data = file.read()
            text = data.decode("utf-8", errors="replace")
            parts.append(f"// FILE: {name}\n{text}")
    return "\n\n".join(parts)
