import csv
import pathlib


keys = {
    "ldy-30-3p-lacen",
    "wtk-f-pw3c40",
    "flsn20",
    "ldy-30-2p-qitn",
    "jagar40",
    "bfp50-2p",
}

path = next(pathlib.Path(".").glob("036RPP*/**/normal-item20260825161522.csv"))
fields = [
    "商品番号",
    "商品名",
    "キャッチコピー",
    "PC用商品説明文",
    "スマートフォン用商品説明文",
    "PC用販売説明文",
    "商品画像パス1",
    "商品画像名（ALT）1",
    "商品画像パス2",
    "商品画像名（ALT）2",
    "商品画像パス3",
    "商品画像名（ALT）3",
    "通常購入販売価格",
]

seen = set()
with path.open(encoding="cp932", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = row.get("商品管理番号（商品URL）", "").strip()
        if key not in keys or key in seen:
            continue
        seen.add(key)
        print("---", key)
        for field in fields:
            value = row.get(field, "").strip()
            if value:
                value = value.replace("\r", " ").replace("\n", " ")
                print(field, ":", value[:900])
        if len(seen) == len(keys):
            break
