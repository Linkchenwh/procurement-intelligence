"""Bounded CSV/XLSX input with identifiers retained as strings."""
import csv
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def read_table(file, filename=None, *, max_bytes=20_000_000):
    name = filename or getattr(file, "name", str(file))
    suffix = Path(name).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise ValueError("仅支持 CSV 或 XLSX 文件")
    if hasattr(file, "getvalue"):
        content = file.getvalue()
    elif hasattr(file, "read"):
        content = file.read(max_bytes + 1)
    else:
        path = Path(file)
        if path.stat().st_size > max_bytes:
            raise ValueError("上传文件不能超过20MB")
        content = path.read_bytes()
    if not content or len(content) > max_bytes:
        raise ValueError("文件为空或超过20MB")
    try:
        if suffix == ".csv":
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = content.decode("gb18030")
            header = next(csv.reader(StringIO(text)))
            if len(header) != len(set(header)) or any(not x.strip() for x in header):
                raise ValueError("CSV 表头重复或为空")
            frame = pd.read_csv(StringIO(text), dtype="string", nrows=100001)
        else:
            # Only read cell values; never execute spreadsheet macros or formulas.
            frame = pd.read_excel(BytesIO(content), dtype="string", nrows=100001)
    except Exception as error:
        raise ValueError(f"文件无法读取，请检查格式、编码和表头: {error}") from error
    if frame.empty or len(frame) > 100000:
        raise ValueError("文件无数据行或超过10万行；政府大文件请使用本地处理脚本")
    return frame


def performance_path():
    paths = sorted((ROOT / "data/raw/kaggle").rglob("*.csv"))
    if len(paths) > 1:
        raise ValueError("Kaggle 目录有多个 CSV，请保留一个明确的分析输入或使用上传功能")
    return paths[0] if paths else None
