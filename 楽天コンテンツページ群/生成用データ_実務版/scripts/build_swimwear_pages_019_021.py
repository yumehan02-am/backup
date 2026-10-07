from __future__ import annotations

import csv
import math
import shutil
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "production"
REPAIR_REFS = ROOT / "references" / "generated_repair_019_021"


PAGES = {
    "019": {
        "slug": "water_buoyancy_body_burden",
        "title": "陸で歩くよりラクに感じるのはなぜ？｜水の中の体の負担の話",
        "short_title": ["水の中で", "体が軽く感じる理由"],
        "product_ids": ["ftmns00", "ftmhs00"],
        "column_pattern": "soft_textbook",
        "relation_depth": "indirect",
        "theme": "水の浮力と負担感をやさしく整理する",
        "palette": ((216, 240, 243), (93, 174, 189), (247, 249, 244)),
        "page_copy": """# 陸で歩くよりラクに感じるのはなぜ？｜水の中の体の負担の話

プールに入った瞬間、体がふっと軽くなるように感じることがあります。

それは気のせいだけではありません。水の中では浮力が働き、陸の上で歩く時とは体の受け止められ方が変わります。もちろん、だからといって急に何でもできるわけではありません。けれど、久しぶりに体を動かしたい人にとって、その軽さは大きな入口になります。

このコラムでは、水の中で体が軽く感じる理由と、プール時間を気楽に始めるための水着選びを考えます。

## 水に入ると軽く感じる

水の中で体が軽く感じるのは、水が体を下から支えてくれるからです。

陸の上では、歩くたびに足、膝、腰が自分の体重を受け止めます。階段を上がる時、長く歩いた時、久しぶりに運動した時に重さを感じるのは自然なことです。

一方、水の中では体が少し浮きます。プールの深さや姿勢によって感じ方は変わりますが、体重をそのまま受け止める陸上運動とは違い、足元への負担感がやわらぐことがあります。だから、水中ウォーキングは「走るのは不安」「いきなり運動は重い」と感じる人にも考えやすい入口になります。

## ラクなのに動いている

水の中は軽く感じる一方で、動かそうとすると水の抵抗があります。

足を前に出す。腕を振る。向きを変える。ひとつひとつの動きに、水が静かに押し返してきます。陸の上のように速く動かなくても、体はきちんと働いています。

ここで大切なのは、ラクに感じることと、何もしていないことは違うという点です。水に支えられながら、抵抗の中でゆっくり動く。そのバランスが、水中運動の続けやすさにつながります。

## 無理をしない始め方

水中ウォーキングは、最初から長く歩く必要はありません。

プールの端から端までゆっくり歩く。少し休む。また歩く。そのくらいからで十分です。水の中では疲れに気づきにくいこともあるため、慣れるまでは短めに終えるくらいが安心です。

持病がある方、痛みがある方、久しぶりに運動する方は、無理をせず、必要に応じて医師や施設スタッフに確認してください。水中運動はやさしい印象がありますが、体調を見ながら進めることは大切です。

## 水着は安心感で選ぶ

水中運動を始める時、水着は見た目だけでなく、動いている間に気を取られにくいことが大切です。

歩いた時に裾がめくれにくいこと。胸元や脇が落ち着くこと。着替えで手間取りにくいこと。泳ぐ速さを競うわけではないからこそ、こうした地味な安心が続けやすさにつながります。

ノースリーブは肩まわりを動かしやすく、半袖は腕を出しすぎたくない日の安心感があります。どちらが正解というより、自分がプールで落ち着いて動けるかを基準にすると選びやすくなります。

## 準備が軽いと続きやすい

プール通いは、運動そのものより支度で止まってしまうことがあります。

水着、帽子、タオル、着替え、飲み物。必要なものを毎回考えるのは、意外と小さな負担です。だから、帽子付きのセットや、着替えやすい前ファスナーの水着は、運動の前の迷いを減らす助けになります。

水の中で体が軽く感じる。その感覚を味方にするために、まずは支度も軽くしておく。気合いよりも、次の一回を妨げない準備の方が、プール時間には似合います。
""",
        "sections": [
            ("019_light", ["水に入ると", "軽く感じる"]),
            ("019_resistance", ["ラクなのに", "動いている"]),
            ("019_start", ["無理をしない", "始め方"]),
            ("019_choice", ["水着は", "安心感で選ぶ"]),
            ("019_routine", ["準備が軽いと", "続きやすい"]),
        ],
        "points": ["このコラムのポイント", "› 水が体を支えてくれる", "› ラクでもきちんと動く", "› 支度の軽さも大切"],
        "video": [
            ("019_scene03.jpg", "水の中で\n体が軽く感じる理由", "title_type"),
            ("019_scene02.jpg", "歩く場所が変わると\n負担感も変わる", "rise_fade"),
            ("019_scene03.jpg", "このコラムのポイント\n› 水が体を支えてくれる\n› ラクでもきちんと動く\n› 支度の軽さも大切", "points"),
            ("019_scene04.jpg", "がんばりすぎない\n入口をつくる", "slide_left"),
            ("019_scene05.jpg", "水着は\n落ち着いて動けるものを", "rise_fade"),
            ("019_scene06.jpg", "次の一回を\n軽くする準備", "slide_right"),
        ],
    },
    "020": {
        "slug": "water_walking_exercise_time",
        "title": "水中ウォーキングはどれくらい運動になる？｜泳がないプール時間の話",
        "short_title": ["泳がない", "プール時間"],
        "product_ids": ["ftmns00", "ftmhs00"],
        "column_pattern": "soft_textbook",
        "relation_depth": "indirect",
        "theme": "水中ウォーキングの運動量を数字に寄せすぎず読む",
        "palette": ((224, 238, 249), (70, 132, 171), (250, 245, 235)),
        "page_copy": """# 水中ウォーキングはどれくらい運動になる？｜泳がないプール時間の話

プールで歩くだけでも、運動になるのでしょうか。

そんな疑問は、かなり現実的です。泳ぎに自信がない人ほど、プールに行くなら泳がなければいけないと思いがちです。でも、フィットネス目的なら、歩く、腕を動かす、休みながら続けるという使い方もあります。

このコラムでは、水中ウォーキングを「泳げない人の妥協」ではなく、大人が続けやすい運動の入口として見直します。

## 歩くだけでも体は使う

水中ウォーキングは、ただ水の中を移動しているだけに見えるかもしれません。

でも実際には、足を出すたびに水を押し、腕を振るたびに抵抗を受けます。陸上のように足音がしないため、頑張っている実感は控えめです。けれど、体は静かに働いています。

運動量は、体重、歩く速さ、水深、時間、腕の使い方によって変わります。数字だけで決めつけるより、「無理なく続けられる強さで、体を動かしている」と捉える方が現実的です。

## カロリーは目安で考える

消費カロリーは気になりますが、ここは少し冷静に見たいところです。

同じ30分でも、ゆっくり歩く人と、しっかり腕を振って歩く人では運動量が変わります。体格や年齢、体調によっても違います。水中ウォーキングの数字を見かけたとしても、それはあくまで目安です。

大切なのは、数字を増やすことだけではありません。今日はプールに行けた。水の中で歩けた。帰ってきて少し体がほぐれた。そういう実感の積み重ねが、続く運動になります。

## 泳がなくても使える時間

プールは泳ぐ人だけの場所ではありません。

歩くレーンがある施設もあり、ゆっくり体を動かす人もいます。最初から長く泳ぐ必要はありません。泳げないから行けないのではなく、泳がない使い方を知っていれば、プールへの距離は少し縮まります。

水中ウォーキングの日は、速さよりもリズムです。呼吸を整え、姿勢を起こし、足裏で床を感じながら歩く。静かな動きでも、日常とは違う体の使い方になります。

## 服装の不安を減らす

せっかくプールに行っても、水着が気になると運動に集中しにくくなります。

トップスがめくれないか。胸元が落ち着くか。着替えに手間取らないか。帽子を忘れないか。こうした小さな不安は、運動量とは別のところで気持ちを削ります。

フィットネス水着を選ぶ時は、歩く動き、腕を振る動き、休憩でプールサイドに上がる場面まで想像してみると実用的です。派手さよりも、気を取られにくい安心感が続けやすさを支えます。

## 続ける人は支度が軽い

運動が続く人は、気合いだけで続けているわけではありません。

バッグに入れるものが決まっている。水着と帽子が一緒に準備できる。着替えで慌てにくい。そうした段取りが、行く前の迷いを減らします。

水中ウォーキングは、泳がないプール時間です。だからこそ、水着選びも「泳ぐため」だけでなく、「歩く時間を落ち着いて過ごすため」に考えてよいはずです。小さな準備が、次の一回を連れてきてくれます。
""",
        "sections": [
            ("020_walk", ["歩くだけでも", "体は使う"]),
            ("020_calorie", ["カロリーは", "目安で考える"]),
            ("020_no_swim", ["泳がなくても", "使える時間"]),
            ("020_wear", ["服装の不安を", "減らす"]),
            ("020_routine", ["続ける人は", "支度が軽い"]),
        ],
        "points": ["このコラムのポイント", "› 歩くだけでも運動になる", "› 数字は目安で考える", "› 支度が続けやすさを作る"],
        "video": [
            ("020_scene03.jpg", "泳がない\nプール時間", "title_type"),
            ("020_scene02.jpg", "水の中を歩くと\n体は静かに働く", "rise_fade"),
            ("020_scene03.jpg", "このコラムのポイント\n› 歩くだけでも運動になる\n› 数字は目安で考える\n› 支度が続けやすさを作る", "points"),
            ("020_scene04.jpg", "カロリーは\n比べすぎない", "slide_left"),
            ("020_scene05.jpg", "気になる服装を\n先に整える", "rise_fade"),
            ("020_scene06.jpg", "続ける人は\n準備が軽い", "slide_right"),
        ],
    },
    "021": {
        "slug": "pool_day_sleep_rhythm",
        "title": "プールに行った日はよく眠れる？｜水中運動と疲れ方のコラム",
        "short_title": ["プールの日の", "心地よい疲れ"],
        "product_ids": ["ftmns00", "ftmhs00"],
        "column_pattern": "seasonal_letter",
        "relation_depth": "indirect",
        "theme": "水中運動後の疲れ方と生活リズム",
        "palette": ((235, 232, 223), (82, 118, 139), (252, 247, 236)),
        "page_copy": """# プールに行った日はよく眠れる？｜水中運動と疲れ方のコラム

プールから帰った日は、いつもと少し違う疲れ方をすることがあります。

足が重いというより、体の奥が静かにほどけたような疲れ。お風呂のあとのような眠気。もちろん、誰にでも同じように起こるわけではありません。けれど、水の中で体を動かした日には、陸上の運動とは違う余韻があります。

このコラムでは、水中運動のあとに感じる心地よい疲れと、無理なくプール通いを続けるための準備を考えます。

## 疲れ方が少し違う

水の中で歩いたあとは、走った時のような強い息切れとは違う疲れを感じることがあります。

水に支えられながら動くため、足元への衝撃はやわらぎます。一方で、水の抵抗の中で腕や脚を動かすので、体はしっかり使われています。軽く感じるのに、あとからじんわり疲れる。その差が、プールの日らしさかもしれません。

疲れ方には個人差があります。気持ちよく眠れる日もあれば、張り切りすぎてだるくなる日もあります。最初は短めにして、自分のちょうどよさを探すことが大切です。

## 眠りを保証する話ではない

「プールに行けば必ずよく眠れる」と言い切ることはできません。

睡眠は、運動だけでなく、食事、ストレス、体調、寝る前の過ごし方、室温など、いろいろな要素に左右されます。だから、水中運動を眠りの特効薬のように考えるのは少し違います。

ただ、日中に無理のない範囲で体を動かし、帰宅後にゆっくり休む流れを作ることは、生活リズムを整えるきっかけになります。プールはその一つの選択肢として考えるくらいが、ちょうどよい距離感です。

## 帰り道まで含めて考える

プールの日は、運動して終わりではありません。

着替えて、髪や体を整えて、濡れたものを持ち帰る。帰り道に少し眠くなることもあります。だから、予定を詰め込みすぎず、帰ってから休める余白を残しておくと安心です。

水中運動は気持ちよくても、体はきちんと働いています。終わったあとの水分補給や、冷えすぎない服装も大切です。運動そのものだけでなく、その後の過ごし方まで含めてプール時間と考えると、疲れを味方にしやすくなります。

## 着替えの手間を減らす

プールの日の疲れを大きくする原因のひとつは、着替えの面倒さです。

濡れた水着が脱ぎにくい。帽子を探す。バッグの中でタオルと着替えが混ざる。小さなことですが、運動後の体には少しこたえます。

前ファスナーの水着や帽子付きのセットは、そうした支度の迷いを減らす助けになります。水着そのものが眠りをよくするわけではありませんが、プールに行く前後の負担を軽くすることは、続けやすさにつながります。

## ほどよい疲れで帰る

プール通いを長く続けるなら、「今日はまだ少しできそう」くらいで終える日があってもいいと思います。

毎回へとへとになるまで頑張ると、次に行く気持ちが重くなることがあります。水の中で歩けた。体が少しほぐれた。帰ってゆっくりできた。そのくらいの満足感を残す方が、大人の運動には合っているかもしれません。

水中運動の心地よい疲れを楽しむために、支度はできるだけ軽く。落ち着いて着られるフィットネス水着を選んでおくと、プールの日の前後まで少し楽になります。
""",
        "sections": [
            ("021_tired", ["疲れ方が", "少し違う"]),
            ("021_sleep", ["眠りを保証する", "話ではない"]),
            ("021_after", ["帰り道まで", "含めて考える"]),
            ("021_change", ["着替えの手間を", "減らす"]),
            ("021_end", ["ほどよい疲れで", "帰る"]),
        ],
        "points": ["このコラムのポイント", "› 疲れ方には個人差がある", "› 帰宅後の余白も大切", "› 支度を軽くして続ける"],
        "video": [
            ("021_scene03.jpg", "プールの日の\n心地よい疲れ", "title_type"),
            ("021_scene02.jpg", "よく眠れるかは\n人それぞれ", "rise_fade"),
            ("021_scene03.jpg", "このコラムのポイント\n› 疲れ方には個人差がある\n› 帰宅後の余白も大切\n› 支度を軽くして続ける", "points"),
            ("021_scene04.jpg", "運動のあとは\n予定を詰めすぎない", "slide_left"),
            ("021_scene05.jpg", "着替えの面倒を\n少し減らす", "rise_fade"),
            ("021_scene06.jpg", "ほどよい疲れで\n帰る", "slide_right"),
        ],
    },
}


def mincho(size: int, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\yumindb.ttf" if bold else r"C:\Windows\Fonts\yumin.ttf",
        r"C:\Windows\Fonts\YuMincho.ttc",
        r"C:\Windows\Fonts\meiryo.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_size(text: str, font) -> tuple[int, int]:
    scratch = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    box = ImageDraw.Draw(scratch).textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def cover_crop(img: Image.Image, size: tuple[int, int], bias_x: float = 0.0, bias_y: float = 0.0) -> Image.Image:
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    max_left = resized.width - target_w
    max_top = resized.height - target_h
    left = round(max_left * (0.5 + bias_x / 2))
    top = round(max_top * (0.5 + bias_y / 2))
    left = max(0, min(max_left, left))
    top = max(0, min(max_top, top))
    return resized.crop((left, top, left + target_w, top + target_h))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def glow_box(size: tuple[int, int], alpha: int = 76) -> Image.Image:
    w, h = size
    pad = 74
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=28, fill=(255, 255, 255, alpha))
    return layer.filter(ImageFilter.GaussianBlur(34))


def draw_lines(img: Image.Image, lines: list[str], x: int, y: int, sizes: list[int], gaps: list[int], fill=(42, 38, 35)) -> None:
    frame = img.convert("RGBA")
    draw = ImageDraw.Draw(frame)
    current_y = y
    for idx, line in enumerate(lines):
        font = mincho(sizes[min(idx, len(sizes) - 1)], idx == 0)
        w, h = text_size(line, font)
        frame.alpha_composite(glow_box((w + 98, h + 48)), (x - 118, current_y - 82))
        draw.text((x, current_y), line, font=font, fill=(*fill, 255))
        current_y += gaps[min(idx, len(gaps) - 1)]
    img.paste(frame.convert("RGB"))


def vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    pix = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        color = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(w):
            pix[x, y] = color
    return img


def draw_pool_lanes(draw: ImageDraw.ImageDraw, w: int, h: int, y0: int, color=(255, 255, 255, 150)) -> None:
    for i in range(6):
        y = y0 + i * 115
        draw.line([(0, y), (w, y - 120)], fill=color, width=10)
        for x in range(-80, w, 130):
            draw.ellipse((x, y - 18, x + 42, y + 18), fill=(79, 130, 169, 130))


def make_background(content_no: str, role: str, page: dict[str, object], seed: int) -> Image.Image:
    top, mid, warm = page["palette"]  # type: ignore[index]
    w = h = 1600
    img = vertical_gradient((w, h), top, warm)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if content_no == "021":
        draw.rectangle((0, 0, w, 470), fill=(246, 238, 220, 185))
        draw.ellipse((1060, 90, 1320, 350), fill=(255, 221, 156, 150))
        draw.rectangle((0, 760, w, h), fill=(70, 106, 128, 75))
    else:
        draw.rectangle((0, 0, w, 520), fill=(248, 252, 250, 170))
        draw.rectangle((0, 640, w, h), fill=(*mid, 120))
        draw_pool_lanes(draw, w, h, 780, (255, 255, 255, 130))

    for i in range(18):
        x = (seed * 97 + i * 173) % w
        y = 600 + ((seed * 53 + i * 89) % 760)
        r = 110 + ((seed + i * 17) % 90)
        draw.ellipse((x - r, y - r // 3, x + r, y + r // 3), fill=(255, 255, 255, 22))

    if "title" in role:
        draw.rounded_rectangle((1040, 330, 1450, 1160), radius=70, fill=(255, 255, 255, 24))
        x0 = 1235
        draw.ellipse((x0, 500, x0 + 64, 564), fill=(72, 64, 58, 92))
        draw.rounded_rectangle((x0 - 28, 582, x0 + 92, 810), radius=36, fill=(32, 58, 76, 100))
        draw.arc((x0 - 52, 600, x0 + 45, 790), 110, 245, fill=(51, 71, 84, 78), width=18)
        draw.arc((x0 + 38, 600, x0 + 135, 790), -65, 70, fill=(51, 71, 84, 78), width=18)
        draw.line((x0 - 2, 818, x0 - 26, 1010), fill=(51, 61, 68, 82), width=24)
        draw.line((x0 + 66, 818, x0 + 98, 1010), fill=(51, 61, 68, 82), width=24)
    elif "calorie" in role or "sleep" in role:
        draw.rounded_rectangle((1000, 300, 1370, 1020), radius=44, fill=(255, 255, 255, 98))
        for i in range(5):
            draw.arc((1040 + i * 38, 380 + i * 70, 1340 - i * 20, 680 + i * 70), 190, 340, fill=(*mid, 125), width=8)
    elif "accent" in role:
        draw.rectangle((170, 1090, 760, 1245), fill=(255, 255, 255, 105))
        draw.rounded_rectangle((1040, 820, 1330, 1120), radius=28, fill=(236, 229, 215, 125))
        draw.ellipse((1085, 870, 1145, 930), fill=(52, 55, 58, 145))
    else:
        x0 = 980 if seed % 2 else 1080
        draw.ellipse((x0, 430, x0 + 78, 508), fill=(53, 48, 44, 112))
        draw.rounded_rectangle((x0 - 30, 520, x0 + 108, 790), radius=34, fill=(39, 57, 76, 104))
        draw.line((x0 - 8, 795, x0 - 42, 1010), fill=(44, 55, 62, 98), width=26)
        draw.line((x0 + 78, 795, x0 + 124, 1010), fill=(44, 55, 62, 98), width=26)

    layer = layer.filter(ImageFilter.GaussianBlur(0.35))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    return img.filter(ImageFilter.UnsharpMask(radius=1.1, percent=105, threshold=4))


PAGE_SOURCES = {
    "019": {
        "title": "019_pool_wide.png",
        "points": "019_pool_walk.png",
        "019_light": "019_light_underwater.png",
        "019_resistance": "019_water_close.png",
        "019_start": "019_start_distant_pool.png",
        "019_choice": "019_choice_preparation.png",
        "019_routine": "019_routine_poolbag.png",
        "accent_01": "019_accent_water_ripple.png",
        "accent_02": "019_accent_bathroom_prep.png",
    },
    "020": {
        "title": "020_title_pool_time_stilllife.png",
        "points": "020_pool_prep.png",
        "020_walk": "020_walk_wide_lane.png",
        "020_calorie": "020_calorie_time.png",
        "020_no_swim": "020_no_swim_walking_lane.png",
        "020_wear": "020_wear_changing_bench.png",
        "020_routine": "020_routine_entryway.png",
        "accent_01": "020_accent_pool_key.png",
        "accent_02": "020_accent_laundry_prep.png",
    },
    "021": {
        "title": "021_pool_after.png",
        "points": "021_pool_rest.png",
        "021_tired": "021_tired_pool_lounge.png",
        "021_sleep": "021_sleep_home_evening.png",
        "021_after": "021_after_lounge.png",
        "021_change": "021_change_locker_room.png",
        "021_end": "021_end_evening_walk.png",
        "accent_01": "021_accent_home_towel.png",
        "accent_02": "021_accent_dusk_window.png",
    },
}


def source_name_for(content_no: str, role: str) -> str:
    return PAGE_SOURCES[content_no][role]


def source_background(content_no: str, role: str) -> Image.Image:
    filename = source_name_for(content_no, role)
    path = REPAIR_REFS / filename
    if not path.exists():
        raise FileNotFoundError(f"生成背景が見つかりません: {path}")
    return Image.open(path).convert("RGB")


def make_bgm(base: Path, content_no: str, mood: str) -> None:
    video = base / "video"
    video.mkdir(parents=True, exist_ok=True)
    path = video / f"bgm_swimwear_{content_no}.wav"
    sr = 44100
    duration = 30.0
    if mood == "evening":
        chords = [(220.00, 293.66, 369.99), (246.94, 329.63, 415.30), (196.00, 261.63, 329.63), (293.66, 369.99, 440.00)]
        pulse = 0.006
    else:
        chords = [(261.63, 329.63, 392.00), (293.66, 369.99, 440.00), (246.94, 329.63, 415.30), (329.63, 392.00, 493.88)]
        pulse = 0.008
    total = int(sr * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for n in range(total):
            t = n / sr
            env = min(1.0, t / 1.4, (duration - t) / 2.0)
            chord = chords[int(t / 4.0) % len(chords)]
            sample = 0.0
            for freq in chord:
                sample += math.sin(2 * math.pi * freq * t) * 0.048
                sample += math.sin(2 * math.pi * freq * 2.0 * t) * 0.004
            sample += math.sin(2 * math.pi * 783.99 * t) * pulse * (0.5 + 0.5 * math.sin(2 * math.pi * 0.13 * t))
            sample *= env * 0.62
            val = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(val.to_bytes(2, "little", signed=True))
        wf.writeframes(frames)


def make_scenes(base: Path, content_no: str, files: list[str]) -> None:
    scenes = base / "video" / "scene_backgrounds"
    if scenes.exists():
        shutil.rmtree(scenes)
    scenes.mkdir(parents=True, exist_ok=True)
    for idx, name in enumerate(files, 1):
        img = Image.open(base / "images" / "work" / name).convert("RGB")
        cover_crop(img, (1200, 1200), 0, 0).save(scenes / f"{content_no}_scene{idx:02d}.jpg", quality=94)


def build_page(content_no: str, page: dict[str, object]) -> None:
    base = PRODUCTION / f"{content_no}_{page['slug']}" / "納品用"
    delivery = base / "images" / "delivery"
    work = base / "images" / "work"
    originals = work / "generated_originals"
    data = base / "data"
    delivery.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    originals.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    (base / "video").mkdir(parents=True, exist_ok=True)

    (base / "page_copy.md").write_text(str(page["page_copy"]), encoding="utf-8")

    roles = ["title", "points"] + [role for role, _lines in page["sections"]] + ["accent_01", "accent_02"]
    source_rows = []
    for idx, role in enumerate(roles, 1):
        source_name = source_name_for(content_no, role)
        img = source_background(content_no, role)
        bg_name = f"{role}_bg.png" if str(role).startswith(f"{content_no}_") else f"{content_no}_{role}_bg.png"
        img.save(originals / bg_name)
        img.save(work / bg_name)
        source_rows.append({"role": str(role), "source_file": source_name, "work_file": f"images/work/{bg_name}"})

    write_csv(data / "image_source_manifest.csv", ["role", "source_file", "work_file"], source_rows)

    title = cover_crop(Image.open(work / f"{content_no}_title_bg.png").convert("RGB"), (1600, 900), -0.12, 0.0)
    draw_lines(title, page["short_title"], 94, 300, [72, 84], [104, 108])  # type: ignore[arg-type]
    title.save(delivery / f"{content_no}_title.jpg", quality=94)
    title.save(delivery / f"{content_no}_thumbnail.jpg", quality=94)

    points = cover_crop(Image.open(work / f"{content_no}_points_bg.png").convert("RGB"), (1600, 520), -0.16, 0.0)
    draw_lines(points, page["points"], 100, 70, [46, 34, 34, 34], [74, 56, 56, 56])  # type: ignore[arg-type]
    points.save(work / f"{content_no}_points.jpg", quality=94)

    banner_rows = []
    for role, lines in page["sections"]:  # type: ignore[assignment]
        img = cover_crop(Image.open(work / f"{role}_bg.png").convert("RGB"), (1600, 520), -0.18, 0.0)
        draw_lines(img, lines, 92, 148, [54, 54], [78, 72])
        out = f"{role}.jpg"
        img.save(delivery / out, quality=94)
        banner_rows.append({"filename": out, "headline": "\n".join(lines), "subcopy": "", "asset_type": role.replace(f"{content_no}_", "")})

    for accent in ["accent_01", "accent_02"]:
        cover_crop(Image.open(work / f"{content_no}_{accent}_bg.png").convert("RGB"), (1200, 1200), 0, 0).save(delivery / f"{content_no}_{accent}.jpg", quality=94)

    write_csv(
        data / "banner_plan.csv",
        ["filename", "headline", "subcopy", "asset_type"],
        [
            {"filename": f"{content_no}_title.jpg", "headline": str(page["title"]), "subcopy": str(page["theme"]), "asset_type": "title"},
            {"filename": f"{content_no}_points.jpg", "headline": "\n".join(page["points"]), "subcopy": "", "asset_type": "points"},  # type: ignore[arg-type]
            *banner_rows,
            {"filename": f"{content_no}_accent_01.jpg", "headline": "", "subcopy": "文字なし正方形アクセント", "asset_type": "accent_image"},
            {"filename": f"{content_no}_accent_02.jpg", "headline": "", "subcopy": "文字なし正方形アクセント", "asset_type": "accent_image"},
        ],
    )

    parts = [
        {"order": "1", "part_type": "banner", "file_or_source": f"images/delivery/{content_no}_title.jpg", "note": "タイトル画像 1600x900", "placement": "", "after_section": ""},
        {"order": "2", "part_type": "video", "file_or_source": f"video/opening_cm_{content_no}_vertical.mp4", "note": "タイトル直下の動く目次CM", "placement": "", "after_section": ""},
        {"order": "3", "part_type": "points_image", "file_or_source": f"images/work/{content_no}_points.jpg", "note": "動画用ポイント画像 TSVには出さない", "placement": "", "after_section": ""},
    ]
    order = 4
    for idx, (role, _lines) in enumerate(page["sections"], 1):  # type: ignore[assignment]
        parts.append({"order": str(order), "part_type": "banner", "file_or_source": f"images/delivery/{role}.jpg", "note": "章バナー", "placement": "before_body", "after_section": str(idx)})
        order += 1
        if idx == 2:
            parts.append({"order": str(order), "part_type": "accent_image", "file_or_source": f"images/delivery/{content_no}_accent_01.jpg", "note": "文字なし正方形アクセント", "placement": "after_body", "after_section": "2"})
            order += 1
        if idx == 4:
            parts.append({"order": str(order), "part_type": "accent_image", "file_or_source": f"images/delivery/{content_no}_accent_02.jpg", "note": "文字なし正方形アクセント", "placement": "after_body", "after_section": "4"})
            order += 1
    parts.append({"order": str(order), "part_type": "product_parts", "file_or_source": "product_ids.csv", "note": "関連商品パーツ", "placement": "", "after_section": ""})
    write_csv(data / "rakuten_parts_plan.csv", ["order", "part_type", "file_or_source", "note", "placement", "after_section"], parts)

    scene_files = ["title", page["sections"][0][0], "points", page["sections"][1][0], page["sections"][3][0], page["sections"][4][0]]  # type: ignore[index]
    make_scenes(base, content_no, [f"{content_no}_{role}_bg.png" if role in {"title", "points"} else f"{role}_bg.png" for role in scene_files])

    storyboard = []
    for idx, (background, copy, animation) in enumerate(page["video"], 1):  # type: ignore[assignment]
        storyboard.append(
            {
                "scene": str(idx),
                "background_file": background,
                "duration_sec": "5.2" if idx == 1 else ("4.1" if idx == 3 else "3.6"),
                "display_copy": copy,
                "text_animation": animation,
                "crop_x": "0",
                "crop_y": "0",
            }
        )
    write_csv(data / "video_storyboard.csv", ["scene", "background_file", "duration_sec", "display_copy", "text_animation", "crop_x", "crop_y"], storyboard)

    write_csv(
        base / "product_ids.csv",
        ["product_id", "role", "note"],
        [
            {"product_id": product_id, "role": "関連商品", "note": "一般的なフィットネス水着。帽子付き上下セット"}
            for product_id in page["product_ids"]  # type: ignore[union-attr]
        ],
    )

    ref = """# 参考情報メモ

- Mayo Clinic News Network: 水中運動は浮力により関節や骨への負担感を軽くし、水の抵抗で運動になるという説明を確認。
- CDC Healthy Swimming: 水中運動は身体面とメンタル面の健康に役立つ可能性があり、慢性疾患がある人にも有用な場合があるという説明を確認。
- Harvard Health: 水中エアロビクスなどの消費カロリーは体重や強度で変わるため、本文では数字を断定せず目安として扱う。
- Mayo Clinic: 運動は睡眠の質に役立つ場合があるが、睡眠は複数要因に左右されるため、本文では保証表現を避ける。
"""
    (data / "reference_sources.md").write_text(ref, encoding="utf-8")

    notes = f"""# 制作メモ {content_no}

- 元タイトル案: ftmns00/ftmhs00 リスト
- タイトル: {page['title']}
- 商品ID: ftmns00 / ftmhs00
- column_pattern: {page['column_pattern']}
- relation_depth: {page['relation_depth']}
- reference_mode: none
- video_style: toc_cm
- 商品画像確認: ftmns00/ftmhs00 は一般的なフィットネス水着として確認。商品写真の精密再現は行わず、帽子付き上下セット、前ファスナー、ノースリーブ/半袖の違い、めくれ対策を本文後半の接続に使用。
- 商品との距離: indirect。本文前半は水中運動の知識や生活リズムを主役にし、商品紹介は終盤で準備のしやすさへ橋渡し。
- 既存ページで避ける要素: 018の特殊な体型カバー水着寄せ、商品柄再現、プール内の後ろ姿メイン構図。今回は一般水着向けに抽象度を上げた生活シーンで差別化。
- 背景画像: references/generated_repair_019_021/ の実写風生成背景を使用。簡易図形・プレースホルダー背景は不採用。
- 画像生成順序: 個別背景生成 -> references保存 -> generated_originals保存 -> work配置 -> 文字入れ -> delivery書き出し。コンタクトシートや一覧画像からの切り出しなし。
- points画像: images/work/{content_no}_points.jpg は管理素材。標準TSVには出さない。
"""
    (base / "notes.md").write_text(notes, encoding="utf-8")

    make_bgm(base, content_no, "evening" if content_no == "021" else "calm")


def build() -> None:
    for content_no, page in PAGES.items():
        build_page(content_no, page)


if __name__ == "__main__":
    build()
