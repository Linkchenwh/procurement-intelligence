"""Review title/attribute packaging against preserved HTML; never change original observations."""
import argparse
import re

import pandas as pd

from scripts.collect_market import visible
from src.data_loader import ROOT


def main(input_path=None):
    source = ROOT / input_path if input_path else ROOT / "data/market/quotes_current.csv"
    if not source.exists() and input_path is None:
        source = ROOT / "data/market/quotes.csv"
    frame = pd.read_csv(source)
    frame["packaging_conflict"] = False
    frame["review_note"] = ""
    for index, row in frame.iterrows():
        page = (ROOT / row.evidence_file).read_text(encoding="utf-8")
        match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
        title = visible(match.group(1)) if match else row.product_name
        frame.loc[index, "product_name"] = title
        # Only the product's own h1, never related-product titles elsewhere in the page.
        patterns = {"paper_size": r"(?<![A-Za-z0-9])(A[0-9])(?![A-Za-z0-9])", "gsm": r"(\d+)\s*[gG]", "sheets_per_ream": r"(\d+)\s*张",
                    "reams_per_box": r"(\d+)\s*包(?:/箱|装)"}
        for column, pattern in patterns.items():
            found = re.search(pattern, title)
            if not found:
                continue
            value = found.group(1) if column == "paper_size" else int(found.group(1))
            existing = row[column]
            if pd.isna(existing) or existing == "unknown":
                frame.loc[index, column] = value
                frame.loc[index, "review_note"] += f"{column}来自本商品h1;"
            elif str(existing) != str(value) and (column == "paper_size" or float(existing) != float(value)):
                frame.loc[index, "packaging_conflict"] = True
                frame.loc[index, "review_note"] += f"{column}标题与属性冲突，待商家核实;"
        if frame.loc[index, "packaging_conflict"]:
            frame.loc[index, "data_status"] = "needs_review"
    target = ROOT / "data/market/quotes_reviewed.csv"
    frame.to_csv(target, index=False, encoding="utf-8-sig")
    print(frame[["quote_id", "product_name", "paper_size", "sheets_per_ream", "reams_per_box", "packaging_conflict", "review_note"]].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Project-relative quote CSV; defaults to latest collected round")
    main(parser.parse_args().input)
