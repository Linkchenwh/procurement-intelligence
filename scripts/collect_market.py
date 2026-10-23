"""Collect a small auditable snapshot of public A4 paper listings. No login or checkout."""
import argparse
import hashlib
import html
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://www.go-easy.com.cn/"


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, value):
        if not self.skip:
            self.parts.append(value)


def visible(markup):
    parser = VisibleText()
    parser.feed(markup)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def snapshot(session, url, path):
    response = session.get(url, timeout=(20, 60))
    response.raise_for_status()
    response.encoding = "utf-8"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Each run creates a timestamped directory, preserving previous evidence.
    path.write_bytes(response.content)
    text = visible(response.text)
    path.with_suffix(".txt").write_text(text, encoding="utf-8")
    return response.text, text, hashlib.sha256(response.content).hexdigest()


def main(direct=False):
    session = requests.Session()
    session.trust_env = not direct
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    evidence = ROOT / "data/market/evidence" / now.strftime("%Y%m%d_%H%M%S")
    markup, _, _ = snapshot(session, urljoin(BASE, "category-700-b0.html"), evidence / "category.html")
    links = re.findall(r'<a[^>]+href="(goods-\d+\.html)"[^>]*>(.*?)</a>', markup, flags=re.S)
    candidates = {}
    for link, inner in links:
        label = visible(inner)
        if "A4" in label.upper() and "80" in label and "复印纸" in label:
            candidates[link] = label
    observations = []
    for link, label in candidates.items():
        url = urljoin(BASE, link)
        page, text, digest = snapshot(session, url, evidence / link)
        start = text.find("当前位置")
        section = text[start:]
        # Main listed price precedes delivery selector; recommendations are excluded.
        header = section.split("配 送 至")[0]
        match = re.search(r"[￥¥]\s*([0-9]+(?:\.[0-9]+)?)\s*元", header)
        unit_match = re.search(r"数量\s*-\s*\+\s*(包|箱)", section)
        sku = re.search(r"商品货号：\s*([A-Za-z0-9_-]+)", section)
        attrs = section.split("商品属性")[-1].split("品牌授权书")[0]
        sheets = re.search(r"每包张数\s*(\d+)张", attrs)
        packs = re.search(r"每箱包数\s*(\d+)包", attrs)
        gsm = re.search(r"克重\s*(\d+)g", attrs)
        format_match = re.search(r"规格\s*(A\d)", attrs)
        price = float(match.group(1)) if match else None
        unit = unit_match.group(1) if unit_match else "unknown"
        brand = next((b for b in ["DOUBLE A", "一星蓝旗舰", "五星蓝旗舰", "红钢炮", "传美", "飞毛腿", "新高美", "得力", "柏之美", "红金雅", "Bessie"] if b.lower() in label.lower()), "unknown")
        observations.append({
            "quote_id": link.removesuffix(".html"), "brand": brand, "product_name": label,
            "sku": sku.group(1) if sku else link.removesuffix(".html"), "manufacturer": "unknown",
            "seller": "深圳市佰欣办公用品连锁有限公司", "contract_supplier": "unknown",
            "channel": "佰欣办公用品自营商城", "paper_size": format_match.group(1) if format_match else "unknown",
            "gsm": int(gsm.group(1)) if gsm else None,
            "sheets_per_ream": int(sheets.group(1)) if sheets else None,
            "reams_per_box": int(packs.group(1)) if packs else None,
            "price": price, "currency": "CNY", "quote_unit": {"包": "ream", "箱": "box"}.get(unit, "unknown"),
            "min_order_units": None, "max_order_units": None,
            "tax_status": "unknown", "shipping_cost": None,
            "shipping_terms": "页面有广东包邮说明，同时存在默认地区运费选择；需按目标地区和数量重新询价",
            "tax_terms": "待核对商家发票说明；可开发票不自动代表当前价格含税",
            "region": "待按目标地区核验", "lead_time_days": None,
            "collected_at": now.isoformat(), "url": url,
            "attributes": attrs[:600], "data_status": "observed_public_page" if match else "price_unresolved",
            "notes": "公开标价观察；数量阶梯价另行询价；无品牌质量评分；不保证库存/成交/合同条件",
            "evidence_file": str((evidence / link).relative_to(ROOT)).replace("\\", "/"),
            "evidence_sha256": digest, "source_domain": "market_quotes",
        })
        print(json.dumps(observations[-1], ensure_ascii=False), flush=True)
    target = ROOT / "data/market/quotes.csv"
    if target.exists():
        target = ROOT / "data/market" / ("quotes_" + now.strftime("%Y%m%d_%H%M%S") + ".csv")
    pd.DataFrame(observations).to_csv(target, index=False, encoding="utf-8-sig")
    # Preserve every dated observation file, and expose the newly collected round explicitly.
    pd.DataFrame(observations).to_csv(ROOT / "data/market/quotes_current.csv", index=False, encoding="utf-8-sig")
    print(f"Saved {len(observations)} observations: {target}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct", action="store_true")
    main(parser.parse_args().direct)
