from io import BytesIO

import pandas as pd
import pytest

from modules import ingestion


class FakeUpload:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getvalue(self):
        return self._data


def test_clean_text_collapses_blank_lines_and_trailing_spaces():
    assert ingestion.clean_text("a  \r\n\r\n\r\n\r\nb  ") == "a\n\nb"


def test_read_pasted_text_rejects_empty():
    with pytest.raises(ValueError):
        ingestion.read_pasted_text("   \n ")


def test_read_txt_upload():
    upload = FakeUpload("quote.txt", "Supplier A: cheese 250/kg".encode("utf-8"))
    assert "Supplier A" in ingestion.read_uploaded_file(upload)


def test_read_csv_upload():
    upload = FakeUpload("quotes.csv", b"supplier,price\nA,10\nB,12\n")
    text = ingestion.read_uploaded_file(upload)
    assert "supplier,price" in text
    assert "B,12" in text


def test_read_xlsx_upload():
    buffer = BytesIO()
    pd.DataFrame({"supplier": ["A", "B"], "price": [10, 12]}).to_excel(buffer, index=False)
    upload = FakeUpload("quotes.xlsx", buffer.getvalue())
    text = ingestion.read_uploaded_file(upload)
    assert "supplier,price" in text
    assert "A,10" in text


def test_unsupported_extension_rejected():
    with pytest.raises(ValueError):
        ingestion.read_uploaded_file(FakeUpload("photo.jpg", b"x"))


def test_split_messages_by_blank_line():
    text = "Supplier A: oil 20 tins\n1,850 each\n\nSupplier B: oil 20 tins\n1,720 each"
    parts = ingestion.split_messages(text, ingestion.SPLIT_BLANK_LINE)
    assert parts == ["Supplier A: oil 20 tins\n1,850 each", "Supplier B: oil 20 tins\n1,720 each"]


def test_split_messages_each_line():
    text = "Supplier A: oil 1,850\nSupplier B: oil 1,720\n\nSupplier C: oil 1,790"
    parts = ingestion.split_messages(text, ingestion.SPLIT_EACH_LINE)
    assert parts == ["Supplier A: oil 1,850", "Supplier B: oil 1,720", "Supplier C: oil 1,790"]


def test_split_messages_empty_text_returns_empty_list():
    assert ingestion.split_messages("  \n \n", ingestion.SPLIT_BLANK_LINE) == []
    assert ingestion.split_messages(None) == []
