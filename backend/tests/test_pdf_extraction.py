import pytest
from app.ingestion.file_router import classify_file


class TestFileRouter:
    def test_csv_classified(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("a,b,c\n1,2,3\n")
        assert classify_file(str(f)) == "csv"

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = classify_file(str(f))
        assert result is None or result == "unknown"

    def test_empty_file_rejected(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("")
        assert classify_file(str(f)) is None
