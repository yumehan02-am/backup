from __future__ import annotations

import csv
import math
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "production"


PAGES = {
    "007": {
        "slug": "007_posture_remember_intro",
        "title": "猫背を“治す”ではなく、姿勢を思い出す｜大人の姿勢サポートインナー入門",
        "style": "知識コラム",
        "tone": "明るいデスク・鏡・知識整理。007は学びの空気、008は習慣、009は朝の物語で差別化。",
        "products": ["ssjbr00", "ssjtk00"],
        "bgs": ["title", "points", "awareness", "choice", "closing"],
        "banner": [
            ("title", ["猫背を“治す”ではなく", "姿勢を思い出す"], "大人の姿勢サポートインナー入門"),
            ("points", ["このコラムのポイント", "› 矯正ではなく意識づけ", "› 背中を思い出すきっかけ", "› 毎日の下着で続ける"], ""),
            ("awareness", ["姿勢は", "一日中がんばれない"], "だから、思い出す仕組みを作る"),
            ("choice", ["ブラ型とブラタンク型", "どちらが続けやすい？"], "服と生活に合わせて選ぶ"),
            ("closing", ["きれいな立ち姿は", "まず思い出すことから"], ""),
        ],
        "storyboard": [
            ("5.8", "title", "猫背を治すより\n姿勢を思い出す", "typewriter"),
            ("3.8", "awareness", "一日中\n背すじを頑張れない", "rise"),
            ("4.8", "points", "このコラムのポイント\n› 矯正ではなく意識\n› 背中を思い出す\n› 毎日続ける", "points"),
            ("3.8", "choice", "強く固定するより\n気づくきっかけ", "slide_left"),
            ("3.8", "closing", "下着は\n習慣にしやすい", "slide_right"),
            ("4.2", "title", "今日の背中を\n少しだけ意識", "soft_drop"),
        ],
        "copy": """# 猫背を“治す”ではなく、姿勢を思い出す｜大人の姿勢サポートインナー入門

## 導入

鏡に映った横顔や、写真に写った後ろ姿を見て、「少し背中が丸いかも」と感じることがあります。

けれど、姿勢を一日中きれいに保つのは簡単ではありません。仕事、家事、スマホ、移動。気づけば肩が前に入り、背中のことを忘れている時間のほうが長いものです。

姿勢サポートインナーは、猫背を治す道具ではありません。矯正ベルトのように強く固定するものでもありません。ここで考えたいのは、毎日の下着を通して「背中を思い出す」きっかけを作ることです。

## 動画直下の補足文

姿勢の悩みは、無理に正そうとすると続きにくいもの。下着でできること、できないことを分けながら、日常の中で意識しやすい選び方を整理します。

## このコラムのポイント

› 矯正ではなく意識づけ

› 背中を思い出すきっかけ

› 毎日の下着で続ける

## 1. 姿勢は、一日中がんばり続けるものではない

背すじを伸ばそうと思っても、数分後には忘れてしまう。これは意志が弱いからではありません。日常の動作は、目の前の作業に意識が向きやすく、姿勢は後回しになりがちです。

だからこそ、必要なのは「完璧な姿勢」ではなく、ふと思い出せるきっかけです。

画像案: `images/007_awareness.jpg`

## 2. 矯正ベルトとサポートインナーは、役割が違う

矯正ベルトは、装着感や固定感がはっきりしているものが多く、目的も特別です。一方、姿勢サポートインナーは、日常の下着として着ることを前提にしたアイテムです。

強く直すのではなく、背中や肩まわりに意識が戻りやすい状態を作る。そこに違いがあります。

## 3. 下着でできること、できないこと

下着を着るだけで猫背が改善する、体が変わる、と言い切ることはできません。

ただ、背中側のサポート感や着用時のフィット感によって、「今、背中が丸くなっているかも」と気づきやすくなることはあります。姿勢そのものを変える主役は、日々の動き方や休み方。下着は、その意識を助ける脇役です。

画像案: `images/007_points.jpg`

## 4. ブラ型とブラタンク型、続けやすいのはどちら？

ブラ型は、普段のブラ感覚で取り入れやすいのが魅力です。ブラタンク型は、お腹まわりまで一枚で整えたい日や、インナーとして安定感がほしい日に向きます。

大切なのは、強さよりも続けやすさ。毎日着るものだからこそ、服装や生活に合う形を選びたいところです。

画像案: `images/007_choice.jpg`

## おすすめ商品への自然な接続

姿勢が気になるけれど、矯正ベルトほど大げさにしたくない方には、姿勢を意識しやすいサポートインナーが候補になります。ブラ型の `ssjbr00`、ブラタンク型の `ssjtk00` を、普段の服や着心地の好みに合わせて紹介します。

## まとめ

姿勢は、気合いだけで続けるものではありません。

大人の下着選びに「背中を思い出す」という視点を少し足す。そんな小さな工夫が、毎日の立ち姿や服の見え方を見直すきっかけになります。
""",
    },
    "008": {
        "slug": "008_correction_belt_continuation",
        "title": "矯正ベルトが続かなかった人へ｜毎日のインナーで姿勢を意識する話",
        "style": "本音コラム",
        "tone": "温かい寝室・引き出し・洗濯。ベルト比較を直接描かず、続けやすい日常感で差別化。",
        "products": ["ssjtk00", "ssjbr00"],
        "bgs": ["title", "points", "daily", "choice", "closing"],
        "banner": [
            ("title", ["矯正ベルトが", "続かなかった人へ"], "毎日のインナーで姿勢を意識する話"),
            ("points", ["このコラムのポイント", "› 続かない理由", "› 下着だからできること", "› 無理なく思い出す"], ""),
            ("daily", ["特別な道具は", "続けるほどむずかしい"], "日常に入る形を考える"),
            ("choice", ["朝、手に取りやすいことも", "大事な機能"], "ブラタンクという選択"),
            ("closing", ["明日の準備に", "背中の意識を少しだけ"], ""),
        ],
        "storyboard": [
            ("5.8", "title", "矯正ベルトが\n続かなかった人へ", "typewriter"),
            ("3.8", "daily", "特別な道具は\n続けるほどむずかしい", "rise"),
            ("4.8", "points", "このコラムのポイント\n› 続かない理由\n› 下着だからできる\n› 無理なく思い出す", "points"),
            ("3.8", "choice", "朝の引き出しに\n入るくらいがいい", "slide_left"),
            ("3.8", "closing", "固定より\n続けやすさを見る", "slide_right"),
            ("4.2", "title", "毎日のインナーで\n背中を意識", "soft_drop"),
        ],
        "copy": """# 矯正ベルトが続かなかった人へ｜毎日のインナーで姿勢を意識する話

## 導入

姿勢をよくしたいと思って、ベルトやサポーターを試したことがある。けれど、着けるのが面倒だったり、服の下で気になったりして、いつの間にか使わなくなってしまった。

それは珍しいことではありません。特別な道具は、目的がはっきりしているぶん、日常に入れるハードルもあります。

このコラムでは、矯正ベルトと同じことを下着に求めるのではなく、毎日着るインナーで「姿勢を意識するきっかけ」を作る考え方を整理します。

## このコラムのポイント

› 続かない理由

› 下着だからできること

› 無理なく思い出す

## 1. 続かなかったのは、あなたのせいだけではない

姿勢ベルトは、装着するタイミングを選びます。家ではよくても外では気になる。服の下に入れると存在感が出る。毎日使うには、少し気合いがいることもあります。

だから、続かないこと自体を失敗と考えなくても大丈夫です。

画像案: `images/008_daily.jpg`

## 2. 下着なら、朝の準備に入りやすい

下着は、毎朝ほぼ必ず手に取るものです。そこに姿勢を意識しやすい構造があれば、特別な道具を追加するよりも生活に入りやすい場合があります。

もちろん、下着が姿勢を治すわけではありません。けれど、背中に意識が向くきっかけを毎日の服装に入れることはできます。

画像案: `images/008_points.jpg`

## 3. 強く固定するより、無理なく続くほうが合う人もいる

しっかり固定される安心感が好きな人もいれば、強い締め付けが苦手な人もいます。

姿勢サポートインナーは、矯正ベルトの代わりではなく、日常で続けやすい選択肢です。強く正すより、思い出せること。毎日着られること。そのほうが合う人もいます。

画像案: `images/008_choice.jpg`

## 4. ブラタンク型は、一枚で習慣化しやすい

ブラタンク型は、ブラとインナーを一枚で済ませたい日にも選びやすい形です。家事、在宅ワーク、近所への外出など、日常の中で取り入れやすいことが続けやすさにつながります。

ブラ型が好みの方は、普段の下着に近い感覚で選ぶのもよいでしょう。

## おすすめ商品への自然な接続

矯正ベルトは大げさに感じるけれど、背中は少し意識したい。そんな方には、ブラタンク型の `ssjtk00`、ブラ型の `ssjbr00` を、着用シーンに合わせて紹介します。

## まとめ

姿勢を整えることは、一度の決意より、思い出す回数のほうが大切かもしれません。

特別な道具が続かなかった人ほど、毎日の下着に小さなきっかけを入れる。そんな現実的な始め方もあります。
""",
    },
    "009": {
        "slug": "009_morning_rounded_back_innerwear",
        "title": "背中が丸いかも、と思った朝に読むインナー選び",
        "style": "読み物コラム",
        "tone": "涼しい朝・鏡・外出前。007の知識感、008の温かい習慣感と違い、物語の導入に寄せる。",
        "products": ["ssjbr00", "ssjtk00"],
        "bgs": ["title", "points", "back", "outfit", "closing"],
        "banner": [
            ("title", ["背中が丸いかも", "と思った朝に"], "読むインナー選び"),
            ("points", ["このコラムのポイント", "› 朝の気づき", "› 背中を責めない", "› 下着で思い出す"], ""),
            ("back", ["後ろ姿は", "自分では見落としやすい"], "気づいた朝から始める"),
            ("outfit", ["服を選ぶ時間に", "背中のことも少しだけ"], ""),
            ("closing", ["今日の背すじを", "やさしく思い出す"], ""),
        ],
        "storyboard": [
            ("5.8", "title", "背中が丸いかも\nと思った朝に", "typewriter"),
            ("3.8", "back", "後ろ姿は\n自分では見落としやすい", "rise"),
            ("4.8", "points", "このコラムのポイント\n› 朝の気づき\n› 背中を責めない\n› 下着で思い出す", "points"),
            ("3.8", "outfit", "服を選ぶ時間に\n背中も少しだけ", "slide_left"),
            ("3.8", "closing", "強く正すより\nそっと気づく", "slide_right"),
            ("4.2", "title", "今日の背すじを\nやさしく思い出す", "soft_drop"),
        ],
        "copy": """# 背中が丸いかも、と思った朝に読むインナー選び

## 導入

朝、鏡の前で服を羽織ったとき。正面は悪くないのに、ふと横や後ろのシルエットが気になることがあります。

背中が少し丸いかも。肩が前に入っているかも。そう気づいた瞬間、なんとなく気分まで小さくなる。

でも、そこで自分を責める必要はありません。姿勢は、気づいたときに戻せばいいもの。毎日の服選びの中に、背中を思い出すきっかけを入れることもできます。

## このコラムのポイント

› 朝の気づき

› 背中を責めない

› 下着で思い出す

## 1. 後ろ姿は、自分では見落としやすい

正面の服は毎日見ていても、後ろ姿は意外と見ていません。写真や鏡の角度で初めて、背中の丸まりや肩の入り方に気づくことがあります。

それは欠点探しではなく、服の見え方を知るきっかけです。

画像案: `images/009_back.jpg`

## 2. 姿勢が気になる朝ほど、強く責めない

姿勢は、疲れや作業時間、スマホを見る姿勢でも変わります。いつも同じ状態ではありません。

だから「悪い姿勢を直さなきゃ」と力むより、「今日は少し背中を思い出そう」と考えるほうが続きやすくなります。

画像案: `images/009_points.jpg`

## 3. インナーは、朝の気づきを日中へつなぐもの

姿勢サポートインナーは、着るだけで猫背を治すものではありません。

ただ、背中側のサポート感があることで、日中にふと姿勢を思い出すきっかけになることがあります。朝に気づいたことを、昼間の生活へそっと持っていくような役割です。

画像案: `images/009_outfit.jpg`

## 4. ブラ型かブラタンク型かは、その日の服で選ぶ

すっきり着たい服の日はブラ型。インナーも一枚でまとめたい日はブラタンク型。どちらか一方に決めるより、服と生活に合わせて分けると選びやすくなります。

大切なのは、強い補整感よりも、無理なく着られること。続けられる形を選ぶことです。

## おすすめ商品への自然な接続

背中が丸いかも、と感じる朝に、姿勢を意識しやすいインナーを選ぶなら、ブラ型の `ssjbr00`、ブラタンク型の `ssjtk00` が候補になります。商品紹介パーツでは、着心地や形の違いを見ながら選べるようにします。

## まとめ

背中が気になる朝は、自分を否定する朝ではありません。

服を選ぶついでに、背中のことを少し思い出す。そんな小さな習慣として、姿勢サポートインナーを考えてみるのもひとつです。
""",
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
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    max_left = resized.width - tw
    max_top = resized.height - th
    left = round(max_left * (0.5 + bias_x / 2))
    top = round(max_top * (0.5 + bias_y / 2))
    return resized.crop((max(0, min(max_left, left)), max(0, min(max_top, top)), max(0, min(max_left, left)) + tw, max(0, min(max_top, top)) + th))


def glow_box(size: tuple[int, int], alpha: int = 102) -> Image.Image:
    w, h = size
    pad = 34
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=26, fill=(255, 255, 255, alpha))
    return layer.filter(ImageFilter.GaussianBlur(18))


def draw_lines(img: Image.Image, lines: list[str], x: int, y: int, sizes: list[int], gaps: list[int]) -> None:
    frame = img.convert("RGBA")
    draw = ImageDraw.Draw(frame)
    current_y = y
    for i, line in enumerate(lines):
        font = mincho(sizes[min(i, len(sizes) - 1)], i == 0)
        w, h = text_size(line, font)
        glow = glow_box((w + 70, h + 34))
        frame.alpha_composite(glow, (x - 69, current_y - 59))
        draw.text((x, current_y), line, font=font, fill=(42, 36, 34, 255))
        current_y += gaps[min(i, len(gaps) - 1)]
    img.paste(frame.convert("RGB"))


def make_bgm(path: Path, page_no: str) -> None:
    sr = 44100
    duration = 31.0
    total = int(sr * duration)
    variants = {
        "007": [(261.63, 329.63, 392.00), (293.66, 369.99, 440.00), (246.94, 329.63, 392.00), (220.00, 277.18, 369.99)],
        "008": [(220.00, 277.18, 329.63), (246.94, 293.66, 369.99), (196.00, 261.63, 329.63), (174.61, 220.00, 293.66)],
        "009": [(293.66, 369.99, 440.00), (329.63, 392.00, 493.88), (261.63, 329.63, 440.00), (246.94, 293.66, 392.00)],
    }
    chords = variants[page_no]
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for n in range(total):
            t = n / sr
            chord = chords[int(t / 4.0) % len(chords)]
            env = min(1.0, t / 1.8, (duration - t) / 2.0)
            sample = 0.0
            for freq in chord:
                sample += math.sin(2 * math.pi * freq * t) * 0.044
                sample += math.sin(2 * math.pi * freq * 2.0 * t) * 0.004
            sample += math.sin(2 * math.pi * (659.25 if page_no != "008" else 523.25) * t) * 0.006 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.12 * t))
            sample *= env * 0.55
            val = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(val.to_bytes(2, "little", signed=True))
        wf.writeframes(frames)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_page(page_no: str, cfg: dict) -> None:
    base = PRODUCTION / cfg["slug"] / "納品用"
    images = base / "images"
    video = base / "video"
    scenes = video / "scene_backgrounds"
    data = base / "data"
    for d in [images, video, scenes, data]:
        d.mkdir(parents=True, exist_ok=True)

    page_copy_path = base / "page_copy.md"
    if not page_copy_path.exists():
        raise FileNotFoundError(
            f"{page_copy_path} がありません。本文は prompts/readable_column_style_rule.md の"
            "読み物コラム基準で作成し、制作メモを入れずに保存してください。"
        )
    (base / "notes.md").write_text(
        f"""# {page_no} 納品メモ

- タイトル: {cfg['title']}
- 元企画番号: ssjbr00 / ssjtk00 タイトル案 { {'007': '2', '008': '4', '009': '5'}[page_no] }
- 対象商品ID: `{ '`, `'.join(cfg['products']) }`
- 種別: {cfg['style']}
- 目的: SEO + 役立つ読み物 + 後半の商品紹介
- 方針: 矯正ベルトではなく、日常の下着で姿勢を意識しやすくする商品として扱う。猫背改善、姿勢矯正、肩こり改善などの医療・効果断定は避ける。
- 差別化メモ: {cfg['tone']}
- 動画: 新規標準ルールに従い `video/opening_cm_{page_no}_vertical.mp4` を主納品にする。
- 背景: 動画背景は `1200 x 1200` 正方形の文字なし生成画像から切り出し。
- BGM: ページごとに異なる雰囲気で生成。標準音量は `-33 LUFS前後`。
- MP4サムネイル: `images/{page_no}_thumbnail.jpg` を `attached_pic` として埋め込む。
""",
        encoding="utf-8",
    )

    write_csv(
        base / "product_ids.csv",
        ["product_id", "role", "note"],
        [
            {"product_id": "ssjbr00", "role": "main" if "ssjbr00" == cfg["products"][0] else "sub", "note": "姿勢サポート系ブラ。普段のブラ感覚で取り入れたい方向。"},
            {"product_id": "ssjtk00", "role": "main" if "ssjtk00" == cfg["products"][0] else "sub", "note": "姿勢サポート系ブラタンク。インナーとして一枚で続けたい方向。"},
        ],
    )

    banner_rows = []
    for role, lines, subcopy in cfg["banner"]:
        src = images / f"{page_no}_{role}_bg.png"
        bg = Image.open(src).convert("RGB").resize((1200, 1200), Image.Resampling.LANCZOS)
        out_name = f"{page_no}_{role}.jpg"
        if role == "title":
            title = cover_crop(bg, (1600, 900), -0.25, 0)
            draw_lines(title, lines, 112, 304, [68, 68], [96, 96])
            title.save(images / out_name, quality=94)
            thumb = cover_crop(bg, (1600, 900), -0.25, 0)
            draw_lines(thumb, lines, 112, 304, [68, 68], [96, 96])
            thumb.save(images / f"{page_no}_thumbnail.jpg", quality=94)
        elif role == "points":
            points = cover_crop(bg, (1600, 520), -0.25, 0)
            draw_lines(points, lines, 96, 92, [48, 33, 33, 33], [76, 55, 55, 55])
            points.save(images / out_name, quality=94)
        else:
            banner = cover_crop(bg, (1600, 520), -0.25, 0)
            draw_lines(banner, lines, 88, 144, [48, 42], [70, 66])
            banner.save(images / out_name, quality=94)
        banner_rows.append({"file": out_name, "headline": " / ".join(lines), "subcopy": subcopy, "type": role})

    write_csv(base / "data" / "banner_plan.csv", ["file", "headline", "subcopy", "type"], banner_rows)
    write_csv(
        base / "data" / "video_storyboard.csv",
        ["scene", "duration", "background", "copy", "animation", "crop_x", "crop_y", "text_center_x", "point_x"],
        [
            {
                "scene": str(i),
                "duration": row[0],
                "background": f"{page_no}_scene{i:02d}.jpg",
                "copy": row[2],
                "animation": row[3],
                "crop_x": "0",
                "crop_y": "0",
                "text_center_x": "",
                "point_x": "",
            }
            for i, row in enumerate(cfg["storyboard"], 1)
        ],
    )
    write_csv(
        base / "data" / "rakuten_parts_plan.csv",
        ["order", "part_type", "file_or_source", "note"],
        [
            {"order": "1", "part_type": "thumbnail", "file_or_source": f"images/{page_no}_thumbnail.jpg", "note": "RMSサムネイル候補"},
            {"order": "2", "part_type": "banner", "file_or_source": f"images/{page_no}_title.jpg", "note": "タイトルバナー"},
            {"order": "3", "part_type": "video", "file_or_source": f"video/opening_cm_{page_no}_vertical.mp4", "note": "タイトル直下の動く目次CM"},
            {"order": "4", "part_type": "text", "file_or_source": "page_copy.md#導入", "note": "導入文"},
            {"order": "5", "part_type": "banner", "file_or_source": f"images/{page_no}_points.jpg", "note": "このコラムのポイント"},
            {"order": "6", "part_type": "text", "file_or_source": "page_copy.md#本文", "note": "本文セクション"},
            {"order": "7", "part_type": "banner", "file_or_source": f"images/{page_no}_{cfg['bgs'][2]}.jpg", "note": "章バナー"},
            {"order": "8", "part_type": "banner", "file_or_source": f"images/{page_no}_{cfg['bgs'][3]}.jpg", "note": "選び方バナー"},
            {"order": "9", "part_type": "banner", "file_or_source": f"images/{page_no}_closing.jpg", "note": "まとめ"},
            {"order": "10", "part_type": "product_parts", "file_or_source": "product_ids.csv", "note": "関連商品への自然な接続"},
        ],
    )

    scene_roles = [row[1] for row in cfg["storyboard"]]
    for i, role in enumerate(scene_roles, 1):
        bg = Image.open(images / f"{page_no}_{role}_bg.png").convert("RGB").resize((1200, 1200), Image.Resampling.LANCZOS)
        bg.save(scenes / f"{page_no}_scene{i:02d}.jpg", quality=94)

    make_bgm(video / f"bgm_posture_column_{page_no}.wav", page_no)

    sheet = Image.new("RGB", (1200, 800), "white")
    files = [f"{page_no}_{role}.jpg" for role, _, _ in cfg["banner"]]
    for i, name in enumerate(files):
        img = Image.open(images / name).convert("RGB")
        img.thumbnail((400, 260), Image.Resampling.LANCZOS)
        x = (i % 3) * 400 + (400 - img.width) // 2
        y = (i // 3) * 400 + 40
        sheet.paste(img, (x, y))
    sheet.save(images / f"{page_no}_banner_contact_sheet.jpg", quality=92)


def main() -> None:
    for page_no, cfg in PAGES.items():
        build_page(page_no, cfg)


if __name__ == "__main__":
    main()
