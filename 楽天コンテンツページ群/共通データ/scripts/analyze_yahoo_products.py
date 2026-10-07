import csv
import io
import pathlib
import re
import statistics
import sys
from collections import Counter, defaultdict


CSV_PATH = pathlib.Path(r"C:\Users\i58400am\Desktop\newapp\Yahoo!\data202608061154.csv")


def read_text(path):
    data = path.read_bytes()
    for enc in ("utf-8-sig", "cp932", "shift_jis", "utf-8"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return data.decode("cp932", "replace"), "cp932-replace"


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def valid_code(code):
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,40}", code or ""))


def to_int(value):
    value = re.sub(r"[^\d]", "", value or "")
    return int(value) if value else 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    text, enc = read_text(CSV_PATH)
    reader = csv.DictReader(io.StringIO(text))
    products = []
    for row in reader:
        code = (row.get("code") or "").strip()
        name = clean(row.get("name"))
        if not valid_code(code) or not name:
            continue
        products.append({
            "path": clean(row.get("path")),
            "name": name,
            "code": code,
            "price": to_int(row.get("sale-price") or row.get("price")),
            "display": (row.get("display") or "").strip(),
            "sort_priority": to_int(row.get("sort_priority")),
            "headline": clean(row.get("headline")),
            "caption": clean(row.get("caption")),
            "abstract": clean(row.get("abstract")),
            "explanation": clean(row.get("explanation"))[:500],
        })

    print("encoding:", enc)
    print("valid_products:", len(products))
    print("categories:")
    for path, count in Counter(p["path"] for p in products).most_common(30):
        print(f"  {count:4d} {path}")
    prices = [p["price"] for p in products if p["price"]]
    if prices:
        print("price_min:", min(prices))
        print("price_median:", int(statistics.median(prices)))
        print("price_max:", max(prices))
    print("sample:")
    by_cat = defaultdict(list)
    for p in products:
        by_cat[p["path"]].append(p)
    for cat, rows in list(by_cat.items())[:10]:
        print("---", cat)
        for p in rows[:3]:
            print(p["code"], p["price"], p["name"][:80])


if __name__ == "__main__":
    main()
