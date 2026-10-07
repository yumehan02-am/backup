from __future__ import annotations

import csv
import math
import shutil
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
BASE = ROOT / "production" / "018_pool_walking_swimwear" / "納品用"
IMAGE_BASE_URL = "https://image.rakuten.co.jp/u-b-yumehan/cabinet/contents/"


PAGE_COPY = """# 泳がなくてもいいプール時間｜水中ウォーキングと水着選びの話

プールに行く、と聞くと、きれいに泳ぐ人の場所を想像してしまうことがあります。

けれど、フィットネス目的のプール時間は、泳げるかどうかだけで決まりません。水の中をゆっくり歩く。腕を動かす。呼吸を整える。そんな使い方でも、陸上とは違う軽さや心地よさがあります。

このコラムでは、泳ぎに自信がない人でも始めやすい水中ウォーキングと、その時間を過ごしやすくする水着選びを考えます。

## 水中ウォーキングとは

水中ウォーキングは、名前の通り、水の中を歩く運動です。

泳ぐためのフォームを覚える必要はなく、最初はプールの端から端まで、ゆっくり歩くだけでも十分です。水に入ると体が少し軽く感じられ、同時に前へ進むたびに水の抵抗もあります。頑張っている感覚が強すぎないのに、体はきちんと動いている。そのほどよさが、久しぶりの運動には向いています。

大切なのは、速く歩くことよりも、続けられる強さで始めることです。周りの人と比べず、自分の歩幅、自分の呼吸、自分のペースでよい。プールは競争の場所だけではなく、体と相談しながら動ける場所でもあります。

## 泳げなくても始めやすい

プールに行く前の不安には、「泳げないから浮いてしまうのでは」という気持ちもあります。

でも、ジムのプールには、黙々と歩いている人、ゆっくり泳ぐ人、休みながら体を動かす人がいます。全員が速く泳いでいるわけではありません。水中ウォーキングは、泳ぎの上手さよりも、通いやすさや無理のなさが大事です。

この入口を知っているだけで、水着選びの視点も変わります。泳ぐための水着というより、歩いても腕を動かしても落ち着く服。めくれにくいこと、胸元や脇が気になりにくいこと、ボトム丈が短すぎないこと。そうした実用面が、プールへの一歩を支えてくれます。

## 水の抵抗を味方にする

水の中では、同じ一歩でも陸上とは違う感覚があります。

足を前に出すと水が押し返してくる。腕を広げると、思ったよりゆっくりしか動かない。けれど、その抵抗があるからこそ、急に走ったり跳ねたりしなくても体を動かせます。膝や腰が心配な人にとっても、まずは軽い運動として考えやすいのが水中ウォーキングです。

ただし、無理は禁物です。最初から長時間を目指さず、休みながら、体調を見ながらで十分。水の中にいると疲れに気づきにくいこともあるので、慣れるまでは短めに終えるくらいでちょうどよいです。

## 服装は動きやすさから

水中ウォーキングの日の水着は、見た目だけでなく、動きの邪魔をしないことが大切です。

トップスが短すぎると、腕を動かしたときや歩いたときに裾が気になります。体に沿いすぎると、プールサイドに出るまでの時間に落ち着かないこともあります。反対に、ふんわりしすぎて水の中で広がるものも動きにくくなります。

大人のフィットネス水着は、隠すためだけではなく、運動の邪魔を減らすために選ぶものです。ほどよく体を受け止めるトップス、安心感のあるボトム丈、動いても意識を持っていかれにくい形。水の中で歩く時間を考えると、派手さよりも安定感が頼りになります。

## 続ける支度を軽くする

運動は、始めることより続けることの方が難しい場合があります。

プールは水着、帽子、タオル、着替え、飲み物など、持ち物が少し多めです。だからこそ、準備で迷うことを減らしておくと、通う気持ちが軽くなります。上下セットになっている、帽子も用意しやすい、バッグに入れるものが決まっている。そんな小さな段取りが、次の一回につながります。

泳がなくてもいい。長く続けなくてもいい。まずは水の中を歩いて、帰ってこられたら十分です。

体型カバータイプのフィットネス水着は、久しぶりのプール時間を大げさにしないための味方になります。水中ウォーキングから始めたい日には、今の自分が落ち着いて動ける一枚を選ぶ。そこから、プールは少し身近になります。
"""


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


def load_bg_map(work: Path) -> dict[str, Image.Image]:
    bg_names = [
        "018_title_bg.png",
        "018_points_bg.png",
        "018_about_bg.png",
        "018_no_swim_bg.png",
        "018_water_bg.png",
        "018_outfit_bg.png",
        "018_routine_bg.png",
        "018_accent_01_bg.png",
        "018_accent_02_bg.png",
    ]
    missing = [name for name in bg_names if not (work / name).exists()]
    if missing:
        raise FileNotFoundError(
            "納品画像・動画背景は個別生成が必須です。素材シートからの切り出しは禁止です。"
            f"不足背景: {', '.join(missing)}"
        )
    return {name: Image.open(work / name).convert("RGB") for name in bg_names}


def glow_box(size: tuple[int, int], alpha: int = 82) -> Image.Image:
    w, h = size
    pad = 72
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=28, fill=(255, 255, 255, alpha))
    return layer.filter(ImageFilter.GaussianBlur(32))


def draw_lines(img: Image.Image, lines: list[str], x: int, y: int, sizes: list[int], gaps: list[int], fill=(42, 38, 35)) -> None:
    frame = img.convert("RGBA")
    draw = ImageDraw.Draw(frame)
    current_y = y
    for idx, line in enumerate(lines):
        font = mincho(sizes[min(idx, len(sizes) - 1)], idx == 0)
        w, h = text_size(line, font)
        frame.alpha_composite(glow_box((w + 96, h + 48)), (x - 116, current_y - 82))
        draw.text((x, current_y), line, font=font, fill=(*fill, 255))
        current_y += gaps[min(idx, len(gaps) - 1)]
    img.paste(frame.convert("RGB"))


def make_bgm() -> None:
    video = BASE / "video"
    video.mkdir(parents=True, exist_ok=True)
    path = video / "bgm_swimwear_018.wav"
    sr = 44100
    duration = 30.0
    chords = [
        (261.63, 329.63, 392.00),
        (293.66, 369.99, 440.00),
        (246.94, 329.63, 415.30),
        (329.63, 392.00, 493.88),
    ]
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
            sample += math.sin(2 * math.pi * 783.99 * t) * 0.008 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.13 * t))
            sample *= env * 0.62
            val = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(val.to_bytes(2, "little", signed=True))
        wf.writeframes(frames)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_scenes(files: list[str]) -> None:
    scenes = BASE / "video" / "scene_backgrounds"
    if scenes.exists():
        shutil.rmtree(scenes)
    scenes.mkdir(parents=True, exist_ok=True)
    square_bias = {
        "018_title_bg.png": 0.35,
        "018_outfit_bg.png": 0.75,
        "018_routine_bg.png": 0.55,
    }
    for idx, name in enumerate(files, 1):
        img = Image.open(BASE / "images" / "work" / name).convert("RGB")
        cover_crop(img, (1200, 1200), square_bias.get(name, 0), 0).save(scenes / f"018_scene{idx:02d}.jpg", quality=94)


def make_contact_sheet(files: list[str]) -> None:
    sheet = Image.new("RGB", (1200, 1200), "white")
    for i, name in enumerate(files):
        path = BASE / "images" / "delivery" / name
        if not path.exists():
            path = BASE / "images" / "work" / name
        img = Image.open(path).convert("RGB")
        img.thumbnail((390, 260), Image.Resampling.LANCZOS)
        x = (i % 3) * 400 + (400 - img.width) // 2
        y = (i // 3) * 380 + 24
        sheet.paste(img, (x, y))
    sheet.save(BASE / "images" / "work" / "018_contact_sheet.jpg", quality=92)


def copy_product_reference() -> None:
    ref_dir = BASE / "data" / "product_reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    src_dir = ROOT / "production" / "017_pool_before_weight_loss_illustrated" / "納品用" / "data" / "product_reference"
    for name in ["fitm-cv-do_main.jpg", "taikf00_main.jpg"]:
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, ref_dir / name)


def build() -> None:
    delivery = BASE / "images" / "delivery"
    work = BASE / "images" / "work"
    data = BASE / "data"
    delivery.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    (BASE / "video").mkdir(parents=True, exist_ok=True)

    (BASE / "page_copy.md").write_text(PAGE_COPY, encoding="utf-8")
    copy_product_reference()

    bg_map = load_bg_map(work)

    title = cover_crop(bg_map["018_title_bg.png"], (1600, 900), -0.12, 0.0)
    draw_lines(title, ["泳がなくてもいい", "プール時間"], 94, 300, [76, 86], [104, 108])
    title.save(delivery / "018_title.jpg", quality=94)
    title.save(delivery / "018_thumbnail.jpg", quality=94)

    points = cover_crop(bg_map["018_points_bg.png"], (1600, 520), -0.16, 0.0)
    draw_lines(points, ["このコラムのポイント", "› 歩くだけでも入口になる", "› 水の抵抗を味方にする", "› 服装は動きやすさから"], 100, 70, [46, 34, 34, 34], [74, 56, 56, 56])
    points.save(work / "018_points.jpg", quality=94)

    banners = [
        ("018_about_bg.png", "018_about.jpg", ["水中ウォーキング", "という選択"]),
        ("018_no_swim_bg.png", "018_no_swim.jpg", ["泳げなくても", "始めやすい"]),
        ("018_water_bg.png", "018_water.jpg", ["水の抵抗を", "味方にする"]),
        ("018_outfit_bg.png", "018_outfit.jpg", ["服装は", "動きやすさから"]),
        ("018_routine_bg.png", "018_routine.jpg", ["続ける支度を", "軽くする"]),
    ]
    for src, out, lines in banners:
        img = cover_crop(bg_map[src], (1600, 520), -0.18, 0.0)
        draw_lines(img, lines, 92, 148, [54, 54], [78, 72])
        img.save(delivery / out, quality=94)

    cover_crop(bg_map["018_accent_01_bg.png"], (1200, 1200), 0, 0).save(delivery / "018_accent_01.jpg", quality=94)
    cover_crop(bg_map["018_accent_02_bg.png"], (1200, 1200), 0, 0).save(delivery / "018_accent_02.jpg", quality=94)

    write_csv(
        data / "banner_plan.csv",
        ["filename", "headline", "subcopy", "asset_type"],
        [
            {"filename": "018_title.jpg", "headline": "泳がなくてもいいプール時間", "subcopy": "水中ウォーキングと水着選びの話", "asset_type": "title"},
            {"filename": "018_points.jpg", "headline": "このコラムのポイント\n› 歩くだけでも入口になる\n› 水の抵抗を味方にする\n› 服装は動きやすさから", "subcopy": "", "asset_type": "points"},
            {"filename": "018_about.jpg", "headline": "水中ウォーキングという選択", "subcopy": "歩くだけでも始められる", "asset_type": "about"},
            {"filename": "018_no_swim.jpg", "headline": "泳げなくても始めやすい", "subcopy": "水着選びの視点を変える", "asset_type": "no_swim"},
            {"filename": "018_water.jpg", "headline": "水の抵抗を味方にする", "subcopy": "無理なく体を動かす", "asset_type": "water"},
            {"filename": "018_outfit.jpg", "headline": "服装は動きやすさから", "subcopy": "派手さより安定感", "asset_type": "outfit"},
            {"filename": "018_routine.jpg", "headline": "続ける支度を軽くする", "subcopy": "迷わない準備へ", "asset_type": "routine"},
            {"filename": "018_accent_01.jpg", "headline": "", "subcopy": "文字なし正方形アクセント", "asset_type": "accent_image"},
            {"filename": "018_accent_02.jpg", "headline": "", "subcopy": "文字なし正方形アクセント", "asset_type": "accent_image"},
        ],
    )

    write_csv(
        data / "rakuten_parts_plan.csv",
        ["order", "part_type", "file_or_source", "note", "placement", "after_section"],
        [
            {"order": "1", "part_type": "banner", "file_or_source": "images/delivery/018_title.jpg", "note": "タイトル画像 1600x900", "placement": "", "after_section": ""},
            {"order": "2", "part_type": "video", "file_or_source": "video/opening_cm_018_vertical.mp4", "note": "タイトル直下の動く目次CM", "placement": "", "after_section": ""},
            {"order": "3", "part_type": "points_image", "file_or_source": "images/work/018_points.jpg", "note": "動画用ポイント画像 TSVには出さない", "placement": "", "after_section": ""},
            {"order": "4", "part_type": "banner", "file_or_source": "images/delivery/018_about.jpg", "note": "章バナー", "placement": "before_body", "after_section": "1"},
            {"order": "5", "part_type": "banner", "file_or_source": "images/delivery/018_no_swim.jpg", "note": "章バナー", "placement": "before_body", "after_section": "2"},
            {"order": "6", "part_type": "accent_image", "file_or_source": "images/delivery/018_accent_01.jpg", "note": "文字なし正方形アクセント", "placement": "after_body", "after_section": "2"},
            {"order": "7", "part_type": "banner", "file_or_source": "images/delivery/018_water.jpg", "note": "章バナー", "placement": "before_body", "after_section": "3"},
            {"order": "8", "part_type": "banner", "file_or_source": "images/delivery/018_outfit.jpg", "note": "章バナー", "placement": "before_body", "after_section": "4"},
            {"order": "9", "part_type": "accent_image", "file_or_source": "images/delivery/018_accent_02.jpg", "note": "文字なし正方形アクセント", "placement": "after_body", "after_section": "4"},
            {"order": "10", "part_type": "banner", "file_or_source": "images/delivery/018_routine.jpg", "note": "章バナー", "placement": "before_body", "after_section": "5"},
            {"order": "11", "part_type": "product_parts", "file_or_source": "product_ids.csv", "note": "関連商品パーツ", "placement": "", "after_section": ""},
        ],
    )

    write_csv(
        data / "video_storyboard.csv",
        ["scene", "background_file", "duration_sec", "display_copy", "text_animation", "crop_x", "crop_y"],
        [
            {"scene": "1", "background_file": "018_scene03.jpg", "duration_sec": "5.2", "display_copy": "泳がなくてもいい\nプール時間", "text_animation": "title_type", "crop_x": "0", "crop_y": "0"},
            {"scene": "2", "background_file": "018_scene02.jpg", "duration_sec": "3.6", "display_copy": "水の中を\n歩くところから", "text_animation": "rise_fade", "crop_x": "0", "crop_y": "0"},
            {"scene": "3", "background_file": "018_scene03.jpg", "duration_sec": "4.0", "display_copy": "このコラムのポイント\n› 歩くだけでも入口になる\n› 水の抵抗を味方にする\n› 服装は動きやすさから", "text_animation": "points", "crop_x": "0", "crop_y": "0"},
            {"scene": "4", "background_file": "018_scene04.jpg", "duration_sec": "3.6", "display_copy": "がんばるより\n続けやすく", "text_animation": "slide_left", "crop_x": "0", "crop_y": "0"},
            {"scene": "5", "background_file": "018_scene05.jpg", "duration_sec": "3.6", "display_copy": "動きやすさで\n水着を選ぶ", "text_animation": "rise_fade", "crop_x": "0.42", "crop_y": "0"},
            {"scene": "6", "background_file": "018_scene06.jpg", "duration_sec": "3.6", "display_copy": "次の一回を\n軽くする準備", "text_animation": "slide_right", "crop_x": "0.36", "crop_y": "0"},
        ],
    )

    write_csv(
        BASE / "product_ids.csv",
        ["product_id", "role", "note"],
        [
            {"product_id": "fitm-cv-do", "role": "関連商品", "note": "体型カバー水着。水中ウォーキングの入口として"},
            {"product_id": "taikf00", "role": "関連商品", "note": "体型カバー水着。共通テーマの関連商品"},
        ],
    )

    notes = """# 制作メモ 018

- 元タイトル案: リスト3
- タイトル: 泳がなくてもいいプール時間｜水中ウォーキングと水着選びの話
- 商品ID: fitm-cv-do / taikf00
- column_pattern: soft_textbook
- reference_mode: product_inspired_illustration
- video_style: toc_cm
- 商品画像確認: fitm-cv-do_main.jpg / taikf00_main.jpg を確認。今回はユーザー指示により例外として taikf00 寄せで作成。
- 商品画像の扱い: taikf00 の長めトップス、膝上丈ボトム、黒ベース、アルファベット柄の方向性を参照。ロゴ、商品ページ文字、価格、サイズ表記、モデル顔、商品写真構図は再現しない。
- 既存ページで避ける要素: 015の運動再開心理、017の痩せてから問題とコミカル主人公表現。プールバッグや水面は使うが、本文軸を水中ウォーキングの始めやすさへ変更。
- 今回採用する差別化要素: 水中ウォーキング、泳げない人の入口、水の抵抗、動きやすい服装、準備を軽くする導線。
- 画像差別化チェック: 通常ルールでは無地・汎用寄せにしたが、ユーザー指示により taikf00 のアルファベット柄方向へ差し替え。
- points画像: images/work/018_points.jpg は管理素材。標準TSVには出さない。
"""
    (BASE / "notes.md").write_text(notes, encoding="utf-8")

    make_scenes(["018_title_bg.png", "018_about_bg.png", "018_points_bg.png", "018_water_bg.png", "018_outfit_bg.png", "018_routine_bg.png"])
    make_bgm()
    make_contact_sheet(["018_title.jpg", "018_points.jpg", "018_about.jpg", "018_no_swim.jpg", "018_water.jpg", "018_outfit.jpg", "018_routine.jpg", "018_accent_01.jpg", "018_accent_02.jpg"])


if __name__ == "__main__":
    build()
