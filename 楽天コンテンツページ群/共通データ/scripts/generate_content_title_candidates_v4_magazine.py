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
OUT = ROOT / "楽天コンテンツページ群" / "content_title_candidates_300_v4_magazine.csv"


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
    if has(blob, "ガードル", "補正", "補整", "ボディスーツ", "ボディブリファー"):
        return "補正下着"
    if has(blob, "シルク", "絹"):
        return "シルク・敏感肌"
    if has(blob, "腹巻", "温活", "冷え", "あったか"):
        return "温活インナー"
    if has(blob, "タオル", "ストール", "冷感"):
        return "冷感・季節雑貨"
    if has(blob, "シリコンパッド", "フェムケア", "美容健康", "雑貨"):
        return "美容健康雑貨"
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
        ("レース", ["レース"]),
        ("深履き", ["深履き", "深ばき"]),
        ("前開き", ["前開き", "フロントホック"]),
        ("体型カバー", ["体型カバー"]),
        ("フィットネス", ["フィットネス", "ヨガ", "スポーツ"]),
        ("シルク", ["シルク", "絹"]),
        ("夏向け", ["夏", "冷感", "メッシュ", "涼"]),
        ("冬向け", ["冬", "あったか", "発熱", "裏起毛"]),
    ]
    return [label for label, words in checks if any(w in blob for w in words)][:6]


def search_intent_for(category):
    table = {
        "尿漏れパンツ 女性用 軽失禁": ["吸水ショーツ 選び方", "軽失禁 下着", "尿漏れ パッド 代わり"],
        "尿漏れパンツ 女性用 50cc": ["吸水ショーツ 50cc", "尿漏れパンツ 女性用", "長時間 尿漏れ 対策"],
        "尿漏れパンツ 高吸水・介護": ["介護用パンツ 洗える", "高吸水パンツ", "尿漏れパンツ 150cc"],
        "尿漏れパンツ 男性用": ["男性 尿漏れパンツ", "吸水パンツ メンズ", "シニア 下着 男性"],
        "ブラトップ・カップ付きインナー": ["ブラトップ 選び方", "カップ付きインナー", "締め付けない インナー"],
        "ブラジャー・ソフトブラ": ["ノンワイヤーブラ 選び方", "締め付けない ブラ", "ソフトブラ"],
        "汗取りインナー": ["汗取りインナー", "脇汗対策", "汗ジミ 防止"],
        "レディース水着": ["体型カバー水着", "大人 水着", "フィットネス水着"],
        "レッグウェア": ["レギンス 選び方", "冷え対策 レッグウェア", "スパッツ レディース"],
        "補正下着": ["補正下着 選び方", "ガードル 苦しくない", "服のライン 下着"],
        "シルク・敏感肌": ["敏感肌 インナー", "シルク インナー", "肌にやさしい 下着"],
        "温活インナー": ["温活 インナー", "腹巻 レディース", "冷え対策 下着"],
        "冷感・季節雑貨": ["冷感タオル", "暑さ対策 グッズ", "夏 外出 対策"],
        "ショーツ": ["締め付けない ショーツ", "深履き ショーツ", "ふんどしショーツ"],
        "インナー": ["レディース インナー", "肌着 選び方", "大人女性 下着"],
    }
    return table.get(category, ["レディース インナー", "下着 選び方", "肌着 レディース"])


def music_style_for(category):
    if "水着" in category or "冷感" in category:
        return "fashion_magazine_bright"
    if "補正" in category:
        return "urban_editorial_pop"
    if "尿漏れ" in category or "介護" in category:
        return "clean_lifestyle_warm"
    if "シルク" in category or "温活" in category:
        return "soft_beauty_column"
    return "apparel_magazine_soft"


def price_band(price):
    if price >= 6000:
        return "高単価"
    if price >= 3000:
        return "中単価"
    if price:
        return "低単価"
    return "不明"


def load_products():
    text, _ = read_text(CSV_PATH)
    products = []
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
        products.append(p)
    prices = [p["price"] for p in products if p["price"]]
    median = statistics.median(prices) if prices else 3000
    for p in products:
        score = 45
        if p["price"]:
            score += min(30, p["price"] / max(median, 1) * 12)
        if p["display"] in ("1", "Y", "y", "表示"):
            score += 8
        if p["sort_priority"]:
            score += min(10, p["sort_priority"] / 1000)
        if p["features"]:
            score += min(8, len(p["features"]) * 2)
        p["score"] = round(score, 1)
    return products


KITS = {
    "尿漏れパンツ 女性用 軽失禁": {
        "noun": "吸水ショーツ",
        "world": "朝の支度、外出、旅行、パッドに頼りすぎない選択",
        "bridge": "軽失禁向けの吸水量や見た目の自然さから商品を紹介",
        "hooks": ["え、これ下着で備える話？", "パッドだけが正解じゃない", "ふつうに見える安心感"],
        "angles": [
            ("本音コラム", "尿漏れ対策を“こっそり”から“ふつうの準備”へ｜吸水ショーツの新しい考え方", "恥ずかしさをほどく読み物"),
            ("コミカル物語", "くしゃみ一回で予定が不安になる朝の話｜吸水ショーツ会議、はじまる", "朝のクローゼットを舞台にした軽い物語"),
            ("商品選び", "20cc・30ccはどのくらい？軽失禁ショーツの吸水量を生活シーンで考える", "吸水量を生活場面に置き換える"),
            ("婦人誌コラム", "外出バッグに安心を一枚｜大人女性の“もしも”を軽くする下着選び", "旅行や買い物の気分に寄せる"),
        ],
    },
    "尿漏れパンツ 女性用 50cc": {
        "noun": "50cc吸水ショーツ",
        "world": "長時間移動、仕事、観劇、通院、旅行",
        "bridge": "50cc前後の備えが合いやすいシーンから商品を紹介",
        "hooks": ["長い外出の日、何を足す？", "安心感は盛りすぎない", "50ccという選択肢"],
        "angles": [
            ("商品選び", "30ccでは少し不安な日に｜50cc吸水ショーツのちょうどいい備え方", "吸水量の段階を整理"),
            ("知識コラム", "吸水量の数字だけで選ばない｜50ccショーツを生活時間で見比べる", "数字を体感に翻訳する"),
            ("シーン物語", "電車、映画、カフェ。席を立ちにくい日の下着選び", "長時間座る日の小さな不安"),
        ],
    },
    "尿漏れパンツ 高吸水・介護": {
        "noun": "高吸水パンツ",
        "world": "介護、夜間、長時間、ご家族の準備",
        "bridge": "150cc以上や洗い替えの必要性から商品を紹介",
        "hooks": ["本人の気持ちも置いていかない", "吸水量と洗い替えの話", "介護下着を選ぶ前に"],
        "angles": [
            ("家族向けコラム", "介護用パンツを選ぶ家族へ｜吸水量より先に考えたい“使う人の気持ち”", "介護の実用品をやさしく考える"),
            ("商品選び", "150cc以上はどんな時に必要？高吸水パンツの選び方と洗い替え計画", "吸水量と枚数の実務"),
            ("本音コラム", "紙パンツだけじゃない選択肢｜洗える高吸水パンツという考え方", "選択肢を広げる読み物"),
        ],
    },
    "尿漏れパンツ 男性用": {
        "noun": "男性用吸水パンツ",
        "world": "シニア男性、外出、長距離移動、父の日",
        "bridge": "男性用の見た目と吸水量から商品を紹介",
        "hooks": ["父にどうすすめる？", "見た目はふつうがいい", "男性の尿もれ対策"],
        "angles": [
            ("本音コラム", "父に尿もれパンツをすすめる時、言い方で空気は変わる", "家族からすすめる時の心理"),
            ("商品選び", "男性用吸水パンツは見た目で選んでいい｜続けやすさの条件", "自然に使えることを重視"),
            ("ギフト企画", "父の日に“気づかい”を贈る｜男性用吸水パンツという実用品ギフト", "ギフト導線にする"),
        ],
    },
    "ブラトップ・カップ付きインナー": {
        "noun": "ブラトップ",
        "world": "休日、在宅、夏、ブラを休みたい日",
        "bridge": "締め付け感やカップ付きの便利さから商品を紹介",
        "hooks": ["今日はブラを休みたい", "ラクして整える", "一枚で出かけられる？"],
        "angles": [
            ("婦人誌コラム", "ブラを休みたい日は悪い日じゃない｜大人のブラトップ活用術", "自分にやさしい選択"),
            ("商品選び", "アンダーゴムが苦手な人へ｜締め付けにくいカップ付きインナーの見方", "構造の違いを説明"),
            ("コミカル物語", "朝のブラ会議、満場一致でブラトップの日", "クローゼット内の軽い物語"),
        ],
    },
    "ブラジャー・ソフトブラ": {
        "noun": "ノンワイヤーブラ",
        "world": "締め付け、夜、療養、リラックス",
        "bridge": "ノンワイヤー、前開き、素材の違いから商品を紹介",
        "hooks": ["ワイヤーに勝たなくていい", "ラクなブラは手抜きじゃない", "夜も昼も軽く"],
        "angles": [
            ("本音コラム", "ラクなブラを選ぶのは手抜きじゃない｜大人のノンワイヤーブラ案内", "我慢しない下着選び"),
            ("商品選び", "締め付けないブラはどこを見る？アンダー・素材・形のチェックポイント", "失敗回避の実用記事"),
            ("療養コラム", "入院や療養時に前開きブラが助かる理由｜着替えやすさの話", "通常商品ページで言いにくい用途"),
        ],
    },
    "汗取りインナー": {
        "noun": "汗取りインナー",
        "world": "白シャツ、通勤、夏、脇汗、清潔感",
        "bridge": "汗取りパッド付きや響きにくさから商品を紹介",
        "hooks": ["白シャツの日の保険", "汗ジミ、見られてる？", "清潔感は仕込みで決まる"],
        "angles": [
            ("知識コラム", "汗ジミが目立つ色・目立ちにくい色｜白シャツの日のインナー作戦", "色と素材の知識"),
            ("商品選び", "脇汗対策は薄さだけで選ばない｜汗取りインナーの見るべきポイント", "失敗しやすい基準を補正"),
            ("シーン物語", "満員電車を降りたあと、ジャケットを脱げる私でいたい", "通勤シーンの共感"),
        ],
    },
    "レディース水着": {
        "noun": "体型カバー水着",
        "world": "ジム、プール、旅行、久しぶりの水着",
        "bridge": "露出控えめ、めくれにくさ、動きやすさから商品を紹介",
        "hooks": ["水着売り場で固まる前に", "隠すより整える", "大人の水着は形で選ぶ"],
        "angles": [
            ("婦人誌コラム", "久しぶりの水着選びで落ち込まない｜大人女性の体型カバー水着案内", "自己肯定感を傷つけない"),
            ("商品選び", "めくれにくい水着はどこが違う？ジム・プール用水着の選び方", "動きやすさと安心感"),
            ("コミカル物語", "試着室で心が折れそうな日に読む、大人の水着作戦会議", "水着選びの心理を軽くする"),
        ],
    },
    "レッグウェア": {
        "noun": "レッグウェア",
        "world": "冷え、重ね着、足元、季節の変わり目",
        "bridge": "厚み、素材、季節感から商品を紹介",
        "hooks": ["冷えは足元から来る", "重ね着してもすっきり", "薄いのに頼れる？"],
        "angles": [
            ("知識コラム", "静電気が起きやすい服の組み合わせ｜冬のレッグウェア素材相性表", "素材の相性を読み物化"),
            ("商品選び", "レギンスとスパッツ、何が違う？大人の重ね着で見る選び方", "呼び名と用途を整理"),
            ("季節コラム", "季節の変わり目に一枚足すなら｜薄手レッグウェアの使いどころ", "実用的な季節導線"),
        ],
    },
    "補正下着": {
        "noun": "補正下着",
        "world": "服のライン、お腹まわり、きれい見え、本音",
        "bridge": "ガードルや補正インナーを服の見え方から商品紹介",
        "hooks": ["お肉は消えません", "痩せる下着、ではない", "服の見え方は変えられる"],
        "angles": [
            ("本音コラム", "着るだけで痩せる、はありえない｜それでも補正下着を使う意味", "商品ページで言いにくい本音"),
            ("商品選び", "苦しい補正下着は続かない｜毎日使いやすいガードルの見方", "継続できる条件"),
            ("婦人誌コラム", "お腹のお肉はどこにも行かない。でも服のラインは整えられる", "リアルな本音と期待値調整"),
        ],
    },
    "シルク・敏感肌": {
        "noun": "やさしい肌着",
        "world": "敏感肌、乾燥、チクチク、素材",
        "bridge": "シルク、綿、ガーゼなど素材別に商品を紹介",
        "hooks": ["肌着で一日が変わる", "チクチクの正体", "素材を味方にする"],
        "angles": [
            ("知識コラム", "綿100％がいつも正解とは限らない？敏感肌インナーの素材選び", "素材の長所短所を整理"),
            ("商品選び", "シルク・綿・ガーゼを比べる｜肌に直接ふれる下着の選び方", "素材比較"),
            ("婦人誌コラム", "肌がゆらぐ日は、服より先に肌着を見直す", "季節と肌状態の読み物"),
        ],
    },
    "温活インナー": {
        "noun": "温活インナー",
        "world": "冷え、腹巻、冷房、冬、寝冷え",
        "bridge": "腹巻き、あったか素材、重ね着しやすさから商品紹介",
        "hooks": ["冷え対策は厚着だけじゃない", "お腹を冷やさない作戦", "見えない一枚が効く"],
        "angles": [
            ("知識コラム", "冷え対策は厚着だけじゃない｜肌に近い一枚を見直す温活インナー術", "肌に近い層の話"),
            ("商品選び", "腹巻きはダサい？見えにくく使える温活アイテムの選び方", "思い込みを崩す"),
            ("季節コラム", "冷房でお腹が冷える人へ｜夏にも使える薄手温活インナー", "夏の冷房対策"),
        ],
    },
    "冷感・季節雑貨": {
        "noun": "冷感アイテム",
        "world": "暑さ、日差し、通勤、外出、バッグの中身",
        "bridge": "冷感タオルやストールの使い方から商品紹介",
        "hooks": ["バッグに入る暑さ対策", "夏の外出を軽くする", "汗をかく前に仕込む"],
        "angles": [
            ("季節コラム", "夏の外出、気合いだけで乗り切らない｜バッグに入る冷感アイテム", "外出準備の読み物"),
            ("商品選び", "冷感タオルとストール、どちらを選ぶ？使う場面で見る暑さ対策", "用途別比較"),
            ("知識コラム", "涼しさは首元から？暑さ対策で見直したい冷やす場所", "体感に寄せる"),
        ],
    },
    "ショーツ": {
        "noun": "大人ショーツ",
        "world": "鼠径部、締め付け、深履き、毎日の下着",
        "bridge": "深履き、ふんどし型、綿素材などから商品紹介",
        "hooks": ["ショーツ、なんとなく選んでない？", "鼠径部をラクにする", "一日中はくものだから"],
        "angles": [
            ("本音コラム", "ショーツの締め付けを我慢しない｜鼠径部をラクにする下着選び", "毎日の不快感に寄せる"),
            ("商品選び", "深履き・浅履き・ふんどし型｜大人ショーツの形で変わる心地よさ", "形の違いを整理"),
            ("コミカル物語", "タンスの中で一軍ショーツだけが減っていく理由", "日常あるあるで読ませる"),
        ],
    },
    "インナー": {
        "noun": "大人インナー",
        "world": "肌着、重ね着、汗、冷え、素材",
        "bridge": "季節や素材、着心地から商品紹介",
        "hooks": ["肌着は地味だけど重要", "一枚目が一日を決める", "服の下の主役"],
        "angles": [
            ("知識コラム", "静電気が起きやすい素材、起きにくい素材｜冬インナーの組み合わせ講座", "商品から少し離れた知識"),
            ("商品選び", "インナーは季節で替える？汗・冷え・肌ざわりで見る選び方", "季節別の実用記事"),
            ("婦人誌コラム", "服を増やす前に、肌着を整える｜大人インナーの考え方", "ワードローブの読み物"),
        ],
    },
    "美容健康雑貨": {
        "noun": "美容健康アイテム",
        "world": "セルフケア、フェムケア、自宅ケア、清潔感",
        "bridge": "使いやすさや続けやすさから商品紹介",
        "hooks": ["人に聞きにくいケアの話", "続くケアだけが残る", "毎日の小さな整え"],
        "angles": [
            ("本音コラム", "フェムケア用品、人に聞きにくいからこそ選び方を整理する", "相談しにくい悩みの入口"),
            ("商品選び", "美容健康アイテムは続けやすさで選ぶ｜自宅ケアの見比べポイント", "継続性で商品を見る"),
            ("婦人誌コラム", "自分の機嫌を整える小さな道具｜毎日のセルフケア案内", "気分と実用の間"),
        ],
    },
}


GENERIC_ANGLES = [
    ("知識コラム", "{noun}選びの前に知りたい、素材と季節の小さな相性", "素材や季節を入口にした知識系"),
    ("本音コラム", "売り文句だけではわからない{noun}の本当の選びどころ", "商品ページでは言いにくい本音"),
    ("比較・選び方", "買ってから後悔しない{noun}｜サイズ・素材・使う場面のチェック表", "失敗回避の実用記事"),
    ("コミカル物語", "クローゼットの中で始まる{noun}作戦会議", "商品を擬人化しすぎない軽い物語"),
    ("婦人誌コラム", "きれいに見える日、ラクに過ごす日｜大人の{noun}との付き合い方", "生活者目線のコラム"),
    ("季節コラム", "季節の変わり目に見直したい{noun}｜汗・冷え・肌ざわりの話", "季節ニーズのSEO"),
    ("商品選び", "{noun}は何を基準に選ぶ？価格より先に見るべきポイント", "選び方の基礎"),
    ("読み物", "なんとなく不快、を減らす{noun}の考え方", "悩みを広く拾う読み物"),
]


def cm_teaser(title, kit, style):
    hooks = kit["hooks"]
    if style == "コミカル物語":
        return f"{hooks[0]} / あるあるで始まる / 似合う一枚へ"
    if style == "知識コラム":
        return f"{hooks[0]} / 素材の相性 / 選び方の答え"
    if style == "本音コラム":
        return f"{hooks[0]} / きれいごと抜きで / でも前向きに"
    return f"{hooks[0]} / 気になる見出し / 商品選びへ"


def display_copy(title, kit, style):
    if style == "コミカル物語":
        return f"{kit['hooks'][0]} / あるあるで読む / 自分に合う選び方"
    if style == "知識コラム":
        return f"{kit['hooks'][0]} / 知ると選びやすい / 素材と形の話"
    if style == "本音コラム":
        return f"{kit['hooks'][0]} / きれいごと抜きで / 前向きに選ぶ"
    if style == "商品選び":
        return f"{kit['hooks'][0]} / 失敗しにくい基準 / 目的で選ぶ"
    return f"{kit['hooks'][0]} / 気になる目次 / 続きは本文へ"


def add(rows, seen, products, category, style, title, angle, base_score):
    title = re.sub(r"\s+", " ", title).strip()
    title = title.replace("大人の大人", "大人の")
    if len(title) < 12 or title in seen:
        return
    seen.add(title)
    reps = sorted(products, key=lambda p: p["score"], reverse=True)[:5]
    avg_price = int(sum(p["price"] for p in reps) / len(reps)) if reps else 0
    kit = KITS[category]
    score = base_score + (sum(p["score"] for p in reps) / len(reps) if reps else 50) + min(8, len(products) * 0.45)
    rows.append({
        "priority_score": round(score, 1),
        "candidate_title": title,
        "content_style": style,
        "target_category": category,
        "column_angle": angle,
        "reading_hook": kit["hooks"][0],
        "magazine_cm_teaser": cm_teaser(title, kit, style),
        "video_display_copy": display_copy(title, kit, style),
        "soft_product_link": kit["bridge"],
        "representative_codes": " ".join(p["code"] for p in reps),
        "representative_products": " / ".join(p["name"][:34] for p in reps[:3]),
        "product_count": len(products),
        "avg_price": avg_price,
        "price_band": price_band(avg_price),
        "seo_keywords": " / ".join(search_intent_for(category)),
        "music_style": music_style_for(category),
        "video_focus": "雑誌CM風。商品説明ではなく、気になる見出しをテンポよく見せて記事へ誘導",
        "banner_focus": "記事中の箸休め。知識図解、本音の一言、比較早見、コラム見出し",
        "selection_note": "商品ページ誘導ではなく、読み物として成立するコンテンツ企画",
    })


def diversify(rows, limit=300):
    buckets = defaultdict(deque)
    for row in sorted(rows, key=lambda x: x["priority_score"], reverse=True):
        buckets[(row["target_category"], row["content_style"])].append(row)
    keys = deque(sorted(buckets, key=lambda k: buckets[k][0]["priority_score"], reverse=True))
    result = []
    seen_titles = set()
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
        if row["candidate_title"] not in seen_titles:
            result.append(row)
            seen_titles.add(row["candidate_title"])
            last_category = row["target_category"]
        if bucket:
            keys.append(key)
    if len(result) < limit:
        for row in sorted(rows, key=lambda x: x["priority_score"], reverse=True):
            if row["candidate_title"] not in seen_titles:
                result.append(row)
                seen_titles.add(row["candidate_title"])
            if len(result) >= limit:
                break
    return result[:limit]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    products = load_products()
    by_category = defaultdict(list)
    for p in products:
        if p["category"] in KITS:
            by_category[p["category"]].append(p)

    rows = []
    seen = set()
    for category, kit in KITS.items():
        products_in_category = by_category.get(category, [])
        if not products_in_category:
            continue
        for style, title, angle in kit["angles"]:
            add(rows, seen, products_in_category, category, style, title, angle, 22)
        for style, pattern, angle in GENERIC_ANGLES:
            add(rows, seen, products_in_category, category, style, pattern.format(noun=kit["noun"]), angle, 12)
        features = sorted({f for p in products_in_category for f in p["features"]})
        for feature in features[:8]:
            add(
                rows,
                seen,
                [p for p in products_in_category if feature in p["features"]] or products_in_category,
                category,
                "特徴コラム",
                f"{feature}だけで選んで大丈夫？{kit['noun']}の見落としがちなポイント",
                f"{feature}を入口にした選び方",
                10,
            )
            add(
                rows,
                seen,
                [p for p in products_in_category if feature in p["features"]] or products_in_category,
                category,
                "比較・選び方",
                f"{feature}派のための{kit['noun']}案内｜毎日使うならここを見る",
                f"{feature}商品の比較導線",
                9,
            )

    while len(rows) < 330:
        for category, kit in KITS.items():
            products_in_category = by_category.get(category, [])
            if not products_in_category:
                continue
            n = len([r for r in rows if r["target_category"] == category])
            title = f"{kit['hooks'][n % len(kit['hooks'])]}｜{kit['noun']}で考える{kit['world'].split('、')[n % len(kit['world'].split('、'))]}の整え方"
            add(rows, seen, products_in_category, category, "読み物", title, "短いキャッチから入る雑誌風企画", 6)
            if len(rows) >= 330:
                break

    rows = diversify(rows, 300)
    fields = [
        "no", "priority_score", "candidate_title", "content_style", "target_category",
        "column_angle", "reading_hook", "magazine_cm_teaser", "video_display_copy",
        "soft_product_link",
        "representative_codes", "representative_products", "product_count", "avg_price",
        "price_band", "seo_keywords", "music_style", "video_focus", "banner_focus",
        "selection_note",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            out = dict(row)
            out["no"] = i
            writer.writerow(out)
    print(f"products={len(products)} candidates={len(rows)} output={OUT}")


if __name__ == "__main__":
    main()
