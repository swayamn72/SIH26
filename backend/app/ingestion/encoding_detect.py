from pathlib import Path

import chardet
from charset_normalizer import from_path


def detect_encoding(file_path: str | Path) -> str:
    path = Path(file_path)
    raw = path.read_bytes()

    chardet_result = chardet.detect(raw)
    chardet_encoding = chardet_result.get("encoding", "utf-8") or "utf-8"

    better_result = from_path(str(path)).best()
    if better_result:
        return better_result.encoding

    return chardet_encoding if chardet_encoding.lower() != "ascii" else "utf-8"
