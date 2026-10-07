from __future__ import annotations

import csv
import math
import shutil
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "production"
REFS = ROOT / "references" / "generated_032_034"
PROJECT_ROOT = ROOT.parent
LOGO = PROJECT_ROOT / "ゆめはんオリジナル商品マークB.png"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


PAGES = {
    "032": {
        "slug": "neckline_sheer_innerwear_layering",
        "title": "首元だけで服の空気が変わる｜シアーインナーという小さな重ね着",
        "main_title": "首元だけで服の空気が変わる",
        "product_ids": ["clslrb-0", "slksh20"],
        "pattern": "magazine_column",
        "reference_mode": "product_mood",
        "product_reference_level": "level_3_product_mood",
        "lead": [
            "服の印象は、大きなアイテムだけで決まるわけではありません。",
            "ジャケットやカーディガン、シャツの下から少し見える首元。その小さな面積が、全体の空気を変えることがあります。シアーインナーは、主役の服を押しのけず、首元に軽さと奥行きを足してくれる重ね着です。",
            "このコラムでは、薄手のハイネックインナーを、服を整える小さな道具として考えます。",
        ],
        "sections": [
            ("首元は意外と見られる", "鏡を見る時、つい服全体の色や形を気にします。けれど人と話す時に目に入りやすいのは、顔まわりと首元です。\n\n少し開いた襟元に何もないと、服によってはさびしく見えることがあります。反対に、薄手のハイネックが一枚入るだけで、同じ服でも落ち着いた印象になります。"),
            ("重ねても重く見せない", "寒いからと厚手のインナーを足すと、首元や肩まわりがもたつくことがあります。特にジャケットやカーディガンの下では、厚みが出るほど服のラインも変わります。\n\nシアーインナーは、重ね着の安心感を足しながら、見た目を重くしすぎないのが魅力です。"),
            ("白と黒で印象が変わる", "オフホワイトは、顔まわりをやわらかく見せたい時に使いやすい色です。ブラックは、コーディネートを引き締めたい時に頼りになります。\n\n同じハイネックでも、色が変わるだけで服の空気は変わります。手持ちの服に合わせて選ぶと、重ね着が少し楽しくなります。"),
            ("見せるけれど出しすぎない", "透け感という言葉には、少し構えてしまう人もいるかもしれません。けれど大人の重ね着では、肌を見せるためではなく、布の重なりを軽く見せるために使うことができます。\n\n見せるインナーは、目立たせるためだけのものではありません。服と服の間を自然につなぐ、控えめな役割もあります。"),
        ],
        "video_lines": ["首元だけで", "服の空気が変わる", "重ねても重く見せない", "白と黒で印象を変える"],
        "source_roles": ["title", "section_1", "section_2", "section_3", "accent_1"],
    },
    "033": {
        "slug": "ivory_black_sheer_innerwear_set",
        "title": "白と黒を持っておく安心｜迷う朝を減らすシアーインナー2色組",
        "main_title": "白と黒を持っておく安心",
        "product_ids": ["slksh20"],
        "pattern": "magazine_column",
        "reference_mode": "product_mood",
        "product_reference_level": "level_3_product_mood",
        "lead": [
            "朝の服選びで迷うのは、主役の服だけではありません。",
            "首元に何を合わせるか、白がいいのか黒がいいのか。小さなことのようで、ここが決まらないと全体がまとまりにくい日があります。白と黒のシアーインナーを持っておくことは、服選びの迷いを少し減らす準備になります。",
            "このコラムでは、2色組インナーを、朝の支度を助ける道具として見ていきます。",
        ],
        "sections": [
            ("白はやわらかく見せる", "オフホワイトのインナーは、顔まわりにやわらかさを足したい時に使いやすい色です。淡いニットや明るいブラウス、ベージュ系の服とも自然になじみます。\n\n強く主張しないので、首元を少し整えたい日にも向いています。"),
            ("黒は輪郭を整える", "ブラックのインナーは、コーディネートを引き締めたい時に頼りになります。ぼんやり見えがちな服に黒を少し足すと、首元の輪郭が整って見えることがあります。\n\n濃い色のジャケットやカーディガンとも合わせやすく、きちんと感を出したい日に便利です。"),
            ("洗い替えの安心もある", "インナーは肌に近いものなので、洗い替えがあると気持ちが楽です。色違いで持っていると、洗濯中だから選べないという小さな不便も減ります。\n\n派手な便利さではありませんが、毎日の服選びではこうした地味な安心が効いてきます。"),
            ("迷う朝ほど助かる", "時間がない朝ほど、新しい組み合わせに挑戦する余裕はありません。いつもの服に合わせやすい白と黒があると、考える時間を短くできます。\n\nシアーインナー2色組は、おしゃれのためだけではなく、迷う朝を軽くするための準備でもあります。"),
        ],
        "video_lines": ["白と黒を持っておく", "迷う朝が少し軽くなる", "やわらかく見せる白", "輪郭を整える黒"],
        "source_roles": ["title", "section_1", "section_2", "accent_1"],
    },
    "034": {
        "slug": "sheer_innerwear_useful_layering",
        "title": "透けるのに頼れるってどういうこと？｜シアーインナーの距離感",
        "main_title": "透けるのに頼れるってどういうこと？",
        "product_ids": ["clslrb-0", "slksh20"],
        "pattern": "soft_textbook",
        "reference_mode": "product_mood",
        "product_reference_level": "level_3_product_mood",
        "lead": [
            "シアーインナーという言葉を聞くと、少し頼りなさそうに感じるかもしれません。",
            "透け感があるのに、なぜインナーとして使えるのか。そこには、肌を隠すか見せるかだけではない、重ね着ならではの役割があります。薄い布が一枚入ることで、服同士のつながりや首元の印象が整うことがあります。",
            "このコラムでは、シアーインナーの距離感をやわらかく整理します。",
        ],
        "sections": [
            ("透け感は軽さになる", "透ける素材は、肌を強く出すためだけのものではありません。服の中に少し空気を含ませ、重ね着を軽く見せる役割があります。\n\n厚手の服ばかり重ねると重く見える日も、薄いインナーなら首元に抜け感を作れます。"),
            ("一枚で完結させない", "シアーインナーは、一枚で完成させる服というより、重ねて使う服です。シャツ、カーディガン、ジャケットの下に入れることで、見え方が自然になります。\n\n単体で考えるより、手持ちの服とどうつなぐかで選ぶと使いやすくなります。"),
            ("隠すより整える", "インナーというと、隠すためのものと思いがちです。けれどシアーインナーは、隠すだけではなく整える役割もあります。\n\n首元の空き、色のつながり、素材の重なり。小さな部分を整えることで、服全体の印象が落ち着きます。"),
            ("大人の透け感は控えめに", "大人の重ね着では、透け感を強く見せる必要はありません。少しだけ軽さを足す、色をやわらげる、首元をつなぐ。そのくらいの控えめさが使いやすいこともあります。\n\nシアーインナーは、目立つためではなく、服を自然にまとめるために使えるアイテムです。"),
        ],
        "video_lines": ["透けるのに頼れる", "その理由は重ね方にある", "軽さを足す", "首元を整える"],
        "source_roles": ["title", "section_1", "section_2", "accent_1"],
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
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    box = ImageDraw.Draw(img).textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def cover_crop(img: Image.Image, size: tuple[int, int], bias_x: float = 0, bias_y: float = 0) -> Image.Image:
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    max_left = resized.width - tw
    max_top = resized.height - th
    left = round(max_left * (0.5 + bias_x / 2))
    top = round(max_top * (0.5 + bias_y / 2))
    return resized.crop((max(0, min(max_left, left)), max(0, min(max_top, top)), max(0, min(max_left, left)) + tw, max(0, min(max_top, top)) + th))


def glow(w: int, h: int, color=(255, 255, 255), alpha=92) -> Image.Image:
    pad = 64
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (*color, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=30, fill=(*color, alpha))
    return layer.filter(ImageFilter.GaussianBlur(26))


def draw_text_block(img: Image.Image, lines: list[str], x: int, y: int, size: int, fill=(46, 41, 38), gap: int | None = None) -> Image.Image:
    out = img.convert("RGBA")
    font = mincho(size, True)
    gap = gap or round(size * 1.35)
    widths = [text_size(line, font)[0] for line in lines]
    heights = [text_size(line, font)[1] for line in lines]
    gw = max(widths) + 100
    gh = sum(heights) + gap * (len(lines) - 1) + 72
    out.alpha_composite(glow(gw, gh), (x - 54, y - 56))
    draw = ImageDraw.Draw(out)
    cy = y
    for line in lines:
        draw.text((x, cy), line, font=font, fill=(*fill, 255))
        cy += gap
    return out.convert("RGB")


def split_title(title: str) -> list[str]:
    if "｜" in title:
        a, b = title.split("｜", 1)
        return [a, b]
    return [title]


def make_title(src: Path, dst: Path, title: str, no: str) -> None:
    img = cover_crop(Image.open(src).convert("RGB"), (1600, 900), bias_x=0.0)
    lines = split_title(title)
    size = 58 if max(len(x) for x in lines) <= 20 else 50
    img = draw_text_block(img, lines, 84, 124, size, gap=78)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, quality=94)


def make_banner(src: Path, dst: Path, heading: str, body: str, idx: int) -> None:
    bias = [-0.18, 0.18, 0.0, -0.08][idx % 4]
    img = cover_crop(Image.open(src).convert("RGB"), (1600, 520), bias_x=bias)
    lines = [heading]
    sub = body.split("。")[0].replace("\n", "")
    if len(sub) > 24:
        sub = sub[:23] + "…"
    lines.append(sub)
    x = 88 if idx % 2 == 0 else 760
    img = draw_text_block(img, lines, x, 120, 40, gap=58)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, quality=94)


def make_accent(src: Path, dst: Path) -> None:
    img = cover_crop(Image.open(src).convert("RGB"), (1200, 1200))
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, quality=94)


def make_bgm(path: Path) -> None:
    sr = 44100
    duration = 24
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for n in range(sr * duration):
            t = n / sr
            env = min(1, t / 1.2, (duration - t) / 2.0)
            v = 0.16 * env * (math.sin(2 * math.pi * 392 * t) + 0.55 * math.sin(2 * math.pi * 523.25 * t) + 0.35 * math.sin(2 * math.pi * 659.25 * t))
            frames += int(max(-1, min(1, v)) * 32767).to_bytes(2, "little", signed=True)
        wf.writeframes(frames)


def frame_text(frame: Image.Image, lines: list[str], alpha: float, y: int) -> None:
    size = 44
    font = mincho(size, True)
    while size > 30 and any(text_size(line, font)[0] > 620 for line in lines):
        size -= 2
        font = mincho(size, True)
    draw = ImageDraw.Draw(frame)
    a = int(255 * alpha)
    cy = y
    for line in lines:
        w, h = text_size(line, font)
        x = (720 - w) // 2
        g = glow(w + 68, h + 42, color=(255, 255, 255), alpha=138)
        g.putalpha(g.getchannel("A").point(lambda p: int(p * alpha)))
        frame.alpha_composite(g, (x - 50, cy - 36))
        draw.text((x, cy), line, font=font, fill=(48, 42, 38, a))
        cy += 66


def frame_points(frame: Image.Image, points: list[str], alpha: float) -> None:
    title_font = mincho(44, True)
    point_font = mincho(38, True)
    draw = ImageDraw.Draw(frame)
    a = int(255 * alpha)

    title = "このコラムのポイント"
    title_w, title_h = text_size(title, title_font)
    title_x = (720 - title_w) // 2
    title_y = 258
    g = glow(title_w + 92, title_h + 44, color=(255, 255, 255), alpha=132)
    g.putalpha(g.getchannel("A").point(lambda p: int(p * alpha)))
    frame.alpha_composite(g, (title_x - 58, title_y - 38))
    draw.text((title_x, title_y), title, font=title_font, fill=(48, 42, 38, a))

    lines = ["› " + p for p in points[:3]]
    max_w = max((text_size(line, point_font)[0] for line in lines), default=420)
    x = max(92, min(150, (720 - max_w) // 2))
    y = 350
    for line in lines:
        w, h = text_size(line, point_font)
        g = glow(w + 72, h + 38, color=(255, 255, 255), alpha=120)
        g.putalpha(g.getchannel("A").point(lambda p: int(p * alpha)))
        frame.alpha_composite(g, (x - 48, y - 32))
        draw.text((x, y), line, font=point_font, fill=(48, 42, 38, a))
        y += 64


def make_video(base: Path, no: str, page: dict) -> None:
    video_dir = base / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    bgm = video_dir / f"bgm_{no}.wav"
    make_bgm(bgm)
    scene_paths = [
        REFS / f"{no}_title.png",
        REFS / f"{no}_section_1.png",
        REFS / f"{no}_section_2.png",
        REFS / f"{no}_accent_1.png",
    ]
    if no == "033":
        scene_paths = [
            REFS / f"{no}_title.png",
            REFS / f"{no}_section_2.png",
            REFS / f"{no}_section_1.png",
            REFS / f"{no}_accent_1.png",
        ]
    tmp = video_dir / "_frames"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    fps = 24
    duration = 19
    total = fps * duration
    for i in range(total):
        t = i / fps
        scene = min(3, int(t // (duration / 4)))
        local = (t - scene * (duration / 4)) / (duration / 4)
        img = Image.open(scene_paths[scene]).convert("RGB")
        bg = cover_crop(img, (720, 960), bias_x=0.0, bias_y=0.0).convert("RGBA")
        scale = 1.02 + 0.04 * local
        resized = bg.resize((round(720 * scale), round(960 * scale)), Image.Resampling.LANCZOS)
        left = (resized.width - 720) // 2
        top = (resized.height - 960) // 2
        bg = resized.crop((left, top, left + 720, top + 960)).convert("RGBA")
        if scene == 0:
            chars = "".join(page["video_lines"][:2])
            n = min(len(chars), int(len(chars) * max(0, local - 0.12) / 0.55))
            l1, l2 = page["video_lines"][0], page["video_lines"][1]
            shown = []
            rem = n
            if rem > 0:
                shown.append(l1[: min(len(l1), rem)])
                rem -= len(shown[0])
            if rem > 0:
                shown.append(l2[: min(len(l2), rem)])
            frame_text(bg, shown, 1, 338)
        elif scene == 1:
            points = page.get("video_points") or page["video_lines"][1:4]
            frame_points(bg, points, min(1, local * 1.8))
        elif scene == 2:
            frame_text(bg, ["› " + page["video_lines"][2], "› " + page["video_lines"][3]], min(1, local * 1.8), 330)
        else:
            frame_text(bg, [page["main_title"]], max(0, 1 - max(0, local - 0.72) / 0.28), 390)
            if local > 0.78:
                white = Image.new("RGBA", (720, 960), (255, 255, 255, int(255 * min(1, (local - 0.78) / 0.22))))
                bg.alpha_composite(white)
        bg.convert("RGB").save(tmp / f"frame_{i:04d}.jpg", quality=90)
    out = video_dir / f"opening_cm_{no}_vertical.mp4"
    cmd = [
        FFMPEG,
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(tmp / "frame_%04d.jpg"),
        "-i",
        str(bgm),
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        str(out),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    preview = video_dir / f"preview_{no}.jpg"
    cover_frame = min(total - 1, round(fps * 7.8))
    shutil.copyfile(tmp / f"frame_{cover_frame:04d}.jpg", preview)
    shutil.rmtree(tmp)


def write_texts(base: Path, no: str, page: dict) -> None:
    lines = [f"# {page['title']}", ""]
    lines.extend(page["lead"])
    for heading, body in page["sections"]:
        lines.extend(["", f"## {heading}", "", body])
    (base / "page_copy.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    notes = [
        f"# {no} notes",
        f"- title: {page['title']}",
        f"- product_ids: {', '.join(page['product_ids'])}",
        f"- column_pattern: {page['pattern']}",
        f"- reference_mode: {page['reference_mode']}",
        f"- product_reference_level: {page['product_reference_level']}",
        "- 商品画像確認: 楽天CSVと参照画像から、薄手リブ、長袖、ハイネック、メロウ気味の首元と袖口、オフホワイト/ブラックの方向性を確認。",
        "- 商品寄せ: level_3_product_mood。商品写真そのもの、モデル、文字、価格、サイズ表記、商品ページ構図は再現しない。",
        "- 画像品質チェック: 生成画像を元画像として使用。簡易図形、素材シート切り出し、商品画像混入なし。",
    ]
    (base / "notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_tsv(base: Path, no: str, page: dict) -> None:
    url = "https://image.rakuten.co.jp/u-b-yumehan/cabinet/contents/"
    rows = []
    idx = 1
    rows.append([idx, "画像", f"{url}{no}_title.jpg"]); idx += 1
    rows.append([idx, "メインタイトル", page["main_title"]]); idx += 1
    rows.append([idx, "動画", f"{no}_opening_cm_vertical.mp4"]); idx += 1
    rows.append([idx, "本文", "\n" + "\n".join(page["lead"])]); idx += 1
    for s_idx, (heading, body) in enumerate(page["sections"], start=1):
        rows.append([idx, "小タイトル", heading]); idx += 1
        rows.append([idx, "画像", f"{url}{no}_section_{s_idx:02d}.jpg"]); idx += 1
        rows.append([idx, "本文", "\n" + body]); idx += 1
        if s_idx in (2, 4):
            if s_idx == 2:
                rows.append([idx, "画像", f"{url}{no}_accent_01.jpg"]); idx += 1
            elif (REFS / f"{no}_accent_2.png").exists():
                rows.append([idx, "画像", f"{url}{no}_accent_02.jpg"]); idx += 1
    for pid in page["product_ids"]:
        rows.append([idx, "関連商品", pid]); idx += 1
    with (base / "page_paste_blocks.tsv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["row", "part_type", "content"])
        writer.writerows(rows)


def build_page(no: str, page: dict) -> None:
    base = PRODUCTION / f"{no}_{page['slug']}" / "納品用"
    (base / "images" / "delivery").mkdir(parents=True, exist_ok=True)
    (base / "images" / "work" / "generated_originals").mkdir(parents=True, exist_ok=True)
    (base / "data").mkdir(parents=True, exist_ok=True)
    source_roles = list(page["source_roles"])
    if (REFS / f"{no}_accent_2.png").exists() and "accent_2" not in source_roles:
        source_roles.append("accent_2")
    for role in source_roles:
        src = REFS / f"{no}_{role}.png"
        if not src.exists():
            raise FileNotFoundError(src)
        shutil.copyfile(src, base / "images" / "work" / "generated_originals" / src.name)
    delivery = base / "images" / "delivery"
    make_title(REFS / f"{no}_title.png", delivery / f"{no}_title.jpg", page["title"], no)
    section_sources = [
        REFS / f"{no}_section_1.png",
        REFS / f"{no}_section_2.png",
        REFS / f"{no}_section_3.png",
        REFS / f"{no}_accent_1.png",
        REFS / f"{no}_title.png",
    ]
    section_sources = [p for p in section_sources if p.exists()]
    for i, (heading, body) in enumerate(page["sections"], start=1):
        make_banner(section_sources[(i - 1) % len(section_sources)], delivery / f"{no}_section_{i:02d}.jpg", heading, body, i)
    make_accent(REFS / f"{no}_accent_1.png", delivery / f"{no}_accent_01.jpg")
    accent_2 = REFS / f"{no}_accent_2.png"
    if accent_2.exists():
        make_accent(accent_2, delivery / f"{no}_accent_02.jpg")
    write_texts(base, no, page)
    write_tsv(base, no, page)
    write_csv(base / "product_ids.csv", ["product_id"], [{"product_id": pid} for pid in page["product_ids"]])
    banner_rows = [{"banner_no": str(i), "file": f"{no}_section_{i:02d}.jpg", "heading": h, "reference_mode": page["reference_mode"], "product_reference_level": page["product_reference_level"]} for i, (h, _b) in enumerate(page["sections"], start=1)]
    write_csv(base / "data" / "banner_plan.csv", ["banner_no", "file", "heading", "reference_mode", "product_reference_level"], banner_rows)
    make_video(base, no, page)


def main() -> None:
    for no, page in PAGES.items():
        build_page(no, page)


if __name__ == "__main__":
    main()
