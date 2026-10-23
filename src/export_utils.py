"""Plain CSV exports; keep spreadsheet formula injection out of string cells."""
import pandas as pd


def csv_bytes(frame):
    data = frame.copy()
    for column in data:
        if pd.api.types.is_object_dtype(data[column]) or pd.api.types.is_string_dtype(data[column]):
            data[column] = data[column].map(
                lambda value: "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value)
    return data.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")
