import csv
import pathlib
import collections
import re


base = pathlib.Path(".")
matches = list(base.glob("036RPP*/**/normal-item20260825161522.csv"))
if not matches:
    raise SystemExit("CSV not found")

path = matches[0]
rows = None
fieldnames = None
used_encoding = None
for encoding in ("utf-8-sig", "cp932", "utf-8"):
    try:
        with path.open(encoding=encoding, newline="") as f:
            reader = csv.reader(f)
            fieldnames = next(reader)
            rows = list(reader)
        used_encoding = encoding
        break
    except UnicodeDecodeError:
        continue

if rows is None:
    raise SystemExit("Could not decode CSV")

index = {name: i for i, name in enumerate(fieldnames)}


def cell(row, name):
    i = index.get(name)
    if i is None or i >= len(row):
        return ""
    return row[i].strip()


product_key = "商品管理番号（商品URL）"
product_name = "商品名"
genre_id = "ジャンルID"
catch_copy = "キャッチコピー"
pc_desc = "PC用商品説明文"
sp_desc = "スマートフォン用商品説明文"
sales_desc = "PC用販売説明文"
image1 = "商品画像パス1"
price = "通常購入販売価格"

products = collections.OrderedDict()
genres = collections.Counter()
words = collections.Counter()
filled = collections.Counter()

for row in rows:
    key = cell(row, product_key)
    if key and key not in products:
        products[key] = row
    genres[cell(row, genre_id)] += 1
    for name in (image1, pc_desc, sp_desc, sales_desc, catch_copy, price):
        if cell(row, name):
            filled[name] += 1
    name = cell(row, product_name)
    for token in re.findall(r"[A-Za-z0-9０-９一-龠ぁ-んァ-ンー]{2,}", name):
        if len(token) >= 2:
            words[token] += 1

print("FILE", path)
print("ENCODING", used_encoding)
print("ROWS", len(rows))
print("COLUMNS", len(fieldnames))
print("UNIQUE_PRODUCTS", len(products))
print("GENRES_TOP10")
for name, count in genres.most_common(10):
    print(count, name)
print("FILLED")
for name in (image1, pc_desc, sp_desc, sales_desc, catch_copy, price):
    print(name, filled[name])
print("WORD_TOP40")
for word, count in words.most_common(40):
    print(count, word)
print("SAMPLES")
for n, (key, row) in enumerate(products.items(), 1):
    if n > 30:
        break
    print(n, key, "|", cell(row, product_name)[:160], "|", cell(row, genre_id), "|", cell(row, price))
