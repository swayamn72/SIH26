import pytest
from app.ingestion.csv_extractor import extract_csv_rows


class TestCSVExtraction:
    def test_basic_csv(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("Date,Narration,Debit,Credit,Balance\n01/01/2024,Salary,0,50000,50000\n02/01/2024,ATM,2000,0,48000\n", encoding="utf-8")
        data, header = extract_csv_rows(str(f))
        assert header is not None
        assert len(data) == 2
        assert "Date" in header

    def test_csv_with_preamble(self, tmp_path):
        f = tmp_path / "with_preamble.csv"
        f.write_text("Account Statement\nPeriod: Jan 2024\nDate,Narration,Amount,Balance\n01/01/2024,Salary,50000,50000\n", encoding="utf-8")
        data, header = extract_csv_rows(str(f))
        assert header is not None
        assert any("Date" in h or "date" in h.lower() for h in header)
