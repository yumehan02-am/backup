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
OUT = ROOT / "楽天コンテンツページ群" / "content_title_candidates_300_v2.csv"


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
    if has(blob, "ブラトップ", "カップ付き", "ブラタンク", "カップ付"):
        return "ブラトップ・カップ付きインナー"
    if has(blob, "ブラジャー", "ナイトブラ", "ソフトブラ"):
        return "ブラジャー・ソフトブラ"
    if has(blob, "汗取り", "汗ジミ", "脇汗"):
        return "汗取りインナー"
    if has(blob, "水着", "フィットネス水着"):
        return "レディース水着"
    if has(blob, "レギンス", "スパッツ", "レッグ"):
        return "レッグウェア"
    if has(blob, "シルク", "絹"):
        return "シルク・敏感肌"
    if has(blob, "腹巻", "温活", "冷え", "あったか"):
        return "温活インナー"
    if has(blob, "タオル", "ストール", "冷感"):
        return "冷感・季節雑貨"
    if has(blob, "ショーツ", "ふんどし"):
        return "ショーツ"
    return product["path"].split(":")[0] or "その他"


def features_for(product):
    blob = f"{product['path']} {product['name']} {product['explanation']}"
    checks = [
        ("綿100％", ["綿100", "綿 100", "コットン100"]),
        ("ノンワイヤー", ["ノンワイヤー"]),
        ("締め付けにくい", ["締め付けない", "締めつけない", "ラク", "楽"]),
        ("大きいサイズ", ["大きいサイズ", "3L", "4L", "5L"]),
        ("日本製", ["日本製"]),
        ("敏感肌", ["敏感肌", "肌にやさしい", "ガーゼ"]),
        ("汗対策", ["汗取り", "汗ジミ", "脇汗"]),
        ("冷え対策", ["冷え", "温活", "あったか", "腹巻"]),
        ("レース", ["レース"]),
        ("深履き", ["深履き", "深ばき"]),
        ("前開き", ["前開き", "フロントホック"]),
        ("体型カバー", ["体型カバー"]),
        ("フィットネス", ["フィットネス", "ヨガ", "スポーツ"]),
        ("シルク", ["シルク", "絹"]),
        ("ギフト", ["ギフト", "母の日", "敬老の日"]),
        ("夏向け", ["夏", "冷感", "メッシュ", "涼"]),
        ("冬向け", ["冬", "あったか", "発熱", "裏起毛"]),
    ]
    return [label for label, words in checks if any(w in blob for w in words)][:6]


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
    if "敏感肌" in features:
        return "敏感肌が気になる女性"
    return "大人女性"


def search_intent_for(category, features):
    if "尿漏れ" in category:
        return ["尿漏れ パンツ 選び方", "吸水ショーツ 比較", "軽失禁 下着"]
    if "ブラトップ" in category:
        return ["ブラトップ 選び方", "カップ付きインナー", "締め付けない インナー"]
    if "ブラジャー" in category:
        return ["ノンワイヤーブラ 選び方", "締め付けない ブラ", "大人 ブラジャー"]
    if "汗取り" in category:
        return ["汗取りインナー", "脇汗対策", "汗ジミ 防止"]
    if "水着" in category:
        return ["体型カバー水着", "フィットネス水着", "大人 水着"]
    if "温活" in category:
        return ["温活 インナー", "冷え対策 下着", "あったか インナー"]
    if "シルク" in category:
        return ["シルク インナー", "敏感肌 下着", "肌にやさしい インナー"]
    return ["レディース インナー", "大人女性 下着", "肌着 レディース"]


def music_style_for(category, features):
    if "介護" in category or "高吸水" in category or "男性" in category:
        return "senior_care"
    if "水着" in category or "冷感" in category or "夏向け" in features:
        return "season_bright"
    if "ギフト" in features:
        return "gift_warm"
    if "シルク" in category or "敏感肌" in features:
        return "beauty_clean"
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
    score = 48
    price = product["price"]
    if price:
        score += min(32, price / max(median, 1) * 13)
    if product["display"] in ("1", "Y", "y", "表示"):
        score += 8
    if product["sort_priority"]:
        score += min(12, product["sort_priority"] / 1000)
    blob = product["path"] + product["name"] + product["explanation"]
    if has(blob, "尿漏れ", "吸水", "汗取り", "敏感肌", "綿100", "シルク", "体型カバー"):
        score += 7
    if has(blob, "ギフト", "母の日", "敬老の日"):
        score += 5
    return round(score, 1)


def load_products():
    text, _ = read_text(CSV_PATH)
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
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
            "explanation": clean(row.get("explanation")),
        }
        p["category"] = category_for(p)
        p["features"] = features_for(p)
        p["audience"] = audience_for(p, p["category"], p["features"])
        rows.append(p)
    prices = [p["price"] for p in rows if p["price"]]
    median = statistics.median(prices) if prices else 3000
    for p in rows:
        p["score"] = product_score(p, median)
    return rows


CATEGORY_COPY = {
    "尿漏れパンツ 女性用 軽失禁": {
        "noun": "吸水ショーツ",
        "problems": ["咳・くしゃみのちょい漏れ", "外出中の不安", "パッドに頼りすぎたくない日", "旅行や長時間移動"],
        "benefits": ["ふつうの下着感", "目立ちにくさ", "毎日の安心感", "洗い替えしやすさ"],
    },
    "尿漏れパンツ 女性用 50cc": {
        "noun": "50cc吸水ショーツ",
        "problems": ["長時間の外出", "移動が多い日", "少し不安が強い日", "仕事中の不安"],
        "benefits": ["ほどよい備え", "パッド感の少なさ", "日常使い", "安心感"],
    },
    "尿漏れパンツ 高吸水・介護": {
        "noun": "高吸水パンツ",
        "problems": ["介護用の下着選び", "150cc以上の備え", "夜間や長時間", "ご家族の準備"],
        "benefits": ["しっかり吸水", "洗い替え", "本人も家族も使いやすい", "安心感"],
    },
    "尿漏れパンツ 男性用": {
        "noun": "男性用吸水パンツ",
        "problems": ["外出時の尿もれ", "シニア男性の下着選び", "長時間の移動", "見た目に配慮したい日"],
        "benefits": ["自然な見た目", "毎日の使いやすさ", "しっかり備える", "洗い替え"],
    },
    "ブラトップ・カップ付きインナー": {
        "noun": "ブラトップ",
        "problems": ["締め付けが苦手", "ブラを休みたい日", "家でも外でもラクに過ごしたい日", "夏のインナー選び"],
        "benefits": ["ラクな着心地", "一枚で整う", "肌あたり", "きれい見え"],
    },
    "ブラジャー・ソフトブラ": {
        "noun": "ノンワイヤーブラ",
        "problems": ["締め付けが苦手", "ワイヤーがつらい日", "夜やリラックスタイム", "大人のブラ選び"],
        "benefits": ["やさしいフィット感", "ラクなのに整う", "肌あたり", "毎日使いやすい"],
    },
    "汗取りインナー": {
        "noun": "汗取りインナー",
        "problems": ["脇汗", "汗ジミ", "通勤中の汗", "夏の汗対策"],
        "benefits": ["服に響きにくい", "清潔感", "さらっと快適", "汗ばむ季節の安心"],
    },
    "ショーツ": {
        "noun": "大人ショーツ",
        "problems": ["締め付け", "鼠径部の違和感", "毎日の下着選び", "肌あたり"],
        "benefits": ["ラクなはき心地", "自然なフィット", "素材感", "毎日使いやすい"],
    },
    "レディース水着": {
        "noun": "大人水着",
        "problems": ["体型カバー", "プールやジム", "久しぶりの水着選び", "露出を控えたい日"],
        "benefits": ["安心して動ける", "きれい見え", "着やすさ", "大人に似合う"],
    },
    "レッグウェア": {
        "noun": "レッグウェア",
        "problems": ["冷え", "足元のだるさ", "重ね着", "季節の変わり目"],
        "benefits": ["あたたかさ", "動きやすさ", "毎日使える", "すっきり見え"],
    },
    "温活インナー": {
        "noun": "温活インナー",
        "problems": ["お腹の冷え", "腰まわりの冷え", "冬の下着選び", "冷房対策"],
        "benefits": ["じんわり安心", "重ね着しやすい", "毎日使える", "心地よさ"],
    },
    "シルク・敏感肌": {
        "noun": "やさしい肌着",
        "problems": ["チクチク感", "敏感肌", "乾燥しやすい季節", "素材選び"],
        "benefits": ["なめらかな肌ざわり", "清潔感", "上質感", "直接肌にふれる安心"],
    },
    "冷感・季節雑貨": {
        "noun": "夏の冷感アイテム",
        "problems": ["暑さ対策", "日差し", "外出時の汗", "夏の持ち歩き"],
        "benefits": ["ひんやり感", "軽さ", "持ち歩きやすさ", "夏を快適に"],
    },
}


ANGLE_TEMPLATES = [
    ("悩み・用途", "{problem}が気になる日に｜{noun}でできるやさしい備え"),
    ("悩み・用途", "「少し不安」をそのままにしない｜{noun}の選び方"),
    ("悩み・用途", "{problem}対策、何から始める？{noun}の基本ガイド"),
    ("悩み・用途", "{problem}をラクにしたい人へ｜毎日使える{noun}"),
    ("失敗回避", "買ってから後悔しない{noun}選び｜見るべきポイントはここ"),
    ("失敗回避", "{noun}選びで迷う理由｜サイズ・素材・使う場面を整理"),
    ("失敗回避", "価格だけで選ばない{noun}｜長く使うためのチェックリスト"),
    ("比較・早見", "{noun}を比べるならどこを見る？{benefit}で選ぶ早見ガイド"),
    ("比較・早見", "{benefit}で選ぶ{noun}｜自分に合うタイプの見つけ方"),
    ("比較・早見", "{noun}の違いがわかる｜はじめての比較ポイント"),
    ("読み物", "大人の下着選びを見直す日｜{noun}と心地よく暮らすヒント"),
    ("読み物", "毎日の小さな不快感を減らす｜{noun}という選択肢"),
    ("読み物", "見た目も心地よさもあきらめない｜大人の{noun}案内"),
    ("季節", "季節の変わり目に見直したい{noun}｜快適に過ごす準備"),
    ("ギフト", "実用品だけど、ちゃんとやさしい｜贈り物に選ぶ{noun}"),
]


FEATURE_TEMPLATES = [
    ("特徴別", "{feature}にこだわる{noun}｜肌にふれるものを心地よく"),
    ("特徴別", "{feature}派のための{noun}選び｜毎日続けやすい理由"),
    ("特徴別", "{feature}と{benefit}で選ぶ、大人の{noun}"),
    ("特徴別", "{feature}が気になる人へ｜{noun}の見比べポイント"),
]


PRODUCT_TEMPLATES = [
    ("商品単体", "{short_name}を検討中の方へ｜向いている人と選び方"),
    ("商品単体", "{short_name}はどんな場面で使いやすい？購入前ガイド"),
    ("商品単体", "{short_name}の魅力を整理｜素材・形・使う日の選び方"),
]


CURATED_IDEAS = [
    ("尿漏れパンツ 女性用 軽失禁", "尿漏れパッドを毎日使う前に｜吸水ショーツという選択肢"),
    ("尿漏れパンツ 女性用 軽失禁", "外出予定をあきらめないための吸水ショーツ入門"),
    ("尿漏れパンツ 女性用 軽失禁", "見た目はふつう、でも少し安心｜大人女性の吸水ショーツ案内"),
    ("尿漏れパンツ 女性用 50cc", "電車移動や旅行の日に備える｜50cc吸水ショーツの選び方"),
    ("尿漏れパンツ 高吸水・介護", "介護用パンツを選ぶ家族へ｜吸水量と洗い替えの考え方"),
    ("尿漏れパンツ 男性用", "男性の尿もれ対策を自然に｜見た目に配慮した吸水パンツ選び"),
    ("ブラトップ・カップ付きインナー", "ブラを休みたい日のインナー選び｜カップ付きでラクに整える"),
    ("ブラトップ・カップ付きインナー", "アンダーゴムが苦手な人へ｜締め付けにくいブラトップ案内"),
    ("ブラジャー・ソフトブラ", "ワイヤーブラがつらい日に｜ノンワイヤーブラの上手な選び方"),
    ("ブラジャー・ソフトブラ", "夜も昼もラクに過ごしたい｜大人のソフトブラ入門"),
    ("汗取りインナー", "白シャツの日の脇汗対策｜汗取りインナーで清潔感を守る"),
    ("汗取りインナー", "汗ジミを気にせず出かけたい｜夏のインナー準備ガイド"),
    ("シルク・敏感肌", "チクチクしにくい肌着を探す人へ｜敏感肌のインナー選び"),
    ("温活インナー", "お腹の冷えを感じる日に｜温活インナーで毎日を整える"),
    ("レディース水着", "久しぶりの水着選びでも安心｜大人女性の体型カバー水着"),
    ("レディース水着", "ジム・プール通いを始める前に｜フィットネス水着の選び方"),
    ("ショーツ", "締め付けないショーツを探す人へ｜鼠径部をラクにする下着選び"),
    ("冷感・季節雑貨", "暑い日の外出を少し快適に｜冷感アイテムの選び方"),
]


def short_product_name(name):
    stop = [" レディース", " 女性", " 下着", " インナー", " 2色組", " 3色組", " 4色組", " 2枚組", " 3枚組"]
    value = name
    for s in stop:
        value = value.replace(s, " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:30]


def add(candidates, seen, products, title, page_type, category, reason, boost=0):
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) < 14 or title in seen:
        return
    seen.add(title)
    reps = sorted(products, key=lambda p: p["score"], reverse=True)[:5]
    avg_price = int(sum(p["price"] for p in reps) / len(reps)) if reps else 0
    features = sorted({f for p in reps for f in p["features"]})
    score = (sum(p["score"] for p in reps) / len(reps) if reps else 50) + boost + min(9, len(products) * 0.55)
    candidates.append({
        "priority_score": round(score, 1),
        "candidate_title": title,
        "page_type": page_type,
        "target_category": category,
        "representative_codes": " ".join(p["code"] for p in reps),
        "representative_products": " / ".join(p["name"][:34] for p in reps[:3]),
        "product_count": len(products),
        "avg_price": avg_price,
        "price_band": price_band(avg_price),
        "seo_keywords": " / ".join(search_intent_for(category, features)),
        "music_style": music_style_for(category, features),
        "video_focus": "タイトルの世界観、悩みの入口、役立つ選び方、商品ピックアップ",
        "banner_focus": "共感、比較早見、素材感、用途別誘導、CTA",
        "selection_note": reason,
    })


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    products = load_products()
    by_category = defaultdict(list)
    for p in products:
        by_category[p["category"]].append(p)

    candidates = []
    seen = set()

    for category, title in CURATED_IDEAS:
        rows = by_category.get(category, [])
        if rows:
            add(candidates, seen, rows, title, "企画・読み物", category, "悩みや利用シーンから入るキャッチーな企画候補", 15)

    for category, rows in sorted(by_category.items(), key=lambda x: sum(p["score"] for p in x[1]) / len(x[1]), reverse=True):
        copy = CATEGORY_COPY.get(category, {
            "noun": category,
            "problems": ["毎日の使い心地", "商品選びの迷い", "季節の準備", "買い替え"],
            "benefits": ["使いやすさ", "心地よさ", "選びやすさ", "安心感"],
        })
        for i, tmpl in enumerate(ANGLE_TEMPLATES):
            page_type, pattern = tmpl
            problem = copy["problems"][i % len(copy["problems"])]
            benefit = copy["benefits"][(i + 1) % len(copy["benefits"])]
            title = pattern.format(noun=copy["noun"], problem=problem, benefit=benefit)
            add(candidates, seen, rows, title, page_type, category, "カテゴリ特性に合わせて切り口を変えたSEO企画候補", 8)

        feature_hits = defaultdict(list)
        for p in rows:
            for feature in p["features"]:
                feature_hits[feature].append(p)
        for feature, hit_rows in sorted(feature_hits.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
            for j, (page_type, pattern) in enumerate(FEATURE_TEMPLATES):
                benefit = copy["benefits"][j % len(copy["benefits"])]
                title = pattern.format(feature=feature, noun=copy["noun"], benefit=benefit)
                add(candidates, seen, hit_rows, title, page_type, category, "商品の特徴語から作った比較・選び方候補", 6)

    for p in sorted(products, key=lambda x: x["score"], reverse=True)[:120]:
        category = p["category"]
        copy = CATEGORY_COPY.get(category, {"noun": category})
        for page_type, pattern in PRODUCT_TEMPLATES:
            add(
                candidates,
                seen,
                [p],
                pattern.format(short_name=short_product_name(p["name"]), noun=copy["noun"]),
                page_type,
                category,
                "単品を起点にしつつ、購入前の疑問解決に寄せた候補",
                3,
            )

    # Additional catchy seasonal and scenario angles.
    scenario_titles = [
        ("尿漏れパンツ 女性用 軽失禁", "朝の支度に一枚足す安心｜軽失禁が気になる日の下着選び"),
        ("尿漏れパンツ 女性用 軽失禁", "友人との外出を楽しみたい日に｜目立ちにくい吸水ショーツ案内"),
        ("尿漏れパンツ 女性用 50cc", "長めのお出かけ前に確認したい｜吸水量50ccの安心ライン"),
        ("尿漏れパンツ 高吸水・介護", "夜間の不安に備える下着選び｜高吸水タイプの見方"),
        ("ブラトップ・カップ付きインナー", "家ではラク、外ではきれいに｜大人のブラトップ活用術"),
        ("ブラジャー・ソフトブラ", "締め付けを我慢しないブラ選び｜ノンワイヤーで整える毎日"),
        ("汗取りインナー", "汗ばむ通勤の日に｜トップスをきれいに着るインナー対策"),
        ("汗取りインナー", "汗ジミが目立つ服を着る前に｜脇汗対策インナーの選び方"),
        ("シルク・敏感肌", "肌がゆらぎやすい季節に｜素材で選ぶやさしいインナー"),
        ("温活インナー", "冷房でお腹が冷える人へ｜薄手で使える温活インナー"),
        ("レディース水着", "露出を控えてすっきり見せたい｜体型カバー水着の選び方"),
        ("レッグウェア", "足元から整える冷え対策｜毎日使えるレッグウェア案内"),
        ("冷感・季節雑貨", "バッグに入れておきたい暑さ対策｜夏の冷感アイテム特集"),
        ("ショーツ", "毎日のショーツ、なんとなく選んでいませんか？心地よさの見直し方"),
    ]
    for category, title in scenario_titles:
        rows = by_category.get(category, [])
        if rows:
            add(candidates, seen, rows, title, "シーン訴求", category, "生活シーンから入る読み物型SEO候補", 11)

    candidates = sorted(candidates, key=lambda c: c["priority_score"], reverse=True)[:300]
    fields = [
        "no", "priority_score", "candidate_title", "page_type", "target_category",
        "representative_codes", "representative_products", "product_count", "avg_price",
        "price_band", "seo_keywords", "music_style", "video_focus", "banner_focus",
        "selection_note",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(candidates, 1):
            out = dict(row)
            out["no"] = i
            writer.writerow(out)
    print(f"products={len(products)} candidates={len(candidates)} output={OUT}")


if __name__ == "__main__":
    main()
