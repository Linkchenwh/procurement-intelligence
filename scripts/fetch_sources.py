"""Download public sources without credentials; preserve originals and provenance."""
import argparse
import hashlib
import json
import re
import zipfile
from urllib.parse import urlsplit, urlunsplit
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"


def fetch(session, url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(f"EXISTS {target.relative_to(ROOT)}", flush=True)
        return
    response = session.get(url, timeout=(20, 180))
    response.raise_for_status()
    content = response.content
    if target.suffix == ".csv" and b"<html" in content[:1000].lower():
        raise ValueError("CSV download returned HTML")
    target.write_bytes(content)
    record = {
        "url": url, "final_url": urlunsplit(urlsplit(response.url)._replace(query="")),
        "acquired_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "filename": str(target.relative_to(ROOT)), "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    target.with_suffix(target.suffix + ".source.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)


def kaggle(session):
    base = "https://www.kaggle.com/api/v1/datasets/"
    slug = "shahriarkabir/procurement-kpi-analysis-dataset"
    fetch(session, base + "view/" + slug, RAW / "kaggle/metadata.json")
    meta = json.loads((RAW / "kaggle/metadata.json").read_text(encoding="utf-8"))
    print(json.dumps(meta, ensure_ascii=False)[:20000], flush=True)
    archive = RAW / "kaggle/dataset.zip"
    fetch(session, base + "download/" + slug, archive)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if info.filename.endswith(".csv"):
                target = RAW / "kaggle" / Path(info.filename).name
                if not target.exists():
                    target.write_bytes(z.read(info))
                print(f"CSV {target.name}: {target.stat().st_size} bytes", flush=True)


def california(session):
    page = RAW / "california/source_page.html"
    fetch(session, "https://data.ca.gov/dataset/purchase-order-data", page)
    html = page.read_text(encoding="utf-8")
    # Read actual public download links rather than guess retired CKAN resource IDs.
    urls = sorted(set(re.findall(r'https://publish\.data\.ca\.gov[^\s"<>]+', html)))
    print("Resource links: " + json.dumps(urls), flush=True)
    for url in urls:
        clean = url.replace("&amp;", "&")
        if ".csv" in clean.lower() and "/resource/" in clean:
            fetch(session, clean, RAW / "california/purchase_orders.csv")
        elif ".pdf" in clean.lower() and "/resource/" in clean:
            fetch(session, clean, RAW / "california/data_dictionary.pdf")
        elif ".json" in clean.lower() and "/resource/" not in clean:
            fetch(session, clean, RAW / "california/metadata.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", choices=["kaggle", "california"])
    parser.add_argument("--direct", action="store_true", help="Ignore a broken local proxy configuration")
    args = parser.parse_args()
    session = requests.Session()
    session.trust_env = not args.direct
    {"kaggle": kaggle, "california": california}[args.source](session)
