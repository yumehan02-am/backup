import csv
import html
import io
import pathlib
import re
import statistics
import sys
from collections import defaultdict, deque


ROOT = pathlib.Path(r"C:\Users\i58400am\Desktop\newapp")
CSV_PATH = ROOT / "Yahoo!" / "data202608061154.csv"
OUT = ROOT / "楽天コンテンツページ群" / "生成用データ_実務版" / "samples" / "content_proposals_300_v1.csv"


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


def has(text, *words):
    return any(word in text for word in words)


def valid_code(code):
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,40}", code or ""))


def category_for(product):
    blob = f"{product['path']} {product['name']} {product['explanation']}"
    if has(blob, "尿漏れ", "失禁", "吸水"):
        if has(blob, "男性", "紳士"):
            return "男性用吸水パンツ"
        if has(blob, "150cc", "300cc", "介護"):
            return "高吸水・介護パンツ"
        if has(blob, "50cc"):
            return "50cc吸水ショーツ"
        return "軽失禁・吸水ショーツ"
    if has(blob, "補正", "補整", "ガードル", "ボディスーツ", "ボディブリファー"):
        return "補正下着"
    if has(blob, "ブラトップ", "カップ付き", "ブラタンク", "カップ付"):
        return "ブラトップ・カップ付きインナー"
    if has(blob, "ブラジャー", "ナイトブラ", "ソフトブラ"):
        return "ノンワイヤーブラ・ソフトブラ"
    if has(blob, "汗取り", "汗ジミ", "脇汗"):
        return "汗取りインナー"
    if has(blob, "水着", "フィットネス水着"):
        return "レディース水着"
    if has(blob, "レギンス", "スパッツ", "レッグ"):
        return "レッグウェア"
    if has(blob, "シルク", "絹", "ガーゼ", "敏感肌"):
        return "シルク・敏感肌インナー"
    if has(blob, "腹巻", "温活", "冷え", "あったか"):
        return "温活インナー"
    if has(blob, "冷感", "タオル", "ストール"):
        return "冷感・季節雑貨"
    if has(blob, "ショーツ", "ふんどし"):
        return "ショーツ"
    if has(blob, "インナー", "肌着", "トップス", "ボトム"):
        return "インナー"
    return "その他"


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
        ("深履き", ["深履き", "深ばき"]),
        ("前開き", ["前開き", "フロントホック"]),
        ("体型カバー", ["体型カバー"]),
        ("シルク", ["シルク", "絹"]),
    ]
    return [label for label, words in checks if any(word in blob for word in words)]


KITS = {
    "軽失禁・吸水ショーツ": {
        "noun": "吸水ショーツ",
        "need": "外出や日常の少量の尿もれが気になる",
        "seo": "吸水ショーツ 選び方 / 軽失禁 下着 / 尿もれ パッド 代わり",
        "music": "apparel_soft",
        "titles": [
            ("本音コラム", "尿もれ対策を“こっそり”から“ふつうの準備”へ｜吸水ショーツの新しい考え方"),
            ("選び方ガイド", "20cc・30ccはどのくらい？軽失禁ショーツを生活シーンで選ぶ"),
            ("短い物語", "くしゃみ一回で予定が不安になる朝の話｜吸水ショーツ会議、はじまる"),
        ],
    },
    "50cc吸水ショーツ": {
        "noun": "50cc吸水ショーツ",
        "need": "30ccでは少し不安な日や長時間外出に備えたい",
        "seo": "吸水ショーツ 50cc / 尿漏れパンツ 女性用 / 長時間 尿もれ 対策",
        "music": "apparel_soft",
        "titles": [
            ("選び方ガイド", "30ccでは少し不安な日に｜50cc吸水ショーツのちょうどいい備え方"),
            ("知識コラム", "吸水量の数字だけで選ばない｜50ccショーツを生活時間で見比べる"),
            ("シーンコラム", "電車、映画、カフェ。席を立ちにくい日の下着選び"),
        ],
    },
    "高吸水・介護パンツ": {
        "noun": "高吸水パンツ",
        "need": "介護や夜間の備えを、本人の気持ちも含めて考えたい",
        "seo": "介護用パンツ 洗える / 高吸水パンツ / 尿漏れパンツ 150cc",
        "music": "senior_care",
        "titles": [
            ("家族向けコラム", "介護用パンツを選ぶ家族へ｜吸水量より先に考えたい“使う人の気持ち”"),
            ("実用ガイド", "150cc以上はどんな時に必要？高吸水パンツの選び方と洗い替え計画"),
            ("本音コラム", "紙パンツだけじゃない選択肢｜洗える高吸水パンツという考え方"),
        ],
    },
    "補正下着": {
        "noun": "補正下着",
        "need": "服のラインを整えたいが、苦しいものや誇大表現は避けたい",
        "seo": "補正下着 選び方 / ガードル 苦しくない / 服のライン 下着",
        "music": "urban_column",
        "titles": [
            ("本音コラム", "着るだけで痩せる、はありえない｜それでも補正下着を使う意味"),
            ("選び方ガイド", "苦しい補正下着は続かない｜毎日使いやすいガードルの見方"),
            ("婦人誌コラム", "お腹のお肉はどこにも行かない。でも服のラインは整えられる"),
        ],
    },
    "ブラトップ・カップ付きインナー": {
        "noun": "ブラトップ",
        "need": "締め付けを減らしつつ、日常で使える一枚を選びたい",
        "seo": "ブラトップ 選び方 / カップ付きインナー / 締め付けない インナー",
        "music": "apparel_soft",
        "titles": [
            ("婦人誌コラム", "ブラを休みたい日は悪い日じゃない｜大人のブラトップ活用術"),
            ("選び方ガイド", "アンダーゴムが苦手な人へ｜締め付けにくいカップ付きインナーの見方"),
            ("短い物語", "朝のブラ会議、満場一致でブラトップの日"),
        ],
    },
    "汗取りインナー": {
        "noun": "汗取りインナー",
        "need": "白シャツや通勤時の汗ジミを目立たせたくない",
        "seo": "汗取りインナー / 脇汗対策 / 汗ジミ 防止",
        "music": "beauty_clean",
        "titles": [
            ("知識コラム", "汗ジミが目立つ色・目立ちにくい色｜白シャツの日のインナー作戦"),
            ("選び方ガイド", "脇汗対策は薄さだけで選ばない｜汗取りインナーの見るべきポイント"),
            ("シーンコラム", "満員電車を降りたあと、ジャケットを脱げる私でいたい"),
        ],
    },
    "レッグウェア": {
        "noun": "レッグウェア",
        "need": "冷え、静電気、重ね着を考えながら足元を整えたい",
        "seo": "レギンス 選び方 / 静電気 素材 組み合わせ / 冷え対策 レッグウェア",
        "music": "season_bright",
        "titles": [
            ("知識コラム", "静電気が起きやすい素材、起きにくい素材｜冬インナーの組み合わせ講座"),
            ("選び方ガイド", "レギンスとスパッツ、何が違う？大人の重ね着で見る選び方"),
            ("季節コラム", "季節の変わり目に一枚足すなら｜薄手レッグウェアの使いどころ"),
        ],
    },
    "シルク・敏感肌インナー": {
        "noun": "肌にやさしいインナー",
        "need": "チクチクや乾燥が気になり、素材から肌着を選びたい",
        "seo": "敏感肌 インナー / シルク インナー / 肌にやさしい 下着",
        "music": "beauty_clean",
        "titles": [
            ("知識コラム", "綿100％がいつも正解とは限らない？敏感肌インナーの素材選び"),
            ("比較ガイド", "シルク・綿・ガーゼを比べる｜肌に直接ふれる下着の選び方"),
            ("婦人誌コラム", "肌がゆらぐ日は、服より先に肌着を見直す"),
        ],
    },
    "温活インナー": {
        "noun": "温活インナー",
        "need": "冷えや冷房対策を、厚着以外の方法でも考えたい",
        "seo": "温活 インナー / 腹巻 レディース / 冷え対策 下着",
        "music": "beauty_clean",
        "titles": [
            ("知識コラム", "冷え対策は厚着だけじゃない｜肌に近い一枚を見直す温活インナー術"),
            ("本音コラム", "腹巻きはダサい？見えにくく使える温活アイテムの選び方"),
            ("季節コラム", "冷房でお腹が冷える人へ｜夏にも使える薄手温活インナー"),
        ],
    },
}


GENERIC_PATTERNS = [
    ("婦人誌コラム", "{noun}を買う前に、自分の一日を思い出してみる"),
    ("知識コラム", "{noun}選びの前に知りたい、素材と季節の小さな相性"),
    ("比較ガイド", "買ってから後悔しない{noun}｜サイズ・素材・使う場面のチェック表"),
    ("本音コラム", "売り文句だけではわからない{noun}の本当の選びどころ"),
    ("短い物語", "クローゼットの中で始まる{noun}作戦会議"),
    ("季節コラム", "季節の変わり目に見直したい{noun}｜汗・冷え・肌ざわりの話"),
]


def load_products():
    text, _ = read_text(CSV_PATH)
    products = []
    for row in csv.DictReader(io.StringIO(text)):
        code = (row.get("code") or "").strip()
        name = clean(row.get("name"))
        if not valid_code(code) or not name:
            continue
        product = {
            "code": code,
            "name": name,
            "path": clean(row.get("path")),
            "price": to_int(row.get("sale-price") or row.get("price")),
            "display": (row.get("display") or "").strip(),
            "sort_priority": to_int(row.get("sort_priority")),
            "explanation": clean(row.get("explanation")),
        }
        product["category"] = category_for(product)
        product["features"] = features_for(product)
        products.append(product)

    prices = [p["price"] for p in products if p["price"]]
    median = statistics.median(prices) if prices else 3000
    for product in products:
        score = 50
        if product["price"]:
            score += min(25, product["price"] / max(median, 1) * 10)
        if product["display"] in ("1", "Y", "y", "表示"):
            score += 8
        if product["sort_priority"]:
            score += min(10, product["sort_priority"] / 1000)
        score += min(8, len(product["features"]) * 2)
        product["score"] = round(score, 1)
    return products


def story_for(style, title):
    if "物語" in style:
        return "起:日常の小さな違和感 承:クローゼットや外出前の迷い 転:選び方の視点を変える 結:自分に合う一枚へ"
    if "本音" in style:
        return "起:よくある売り文句への違和感 承:できることを整理 転:できないことも正直に伝える 結:納得して選ぶ"
    if "知識" in style:
        return "起:身近な疑問 承:素材や構造の基本 転:組み合わせや失敗例 結:生活シーン別の選び方"
    if "比較" in style or "選び方" in style:
        return "起:選び方で迷う場面 承:比較軸を整理 転:用途別に見る 結:商品ID候補へ自然につなぐ"
    return "起:読者の悩み 承:暮らしの中の原因 転:選び方のヒント 結:おすすめ商品へ自然につなぐ"


def headings_for(style, noun):
    if "本音" in style:
        return f"売り文句を一度ほどく / {noun}でできること / 期待しすぎないための見方 / 続けやすい選び方"
    if "知識" in style:
        return f"まず知っておきたい基本 / 素材と形の違い / 失敗しやすい組み合わせ / 生活シーン別の選び方"
    if "物語" in style:
        return f"朝の小さな事件 / クローゼットの作戦会議 / 選ぶ基準が見えてくる / 明日の自分に合う一枚"
    if "比較" in style or "選び方" in style:
        return f"何で迷いやすいか / 比較するべき3つの軸 / 用途別の選び方 / おすすめ商品を見る前に"
    return f"なぜ気になるのか / 暮らしの中で見直すポイント / 選び方のヒント / 関連商品へのつなぎ"


def video_copy(style, kit):
    if "本音" in style:
        return f"{kit['need'].split('、')[0]} / きれいごと抜きで / 選ぶ前に知りたいこと"
    if "知識" in style:
        return "知ると選びやすい / 素材と形の話 / このコラムのポイント"
    if "物語" in style:
        return "朝の小さな違和感 / あるあるで読む / 自分に合う選び方"
    if "比較" in style or "選び方" in style:
        return "迷う理由を整理 / 3つの基準で見る / 選ぶ前に知りたいこと"
    return "気になる悩みから / このコラムのポイント / 続きは本文で"


def banner_ideas(style):
    if "知識" in style:
        return "ポイント整理バナー / 素材相性バナー / 選び方チェックバナー"
    if "本音" in style:
        return "本音の一言バナー / できること・できないこと整理 / まとめバナー"
    if "物語" in style:
        return "導入シーンバナー / 作戦会議風バナー / まとめバナー"
    return "悩み共感バナー / 比較早見バナー / まとめバナー"


def row_for(no, title, style, category, kit, products):
    reps = sorted(products, key=lambda p: p["score"], reverse=True)[:5]
    avg_price = int(sum(p["price"] for p in reps) / len(reps)) if reps else 0
    return {
        "proposal_no": no,
        "priority_score": round((sum(p["score"] for p in reps) / len(reps) if reps else 50) + min(10, len(products) * 0.5), 1),
        "candidate_title": title,
        "content_style": style,
        "target_category": category,
        "reader_need": kit["need"],
        "column_angle": "商品特性から広げた読み物。売り込みより役立つ内容を優先",
        "story_structure": story_for(style, title),
        "section_headings": headings_for(style, kit["noun"]),
        "seo_keywords": kit["seo"],
        "video_display_copy": video_copy(style, kit),
        "video_role": "タイトルバナー直下の動く目次CM。商品説明ではなく本文を読みたくさせる",
        "banner_ideas": banner_ideas(style),
        "recommended_product_ids_ai": " ".join(p["code"] for p in reps),
        "recommended_product_ids_final": "",
        "product_id_status": "AI仮選定",
        "music_style": kit["music"],
        "production_status": "企画中",
        "notes": f"平均価格目安:{avg_price}円 商品点数:{len(products)}",
    }


def diversify(rows, limit):
    buckets = defaultdict(deque)
    for row in sorted(rows, key=lambda r: r["priority_score"], reverse=True):
        buckets[(row["target_category"], row["content_style"])].append(row)
    keys = deque(sorted(buckets, key=lambda k: buckets[k][0]["priority_score"], reverse=True))
    result = []
    last_category = None
    while keys and len(result) < limit:
        key = keys.popleft()
        bucket = buckets[key]
        if not bucket:
            continue
        row = bucket.popleft()
        if row["target_category"] == last_category and len(keys) > 1:
            bucket.appendleft(row)
            keys.append(key)
            continue
        result.append(row)
        last_category = row["target_category"]
        if bucket:
            keys.append(key)
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    products = load_products()
    grouped = defaultdict(list)
    for product in products:
        if product["category"] in KITS:
            grouped[product["category"]].append(product)

    rows = []
    seen = set()
    no = 1
    for category, kit in KITS.items():
        items = grouped.get(category, [])
        if not items:
            continue
        candidates = list(kit["titles"])
        candidates.extend((style, pattern.format(noun=kit["noun"])) for style, pattern in GENERIC_PATTERNS)
        features = sorted({feature for item in items for feature in item["features"]})
        for feature in features:
            candidates.append(("特徴コラム", f"{feature}だけで選んで大丈夫？{kit['noun']}の見落としがちなポイント"))
        for style, title in candidates:
            if title in seen:
                continue
            seen.add(title)
            rows.append(row_for(no, title, style, category, kit, items))
            no += 1

    while len(rows) < 330:
        for category, kit in KITS.items():
            items = grouped.get(category, [])
            if not items:
                continue
            idx = len([r for r in rows if r["target_category"] == category])
            style = ["婦人誌コラム", "知識コラム", "本音コラム", "比較ガイド", "季節コラム"][idx % 5]
            title = f"{kit['noun']}で変わる、いつもの一日｜{['朝','外出','季節','素材','着心地'][idx % 5]}から考える選び方"
            if title in seen:
                title = f"{title} {idx + 1}"
            seen.add(title)
            rows.append(row_for(no, title, style, category, kit, items))
            no += 1
            if len(rows) >= 330:
                break

    rows = diversify(rows, 300)
    fields = [
        "proposal_no",
        "priority_score",
        "candidate_title",
        "content_style",
        "target_category",
        "reader_need",
        "column_angle",
        "story_structure",
        "section_headings",
        "seo_keywords",
        "video_display_copy",
        "video_role",
        "banner_ideas",
        "recommended_product_ids_ai",
        "recommended_product_ids_final",
        "product_id_status",
        "music_style",
        "production_status",
        "notes",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            row = dict(row)
            row["proposal_no"] = i
            writer.writerow(row)
    print(f"products={len(products)} proposals={len(rows)} output={OUT}")


if __name__ == "__main__":
    main()
