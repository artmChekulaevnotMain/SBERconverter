"""Парсеры файлов разных форматов."""
import csv
import io
import json
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class ParsedData:
    """Результат парсинга файла."""
    def __init__(self, columns: list[str], sample_rows: list[dict], dtypes: dict, separator: str = ","):
        self.columns = columns
        self.sample_rows = sample_rows
        self.dtypes = dtypes
        self.separator = separator

    def to_dict(self) -> dict:
        return {
            "columns": self.columns,
            "sample_rows": self.sample_rows,
            "dtypes": self.dtypes,
            "separator": self.separator,
        }


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str = "") -> ParsedData:
        pass

    def _infer_dtypes(self, df: pd.DataFrame) -> dict:
        result = {}
        for col in df.columns:
            sample = df[col].dropna()
            if sample.empty:
                result[col] = "string"
                continue
            val = sample.iloc[0]
            if isinstance(val, (int, float)):
                result[col] = "number"
            elif isinstance(val, bool):
                result[col] = "boolean"
            else:
                result[col] = "string"
        return result


class CsvParser(BaseParser):
    def parse(self, file_bytes: bytes, filename: str = "") -> ParsedData:
        text = file_bytes.decode("utf-8-sig")
        # Определяем разделитель
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(text[:2000])
            sep = dialect.delimiter
        except csv.Error:
            sep = ";"
        df = pd.read_csv(io.StringIO(text), sep=sep, nrows=100)
        columns = list(df.columns)
        sample_rows = df.head(3).fillna("").to_dict(orient="records")
        dtypes = self._infer_dtypes(df)
        return ParsedData(columns=columns, sample_rows=sample_rows, dtypes=dtypes, separator=sep)


class XlsxParser(BaseParser):
    def parse(self, file_bytes: bytes, filename: str = "") -> ParsedData:
        df = pd.read_excel(io.BytesIO(file_bytes), nrows=100)
        columns = list(df.columns)
        sample_rows = df.head(3).fillna("").to_dict(orient="records")
        dtypes = self._infer_dtypes(df)
        return ParsedData(columns=columns, sample_rows=sample_rows, dtypes=dtypes)


class JsonParser(BaseParser):
    def parse(self, file_bytes: bytes, filename: str = "") -> ParsedData:
        data = json.loads(file_bytes.decode("utf-8-sig"))
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list) or len(data) == 0:
            return ParsedData(columns=[], sample_rows=[], dtypes={})
        df = pd.DataFrame(data[:100])
        columns = list(df.columns)
        sample_rows = df.head(3).fillna("").to_dict(orient="records")
        dtypes = self._infer_dtypes(df)
        return ParsedData(columns=columns, sample_rows=sample_rows, dtypes=dtypes)


class XmlParser(BaseParser):
    def parse(self, file_bytes: bytes, filename: str = "") -> ParsedData:
        root = ET.fromstring(file_bytes.decode("utf-8-sig"))
        rows = []
        for child in root:
            row = {}
            for elem in child:
                row[elem.tag] = elem.text or ""
            if child.attrib:
                for k, v in child.attrib.items():
                    row[k] = v
            if row:
                rows.append(row)
        if not rows:
            return ParsedData(columns=[], sample_rows=[], dtypes={})
        df = pd.DataFrame(rows[:100])
        columns = list(df.columns)
        sample_rows = df.head(3).fillna("").to_dict(orient="records")
        dtypes = self._infer_dtypes(df)
        return ParsedData(columns=columns, sample_rows=sample_rows, dtypes=dtypes)


class PdfParser(BaseParser):
    def parse(self, file_bytes: bytes, filename: str = "") -> ParsedData:
        import pdfplumber
        rows = []
        columns = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[:5]:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    if not columns and table[0]:
                        columns = [str(c) for c in table[0]]
                    for row in table[1:]:
                        if row:
                            rows.append(dict(zip(columns, [str(v) if v else "" for v in row])))
        if not rows:
            return ParsedData(columns=[], sample_rows=[], dtypes={})
        df = pd.DataFrame(rows[:100])
        columns = list(df.columns)
        sample_rows = df.head(3).fillna("").to_dict(orient="records")
        dtypes = self._infer_dtypes(df)
        return ParsedData(columns=columns, sample_rows=sample_rows, dtypes=dtypes)


class DocxParser(BaseParser):
    def parse(self, file_bytes: bytes, filename: str = "") -> ParsedData:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        rows = []
        columns = []
        for table in doc.tables:
            header = [cell.text.strip() for cell in table.rows[0].cells]
            if not columns:
                columns = header
            for row in table.rows[1:]:
                vals = [cell.text.strip() for cell in row.cells]
                rows.append(dict(zip(columns, vals)))
        if not rows:
            return ParsedData(columns=[], sample_rows=[], dtypes={})
        df = pd.DataFrame(rows[:100])
        columns = list(df.columns)
        sample_rows = df.head(3).fillna("").to_dict(orient="records")
        dtypes = self._infer_dtypes(df)
        return ParsedData(columns=columns, sample_rows=sample_rows, dtypes=dtypes)


class HtmlParser(BaseParser):
    def parse(self, file_bytes: bytes, filename: str = "") -> ParsedData:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(file_bytes.decode("utf-8-sig"), "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return ParsedData(columns=[], sample_rows=[], dtypes={})
        dfs = pd.read_html(io.StringIO(str(tables[0])))
        if not dfs:
            return ParsedData(columns=[], sample_rows=[], dtypes={})
        df = dfs[0].head(100)
        columns = list(df.columns)
        sample_rows = df.head(3).fillna("").to_dict(orient="records")
        dtypes = self._infer_dtypes(df)
        return ParsedData(columns=columns, sample_rows=sample_rows, dtypes=dtypes)


class PngParser(BaseParser):
    def parse(self, file_bytes: bytes, filename: str = "") -> ParsedData:
        from PIL import Image
        import pytesseract
        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img, lang="rus+eng")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) < 2:
            return ParsedData(columns=[], sample_rows=[], dtypes={})
        # Пробуем разделить по табуляции или |
        sep = "\t" if "\t" in lines[0] else "|" if "|" in lines[0] else ";"
        columns = [c.strip() for c in lines[0].split(sep)]
        rows = []
        for line in lines[1:4]:
            vals = [v.strip() for v in line.split(sep)]
            rows.append(dict(zip(columns, vals)))
        dtypes = {c: "string" for c in columns}
        return ParsedData(columns=columns, sample_rows=rows, dtypes=dtypes)


PARSERS = {
    ".csv": CsvParser,
    ".xls": XlsxParser,
    ".xlsx": XlsxParser,
    ".json": JsonParser,
    ".xml": XmlParser,
    ".pdf": PdfParser,
    ".docx": DocxParser,
    ".html": HtmlParser,
    ".htm": HtmlParser,
    ".png": PngParser,
    ".jpg": PngParser,
    ".jpeg": PngParser,
}


def get_parser(file_extension: str) -> BaseParser:
    ext = file_extension.lower()
    parser_class = PARSERS.get(ext)
    if not parser_class:
        raise ValueError(f"Формат {ext} не поддерживается. Доступные: {list(PARSERS.keys())}")
    return parser_class()


SUPPORTED_FORMATS = list(PARSERS.keys())
