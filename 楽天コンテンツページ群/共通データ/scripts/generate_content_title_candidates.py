import csv
import html
import io
import pathlib
import re
import statistics
import sys
from collections import defaultdict


ROOT = pathlib.Path(r"C:\Users\i58400am\Desktop\newapp")
CSV_PATH = ROOT / "Yahoo!" / "data202608061154.csv"
OUT = ROOT / "楽天コンテンツページ群" / "content_title_candidates_300.csv"


def read_text(path):
    data = path.read_bytes()
    for enc in ("utf-8-sig", "cp932", "shift_jis", "utf-8"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return data.decode("cp932", "replace"), "cp932-replace"


def clean(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def to_int(value):
    value = re.sub(r"[^\d]", "", value or "")
    return int(value) if value else 0


def valid_code(code):
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,40}", code or ""))


def has(text, *words):
    return any(w in text for w in words)


def category_for(product):
    blob = f"{product['path']} {product['name']} {product['explanation']}"
    if has(blob, "尿漏れ", "失禁", "吸水"):
        if has(blob, "男性", "紳士"):
            return "尿漏れパンツ 男性用"
        if has(blob, "150cc", "300cc", "介護"):
            return "尿漏れパンツ 高吸水・介護"
        if has(blob, "50cc"):
            return "尿漏れパンツ 女性用 50cc"
        return "尿漏れパンツ 女性用 軽失禁"
    if has(blob, "ブラトップ", "カップ付き", "ブラタンク"):
        return "ブラトップ・カップ付きインナー"
    if has(blob, "ブラジャー", "ナイトブラ", "ソフトブラ"):
        return "ブラジャー・ソフトブラ"
    if has(blob, "汗取り", "汗ジミ", "脇汗"):
        return "汗取りインナー"
    if has(blob, "ショーツ", "ふんどし"):
        return "ショーツ"
    if has(blob, "水着", "フィットネス水着"):
        return "レディース水着"
    if has(blob, "レギンス", "スパッツ", "レッグ"):
        return "レッグウェア"
    if has(blob, "シルク", "絹"):
        return "シルク・敏感肌"
    if has(blob, "腹巻", "温活", "冷え"):
        return "温活インナー"
    if has(blob, "タオル", "ストール", "冷感"):
        return "冷感・季節雑貨"
    return product["path"].split(":")[0] or "その他"


def features_for(product):
    blob = f"{product['path']} {product['name']} {product['explanation']}"
    features = []
    checks = [
        ("綿100％", ["綿100", "綿 100", "コットン100"]),
        ("ノンワイヤー", ["ノンワイヤー"]),
        ("締め付けにくい", ["締め付けない", "締めつけない", "楽", "ラク"]),
        ("大きいサイズ", ["大きいサイズ", "3L", "4L", "5L"]),
        ("日本製", ["日本製"]),
        ("肌にやさしい", ["敏感肌", "肌にやさしい", "ガーゼ"]),
        ("汗対策", ["汗取り", "汗ジミ", "脇汗"]),
        ("冷え対策", ["冷え", "温活", "あったか", "腹巻"]),
        ("レース", ["レース"]),
        ("深履き", ["深履き", "深ばき"]),
        ("前開き", ["前開き", "フロントホック"]),
        ("体型カバー", ["体型カバー"]),
        ("フィットネス", ["フィットネス", "ヨガ", "スポーツ"]),
        ("ギフト", ["ギフト", "母の日", "敬老の日"]),
    ]
    for label, words in checks:
        if any(w in blob for w in words):
            features.append(label)
    return features[:5]


def audience_for(product, category, features):
    blob = f"{product['path']} {product['name']} {product['explanation']}"
    if "男性" in category:
        return "男性・シニア"
    if has(blob, "60代", "70代", "シニア", "介護"):
        return "50代・60代・70代"
    if "水着" in category:
        return "大人女性"
    if "大きいサイズ" in features:
        return "大きいサイズを探す女性"
    if "敏感肌" in blob or "肌にやさしい" in features:
        return "敏感肌が気になる女性"
    return "大人女性"


def search_intent_for(category, features):
    if "尿漏れ" in category:
        return ["尿漏れ パンツ 選び方", "吸水ショーツ 比較", "軽失禁 下着 女性"]
    if "ブラトップ" in category:
        return ["ブラトップ 選び方", "カップ付きインナー レディース", "締め付けない インナー"]
    if "ブラジャー" in category:
        return ["ノンワイヤーブラ 選び方", "締め付けない ブラ", "大人 ブラジャー"]
    if "汗取り" in category:
        return ["汗取りインナー レディース", "脇汗対策 インナー", "汗ジミ 防止"]
    if "水着" in category:
        return ["体型カバー水着 レディース", "フィットネス水着 選び方", "大人 水着"]
    if "レッグ" in category:
        return ["レギンス レディース 選び方", "スパッツ レディース", "冷え対策 レッグウェア"]
    if "温活" in category:
        return ["温活 インナー", "冷え対策 下着", "あったか インナー レディース"]
    if "シルク" in category:
        return ["シルク インナー", "敏感肌 下着", "肌にやさしい インナー"]
    return ["レディース インナー 選び方", "大人女性 下着", "肌着 レディース"]


def music_style_for(category, features):
    if "介護" in category or "高吸水" in category or "男性" in category:
        return "senior_care"
    if "シルク" in category or "肌にやさしい" in features:
        return "beauty_clean"
    if "ギフト" in features:
        return "gift_warm"
    if "水着" in category or "冷感" in category:
        return "season_bright"
    return "apparel_soft"


def price_band(price):
    if price >= 6000:
        return "高単価"
    if price >= 3000:
        return "中単価"
    if price:
        return "低単価"
    return "不明"


def product_score(product, median):
    score = 50
    price = product["price"]
    if price:
        score += min(30, price / max(median, 1) * 12)
    if product["display"] in ("1", "Y", "y", "表示"):
        score += 8
    if product["sort_priority"]:
        score += min(12, product["sort_priority"] / 1000)
    blob = product["path"] + product["name"] + product["explanation"]
    if has(blob, "ギフト", "母の日", "敬老の日"):
        score += 4
    if has(blob, "尿漏れ", "吸水", "汗取り", "敏感肌", "綿100", "シルク"):
        score += 6
    return round(score, 1)


def add_candidate(candidates, seen, product_rows, title, page_type, category, reason, score_boost=0):
    title = re.sub(r"\s+", " ", title).strip()
    if not title or title in seen:
        return
    seen.add(title)
    products = sorted(product_rows, key=lambda p: p["score"], reverse=True)
    reps = products[:5]
    avg_price = int(sum(p["price"] for p in reps) / len(reps)) if reps else 0
    features = sorted({f for p in reps for f in p["features"]})
    keywords = search_intent_for(category, features)
    base_score = sum(p["score"] for p in reps) / len(reps) if reps else 50
    candidates.append({
        "priority_score": round(base_score + score_boost + min(10, len(product_rows) * 0.7), 1),
        "candidate_title": title,
        "page_type": page_type,
        "target_category": category,
        "representative_codes": " ".join(p["code"] for p in reps),
        "representative_products": " / ".join(p["name"][:32] for p in reps[:3]),
        "product_count": len(product_rows),
        "avg_price": avg_price,
        "price_band": price_band(avg_price),
        "seo_keywords": " / ".join(keywords),
        "music_style": music_style_for(category, features),
        "video_focus": "ページタイトル、悩み、選び方、素材感、商品ピックアップを短く見せる",
        "banner_focus": "悩み共感、早見表、素材感、商品誘導、CTA",
        "selection_note": reason,
    })


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    text, _enc = read_text(CSV_PATH)
    reader = csv.DictReader(io.StringIO(text))
    raw_products = []
    for row in reader:
        code = (row.get("code") or "").strip()
        name = clean(row.get("name"))
        if not valid_code(code) or not name:
            continue
        p = {
            "path": clean(row.get("path")),
            "name": name,
            "code": code,
            "price": to_int(row.get("sale-price") or row.get("price")),
            "display": (row.get("display") or "").strip(),
            "sort_priority": to_int(row.get("sort_priority")),
            "headline": clean(row.get("headline")),
            "caption": clean(row.get("caption")),
            "abstract": clean(row.get("abstract")),
            "explanation": clean(row.get("explanation")),
        }
        p["category"] = category_for(p)
        p["features"] = features_for(p)
        p["audience"] = audience_for(p, p["category"], p["features"])
        raw_products.append(p)

    prices = [p["price"] for p in raw_products if p["price"]]
    median = statistics.median(prices) if prices else 3000
    for p in raw_products:
        p["score"] = product_score(p, median)

    by_category = defaultdict(list)
    for p in raw_products:
        by_category[p["category"]].append(p)

    candidates = []
    seen = set()

    category_templates = [
        "{cat}の選び方｜{aud}が失敗しにくいポイント",
        "{cat}はどう選ぶ？素材・形・使う場面で比較",
        "{aud}に合う{cat}とは｜毎日使いやすい選び方",
        "{cat}おすすめの選び方｜価格だけで迷わないために",
        "{cat}を初めて選ぶ方へ｜買う前に見たいチェックポイント",
    ]
    for cat, rows in sorted(by_category.items(), key=lambda item: sum(p["score"] for p in item[1]) / len(item[1]), reverse=True):
        top = sorted(rows, key=lambda p: p["score"], reverse=True)[:8]
        aud = top[0]["audience"]
        for tmpl in category_templates:
            add_candidate(candidates, seen, rows, tmpl.format(cat=cat, aud=aud), "商品群", cat, "カテゴリ内の商品数と価格帯をもとにした商品群ページ候補", 6)

    product_templates = [
        "{feature}で選ぶ{simple_cat}｜{aud}に合う一枚を探す",
        "{name_key}はどんな人に向く？特徴と選び方",
        "{simple_cat}選びで迷ったら｜{feature}を重視した比較",
        "{aud}のための{simple_cat}｜{feature}と使いやすさで選ぶ",
        "{name_key}を検討する前に見たい選び方ガイド",
    ]
    for p in sorted(raw_products, key=lambda x: x["score"], reverse=True):
        simple_cat = p["category"].split(" ")[0]
        feature = p["features"][0] if p["features"] else "使いやすさ"
        name_key = p["name"][:26]
        for tmpl in product_templates[:3]:
            add_candidate(
                candidates,
                seen,
                [p],
                tmpl.format(feature=feature, simple_cat=simple_cat, aud=p["audience"], name_key=name_key),
                "商品単体",
                p["category"],
                "単価・表示状態・商品特徴をもとにした単品寄りページ候補",
                2,
            )

    trouble_groups = [
        ("外出中の尿漏れが気になる女性へ｜吸水ショーツの選び方", "尿漏れパンツ 女性用 軽失禁", ["尿漏れ", "吸水"]),
        ("咳やくしゃみのちょい漏れ対策｜普段使いしやすい下着選び", "尿漏れパンツ 女性用 軽失禁", ["尿漏れ", "30cc"]),
        ("長時間の外出に備える吸水ショーツ｜50cc前後の選び方", "尿漏れパンツ 女性用 50cc", ["50cc"]),
        ("介護用の高吸水パンツを選ぶ前に｜150cc以上の目安", "尿漏れパンツ 高吸水・介護", ["150cc", "300cc"]),
        ("汗ジミが気になる季節のインナー選び｜脇汗対策を自然に", "汗取りインナー", ["汗取り", "汗ジミ"]),
        ("敏感肌にやさしいインナー選び｜綿・ガーゼ・シルクを比較", "シルク・敏感肌", ["敏感肌", "シルク", "ガーゼ"]),
        ("締め付けにくいブラを探す方へ｜ノンワイヤーの選び方", "ブラジャー・ソフトブラ", ["ノンワイヤー"]),
        ("大人のブラトップ選び｜楽さときれい見えを両立するには", "ブラトップ・カップ付きインナー", ["ブラトップ", "カップ付き"]),
        ("冷えが気になる日の温活インナー｜お腹まわりを心地よく", "温活インナー", ["温活", "冷え"]),
        ("体型カバー水着の選び方｜大人女性が安心して着られるポイント", "レディース水着", ["水着", "体型カバー"]),
    ]
    for title, cat, words in trouble_groups:
        rows = [p for p in raw_products if p["category"] == cat or any(w in p["name"] + p["path"] + p["explanation"] for w in words)]
        if rows:
            add_candidate(candidates, seen, rows, title, "悩み・用途", cat, "検索意図が明確な悩み起点のSEO候補", 12)

    seasonal_templates = [
        ("母の日に贈りたい実用インナー｜肌ざわりで選ぶギフト", ["ギフト", "母の日", "綿100", "シルク"], "ギフト"),
        ("敬老の日に選ぶやさしい肌着｜毎日使える実用品ギフト", ["敬老の日", "シニア", "ガーゼ", "綿100"], "ギフト"),
        ("夏の汗対策インナー特集｜涼しく過ごす大人の肌着選び", ["汗取り", "冷感", "夏"], "季節"),
        ("冬の冷え対策インナー特集｜お腹と腰まわりを心地よく", ["温活", "冷え", "あったか"], "季節"),
        ("旅行前に準備したい安心インナー｜外出を楽しむ下着選び", ["尿漏れ", "旅行", "吸水"], "季節"),
    ]
    for title, words, page_type in seasonal_templates:
        rows = [p for p in raw_products if any(w in p["name"] + p["path"] + p["explanation"] for w in words)]
        if rows:
            add_candidate(candidates, seen, rows, title, page_type, rows[0]["category"], "季節・イベント需要を狙うSEO候補", 8)

    # Fill to 300 with feature/category combinations.
    feature_labels = [
        "綿100％", "ノンワイヤー", "締め付けにくい", "大きいサイズ", "日本製", "肌にやさしい",
        "汗対策", "冷え対策", "レース", "深履き", "前開き", "体型カバー", "フィットネス"
    ]
    combo_templates = [
        "{feature}の{cat}特集｜毎日使いやすい選び方",
        "{feature}で探す{cat}｜大人女性に合うポイント",
        "{cat}を{feature}で比較｜はじめての選び方ガイド",
        "{feature}重視の{cat}｜見た目と心地よさで選ぶ",
    ]
    for feature in feature_labels:
        for cat, rows in by_category.items():
            hit = [p for p in rows if feature in p["features"]]
            if not hit:
                continue
            for tmpl in combo_templates:
                add_candidate(candidates, seen, hit, tmpl.format(feature=feature, cat=cat), "特徴別", cat, "特徴語とカテゴリを掛け合わせたSEO候補", 5)
                if len(candidates) >= 340:
                    break
            if len(candidates) >= 340:
                break
        if len(candidates) >= 340:
            break

    candidates = sorted(candidates, key=lambda c: c["priority_score"], reverse=True)[:300]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "no",
        "priority_score",
        "candidate_title",
        "page_type",
        "target_category",
        "representative_codes",
        "representative_products",
        "product_count",
        "avg_price",
        "price_band",
        "seo_keywords",
        "music_style",
        "video_focus",
        "banner_focus",
        "selection_note",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(candidates, 1):
            row = dict(row)
            row["no"] = i
            writer.writerow(row)
    print(f"products={len(raw_products)} candidates={len(candidates)} output={OUT}")


if __name__ == "__main__":
    main()
