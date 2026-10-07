import csv
import html
import io
import math
import pathlib
import re
import subprocess
import urllib.request
import wave

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = pathlib.Path(r"C:\Users\i58400am\Desktop\newapp")
CSV_PATH = ROOT / "Yahoo!" / "data202608061154.csv"
BASE = ROOT / "楽天コンテンツページ群" / "027_着るだけで痩せるはありえない_それでも補正下着を使う意味"
OUT = BASE / "納品用"
IMAGES = OUT / "images"
BANNERS = OUT / "banners"
PRODUCT_IMAGES = OUT / "product_images"
SCENES = OUT / "scene_images"
VIDEO = OUT / "video"

TITLE = "着るだけで痩せる、はありえない｜それでも補正下着を使う意味"
CODES = ["nbdbr20", "fcpg20", "slkshm00", "lerkb00", "nbdbr00"]
RAKUTEN_SHOP = "https://item.rakuten.co.jp/u-b-yumehan/"

WIDE = (1600, 900)
BANNER = (1600, 520)
SQUARE = (1000, 1000)
INK = (64, 45, 52, 255)
MUTED = (104, 82, 88, 245)
ROSE = (168, 94, 112, 255)
CREAM = (252, 246, 241, 255)
BLACK = (31, 28, 30, 255)


def read_csv_text(path):
    data = path.read_bytes()
    for enc in ("cp932", "shift_jis", "utf-8-sig", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("cp932", "replace")


def clean(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def yen(value):
    value = re.sub(r"[^\d]", "", value or "")
    return int(value) if value else 0


def font(size, style="mincho"):
    if style == "mincho_light":
        names = [r"C:\Windows\Fonts\yuminl.ttf", r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc"]
    elif style == "mincho":
        names = [r"C:\Windows\Fonts\yumin.ttf", r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc"]
    elif style == "gothic_light":
        names = [r"C:\Windows\Fonts\YuGothL.ttc", r"C:\Windows\Fonts\meiryo.ttc"]
    else:
        names = [r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc"]
    for name in names:
        p = pathlib.Path(name)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


F92 = font(92, "mincho_light")
F74 = font(74, "mincho_light")
F60 = font(60, "mincho")
F48 = font(48, "mincho")
F40 = font(40, "mincho")
F32 = font(32, "gothic_light")
F26 = font(26, "gothic_light")


def ensure_dirs():
    for d in (IMAGES, BANNERS, PRODUCT_IMAGES, SCENES, VIDEO):
        d.mkdir(parents=True, exist_ok=True)


def load_products():
    rows = list(csv.DictReader(io.StringIO(read_csv_text(CSV_PATH))))
    products = {}
    for r in rows:
        code = (r.get("code") or "").strip()
        if code not in CODES:
            continue
        urls = [u.strip() for u in (r.get("item-image-urls") or "").split(";") if u.strip()]
        products[code] = {
            "code": code,
            "name": clean(r.get("name")),
            "price": yen(r.get("sale-price") or r.get("price")),
            "explanation": clean(r.get("explanation")),
            "image_url": urls[0] if urls else "",
            "rakuten_url": f"{RAKUTEN_SHOP}{code}/",
        }
    return [products[c] for c in CODES if c in products]


def download_product_images(products):
    for p in products:
        path = PRODUCT_IMAGES / f"{p['code']}.jpg"
        p["image_path"] = path
        if path.exists() and path.stat().st_size > 1000:
            continue
        if not p["image_url"]:
            continue
        req = urllib.request.Request(p["image_url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            path.write_bytes(r.read())


def text_size(draw, text, fnt):
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw, text, fnt, max_w):
    lines = []
    for raw in text.split("\n"):
        buf = ""
        for ch in raw:
            if text_size(draw, buf + ch, fnt)[0] <= max_w:
                buf += ch
            else:
                if buf:
                    lines.append(buf)
                buf = ch
        if buf:
            lines.append(buf)
    return lines


def draw_lines(draw, xy, text, fnt, fill, max_w, gap=14, align="left"):
    x, y = xy
    for line in wrap_text(draw, text, fnt, max_w):
        tw, th = text_size(draw, line, fnt)
        dx = x if align == "left" else x + (max_w - tw) / 2
        draw.text((dx, y), line, font=fnt, fill=fill)
        y += th + gap
    return y


def editorial_bg(size, mode):
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    x = np.linspace(0, 1, w)
    y = np.linspace(0, 1, h)
    xx, yy = np.meshgrid(x, y)
    if mode == "dark":
        c1 = np.array([44, 38, 43])
        c2 = np.array([185, 142, 145])
    elif mode == "warm":
        c1 = np.array([252, 245, 239])
        c2 = np.array([218, 181, 172])
    elif mode == "urban":
        c1 = np.array([242, 237, 233])
        c2 = np.array([115, 92, 100])
    else:
        c1 = np.array([250, 246, 242])
        c2 = np.array([210, 196, 188])
    mix = np.clip((xx * 0.75 + yy * 0.55), 0, 1)
    arr[:] = (c1 * (1 - mix[..., None]) + c2 * mix[..., None]).astype(np.uint8)
    img = Image.fromarray(arr, "RGB").convert("RGBA")
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(16):
        x0 = int(-100 + i * w / 8)
        y0 = int(h * 0.1 + (i % 4) * h * 0.18)
        d.ellipse((x0, y0, x0 + 440, y0 + 180), fill=(255, 255, 255, 22))
    d.rectangle((0, int(h * 0.72), w, h), fill=(255, 255, 255, 70))
    return Image.alpha_composite(img, layer)


def add_product_strip(img, products, area):
    x0, y0, x1, y1 = area
    slot_w = (x1 - x0) // max(1, len(products))
    for i, p in enumerate(products):
        try:
            pic = Image.open(p["image_path"]).convert("RGBA")
        except Exception:
            continue
        pic.thumbnail((slot_w - 40, y1 - y0 - 40), Image.LANCZOS)
        card = Image.new("RGBA", (slot_w - 20, y1 - y0), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((12, 12, card.width - 12, card.height - 12), radius=26, fill=(255, 255, 255, 232))
        card.alpha_composite(pic, ((card.width - pic.width) // 2, 26))
        img.alpha_composite(card, (x0 + i * slot_w + 10, y0))
    return img


def save_jpg(img, path):
    img.convert("RGB").save(path, quality=92, optimize=True)


def make_hero(products):
    img = editorial_bg(WIDE, "warm")
    d = ImageDraw.Draw(img)
    d.rectangle((80, 0, 760, WIDE[1]), fill=(255, 255, 255, 128))
    draw_lines(d, (118, 150), "お肉は\n消えません。", F92, BLACK, 590, gap=8)
    draw_lines(d, (124, 390), "それでも、服のラインは整えられる。\n補正下着との現実的な付き合い方。", F40, INK, 620, gap=18)
    save_jpg(img, IMAGES / "001_first_view.jpg")


def make_section_images(products):
    specs = [
        ("002_column_mood.jpg", "dark", "着るだけで痩せる？\nその期待はいったん置いてみる。", "本音から始める補正下着コラム"),
        ("003_line_check.jpg", "urban", "変わるのは体重ではなく、\n服を着たときのシルエット。", "お腹・腰・ヒップまわりの見え方を整える"),
        ("004_material_check.jpg", "warm", "続かない補正は、\n結局タンスに戻ります。", "苦しさ・素材・丈を購入前にチェック"),
        ("005_product_pickup.jpg", "light", "商品は、目的で選ぶ。", "ボディブリファー、ガードル、シルク腹巻、骨盤ベルト"),
    ]
    for filename, mode, title, sub in specs:
        img = editorial_bg(WIDE, mode)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, WIDE[0], WIDE[1]), fill=(255, 255, 255, 70 if mode != "dark" else 20))
        draw_lines(d, (120, 190), title, F74, BLACK if mode != "dark" else (255, 255, 255, 245), 820, gap=14)
        draw_lines(d, (126, 430), sub, F32, MUTED if mode != "dark" else (255, 245, 242, 220), 760, gap=14)
        save_jpg(img, IMAGES / filename)


def make_banner(filename, title, body, mode="warm"):
    img = editorial_bg(BANNER, mode)
    d = ImageDraw.Draw(img)
    d.rectangle((70, 70, 1530, 450), fill=(255, 255, 255, 178))
    d.line((116, 252, 1484, 252), fill=(150, 105, 114, 120), width=2)
    draw_lines(d, (116, 115), title, F60, INK, 1320, gap=8, align="center")
    draw_lines(d, (180, 292), body, F32, MUTED, 1240, gap=12, align="center")
    save_jpg(img, BANNERS / filename)


def make_banners():
    make_banner(
        "01_honest_banner.jpg",
        "着るだけで痩せる、はありえない",
        "補正下着は体を消すものではなく、服のラインを整えるための道具です。",
        "dark",
    )
    make_banner(
        "02_reality_check_banner.jpg",
        "補正下着で見るべき3つ",
        "苦しすぎないこと / 服に響きにくいこと / 続けられること",
        "urban",
    )
    make_banner(
        "03_choice_banner.jpg",
        "目的で選ぶと失敗しにくい",
        "お腹まわり、腰、ヒップ、冷え対策。まずは使いたい場面を決める。",
        "warm",
    )
    make_banner(
        "04_cta_banner.jpg",
        "きれい見えは、無理しないところから",
        "毎日使える補正下着を、素材と形で見比べましょう。",
        "light",
    )


def make_scene_images(products):
    scene_specs = [
        ("01_title.png", "dark", "お肉は\n消えません", "でも、服のラインは整えられる"),
        ("02_hook.png", "warm", "きれいごと抜きで", "補正下着のリアルな話"),
        ("03_toc.png", "urban", "今日の目次", "痩せる？ / 苦しい？ / どう選ぶ？"),
        ("04_truth.png", "dark", "着るだけで痩せる\nは、言いすぎ", "期待値を整える"),
        ("05_pickup.png", "light", "目的で選ぶ", "ボディブリファー / ガードル / 腹巻"),
        ("06_cta.png", "warm", "無理しない\nきれい見えへ", "本文で詳しく"),
    ]
    for filename, mode, title, sub in scene_specs:
        img = editorial_bg(SQUARE, mode)
        d = ImageDraw.Draw(img)
        if mode != "dark":
            d.rectangle((0, 0, SQUARE[0], SQUARE[1]), fill=(255, 255, 255, 58))
        if filename == "05_pickup.png":
            add_product_strip(img, products[:3], (145, 610, 855, 930))
        img.save(SCENES / filename)


def ease(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def cover_square(path, scale=1.0, dx=0, dy=0):
    img = Image.open(path).convert("RGBA")
    ratio = max(SQUARE[0] / img.width, SQUARE[1] / img.height) * scale
    img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    x = (img.width - SQUARE[0]) // 2 + dx
    y = (img.height - SQUARE[1]) // 2 + dy
    x = max(0, min(x, img.width - SQUARE[0]))
    y = max(0, min(y, img.height - SQUARE[1]))
    return img.crop((x, y, x + SQUARE[0], y + SQUARE[1]))


def animate_text(base, title, sub, t, mode):
    layer = Image.new("RGBA", SQUARE, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    alpha = int(255 * min(1, t / 0.28) * (1 if t < 0.88 else max(0, (1 - t) / 0.12)))
    y_shift = int((1 - ease(min(1, t / 0.55))) * 26)
    color = (255, 255, 255, alpha) if mode == "dark" else (31, 28, 30, alpha)
    subc = (255, 240, 240, int(alpha * 0.88)) if mode == "dark" else (94, 73, 80, int(alpha * 0.88))
    if mode != "dark":
        d.rectangle((0, 385, 1000, 625), fill=(255, 255, 255, int(alpha * 0.58)))
    draw_lines(d, (88, 405 - y_shift), title, F60, color, 825, gap=12)
    draw_lines(d, (96, 595 - y_shift), sub, F26, subc, 800, gap=10)
    return Image.alpha_composite(base, layer)


def product_float_frame(products, t):
    img = editorial_bg(SQUARE, "light")
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 1000, 1000), fill=(255, 255, 255, 72))
    title = "目的で選ぶ"
    sub = "お腹・腰・ヒップ。気になる場所から"
    draw_lines(d, (90, 110), title, F60, BLACK, 820, gap=12)
    draw_lines(d, (96, 226), sub, F26, MUTED, 800, gap=10)
    show = products[:4]
    if not show:
        return img
    cycle = min(0.999, t) * len(show)
    active = min(len(show) - 1, int(cycle))
    local = cycle - active
    p = show[active]
    try:
        pic = Image.open(p["image_path"]).convert("RGBA")
    except Exception:
        return img
    pic.thumbnail((560, 560), Image.LANCZOS)
    presence = ease(min(1, local / 0.22)) * ease(min(1, (1 - local) / 0.18))
    scale = 0.92 + 0.08 * ease(local)
    card = Image.new("RGBA", (660, 600), (0, 0, 0, 0))
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((54, 42, 606, 568), radius=30, fill=(70, 45, 52, int(45 * presence)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    card.alpha_composite(shadow)
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((42, 32, 618, 558), radius=24, fill=(255, 255, 255, int(248 * presence)))
    pw = int(pic.width * scale)
    ph = int(pic.height * scale)
    pic = pic.resize((pw, ph), Image.LANCZOS)
    card.alpha_composite(pic, ((card.width - pw) // 2, 58))
    card.putalpha(card.split()[-1].point(lambda v: int(v * presence)))
    y = int(335 - 24 * math.sin(math.pi * ease(local)))
    img.alpha_composite(card, (170, y))
    return img


def make_bgm(seconds, path):
    rate = 44100
    n = int(seconds * rate)
    t = np.linspace(0, seconds, n, endpoint=False)
    audio = np.zeros(n, dtype=np.float32)
    chords = [
        [220.00, 277.18, 329.63],
        [196.00, 246.94, 293.66],
        [174.61, 220.00, 261.63],
        [246.94, 311.13, 369.99],
    ]
    for i, notes in enumerate(chords * 2):
        start = i * 2.35
        start_i = int(start * rate)
        end_i = min(n, start_i + int(2.6 * rate))
        if start_i >= n:
            break
        local = np.linspace(0, (end_i - start_i) / rate, end_i - start_i, endpoint=False)
        env = np.minimum(1, local / 0.35) * np.minimum(1, (local[-1] - local + 0.001) / 0.7)
        for note in notes:
            audio[start_i:end_i] += 0.037 * np.sin(2 * np.pi * note * local) * env
    beat = np.sin(2 * np.pi * 2.1 * t)
    audio += 0.015 * np.sign(beat) * (beat > 0.92)
    melody = [440.0, 493.88, 554.37, 493.88, 392.0, 440.0]
    for i, note in enumerate(melody * 4):
        start = 0.55 + i * 0.72
        start_i = int(start * rate)
        end_i = min(n, start_i + int(0.55 * rate))
        if start_i >= n:
            break
        local = np.linspace(0, (end_i - start_i) / rate, end_i - start_i, endpoint=False)
        env = np.exp(-5.0 * local)
        audio[start_i:end_i] += 0.07 * np.sin(2 * np.pi * note * local) * env
    audio *= np.minimum(1, t / 0.9)
    audio *= np.minimum(1, (seconds - t) / 1.3)
    audio = np.clip(audio, -0.9, 0.9)
    pcm = (audio * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())


def make_video(products):
    fps = 30
    scenes = [
        ("01_title.png", "お肉は消えません", "でも、服のラインは整えられる", "dark", 3.0, "in"),
        ("02_hook.png", "きれいごと抜きで", "補正下着のリアルな話", "warm", 2.6, "right"),
        ("03_toc.png", "今日の目次", "痩せる？ 苦しい？ どう選ぶ？", "urban", 2.7, "left"),
        ("04_truth.png", "着るだけで痩せる、は言いすぎ", "期待値を整える", "dark", 2.8, "up"),
        ("05_pickup.png", "目的で選ぶ", "お腹・腰・ヒップ。気になる場所から", "light", 3.0, "in"),
        ("06_cta.png", "無理しないきれい見えへ", "本文で詳しく", "warm", 3.0, "right"),
    ]
    silent = VIDEO / "v1_magazine_cm_silent.mp4"
    final = VIDEO / "v1_magazine_cm_bgm_17sec.mp4"
    bgm = VIDEO / "v1_urban_editorial_pop_bgm.wav"
    writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*"mp4v"), fps, SQUARE)
    prev = None
    for filename, title, sub, mode, seconds, direction in scenes:
        frames = int(seconds * fps)
        for i in range(frames):
            t = i / max(1, frames - 1)
            if filename == "05_pickup.png":
                frame = np.array(product_float_frame(products, t).convert("RGB"))
            else:
                dx = int((ease(t) - 0.5) * 30) if direction in ("left", "right") else 0
                if direction == "left":
                    dx *= -1
                dy = int((ease(t) - 0.5) * 24) if direction == "up" else 0
                base = cover_square(SCENES / filename, 1.05 + 0.035 * ease(t), dx, dy)
                frame = np.array(animate_text(base, title, sub, t, mode).convert("RGB"))
            if prev is not None:
                fade = min(1, i / 10)
                frame = (prev.astype(np.float32) * (1 - fade) + frame.astype(np.float32) * fade).astype(np.uint8)
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            prev = frame
    writer.release()
    make_bgm(sum(s[4] for s in scenes), bgm)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, "-y", "-i", str(silent), "-i", str(bgm), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(final)], check=True)
    cap = cv2.VideoCapture(str(final))
    for sec in (1, 4, 7, 10, 13, 16):
        cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
        ok, frame = cap.read()
        if ok:
            ok, encoded = cv2.imencode(".jpg", frame)
            if ok:
                (VIDEO / f"preview_{sec}s.jpg").write_bytes(encoded.tobytes())
    cap.release()


def product_summary(p):
    name = p["name"]
    if p["code"].startswith("nbdbr"):
        return "胸元から腰まわりまでカバーするボディブリファー。服の下でラインを整えたい日に。"
    if p["code"] == "fcpg20":
        return "ハイウエストタイプのガードル。お腹まわりやヒップラインをすっきり見せたい日に。"
    if p["code"] == "slkshm00":
        return "薄手のシルク腹巻。冷え対策や腰まわりをやさしく整えたい日に。"
    if p["code"] == "lerkb00":
        return "骨盤まわりを支えるベルト。産後や姿勢まわりが気になる日のサポートに。"
    return name[:80]


def make_html(products):
    product_blocks = []
    for p in products:
        img = f"product_images/{p['code']}.jpg"
        product_blocks.append(f"""
    <div class="rb-product">
      <img src="{img}" alt="{html.escape(p['name'])}" width="100%">
      <h3>{html.escape(p['name'])}</h3>
      <p>{html.escape(product_summary(p))}</p>
      <p class="rb-price">参考価格：{p['price']:,}円</p>
      <p><a href="{p['rakuten_url']}">商品を見る</a></p>
    </div>""")

    body = f"""<div class="rb-content rb-content-027">
  <section>
    <img src="images/001_first_view.jpg" alt="{TITLE}" width="100%">
    <h1>{TITLE}</h1>
    <p>「補正下着を着れば痩せる」。そんな魔法みたいな話は、残念ながらありません。お肉がどこかへ消えるわけでも、体重が急に減るわけでもないからです。</p>
    <p>でも、補正下着にはきちんと役割があります。服を着たときのラインを整えること、気になる部分をやさしく支えること、そして“今日はこの服を着よう”と思える気持ちを少し後押しすること。ここでは、きれいごと抜きで補正下着との現実的な付き合い方を考えます。</p>
  </section>

  <section>
    <video src="video/v1_magazine_cm_bgm_17sec.mp4" controls playsinline muted width="100%"></video>
  </section>

  <section>
    <img src="banners/01_honest_banner.jpg" alt="着るだけで痩せる、はありえない" width="100%">
    <h2>まず、期待値を整える</h2>
    <p>補正下着は体を細く作り替えるものではありません。実際にできるのは、やわらかい部分を支えたり、服の下で段差をなだらかにしたり、姿勢や着用感を意識しやすくすることです。</p>
    <p>だからこそ「痩せ見え」という言葉だけで選ぶより、どの服を着る日に、どの部分を整えたいのかを決めて選ぶ方が失敗しにくくなります。</p>
  </section>

  <section>
    <img src="images/002_column_mood.jpg" alt="本音から始める補正下着コラム" width="100%">
    <h2>補正下着を使う意味は、体重ではなく服の見え方</h2>
    <p>たとえばワンピースの腰まわり、薄手パンツのお腹まわり、ニットの背中や脇。気になるポイントは人によって違います。補正下着は、その日の服に合わせて“表面を整える道具”と考えると選びやすくなります。</p>
    <p>大切なのは、苦しさを我慢してまで着ないこと。長く使える一枚は、締め付けの強さよりも、座る、歩く、食事をする、といった日常の動きに合うかどうかで決まります。</p>
  </section>

  <section>
    <img src="banners/02_reality_check_banner.jpg" alt="補正下着で見るべき3つ" width="100%">
    <h2>買う前に見るポイント</h2>
    <ul>
      <li><strong>お腹まわり：</strong>ハイウエストや幅広設計なら、ウエストまわりの段差を整えやすい。</li>
      <li><strong>腰・ヒップ：</strong>ヒップラインを整えたい日は、ガードルや骨盤まわりのサポートタイプを確認。</li>
      <li><strong>上半身：</strong>胸元からお腹、腰まで一体で整えたい日はボディブリファーも選択肢。</li>
      <li><strong>冷え対策：</strong>薄手の腹巻やシルク素材は、補正感より心地よさ重視の日に。</li>
    </ul>
  </section>

  <section>
    <img src="images/003_line_check.jpg" alt="服のラインを整える" width="100%">
    <h2>「苦しいほど効く」は、毎日には向きません</h2>
    <p>補正力が強いほど良い、とは限りません。強すぎる締め付けは、座ったときに苦しくなったり、食い込みや段差が目立ったり、結局使わなくなる原因になります。</p>
    <p>日常使いなら、ほどよく支える、服に響きにくい、脱ぎ着しやすい。この3つを優先するのがおすすめです。</p>
  </section>

  <section>
    <img src="banners/03_choice_banner.jpg" alt="目的で選ぶと失敗しにくい" width="100%">
    <h2>目的別の選び方</h2>
    <table>
      <tr><th>目的</th><th>選びやすいタイプ</th><th>見るポイント</th></tr>
      <tr><td>上半身から腰まで整えたい</td><td>ボディブリファー</td><td>伸縮性、肩まわり、クロッチの仕様</td></tr>
      <tr><td>お腹・ヒップを整えたい</td><td>ガードル</td><td>丈、ウエスト位置、座った時の苦しさ</td></tr>
      <tr><td>腰まわりをやさしく包みたい</td><td>腹巻・薄手サポート</td><td>素材、厚み、季節に合うか</td></tr>
      <tr><td>骨盤まわりを支えたい</td><td>骨盤ベルト</td><td>サイズ、着脱、日常動作との相性</td></tr>
    </table>
  </section>

  <section>
    <img src="images/005_product_pickup.jpg" alt="補正下着の商品ピックアップ" width="100%">
    <h2>記事の内容から選ぶピックアップ商品</h2>
    <div class="rb-products">
{''.join(product_blocks)}
    </div>
  </section>

  <section>
    <h2>よくある質問</h2>
    <h3>補正下着で痩せますか？</h3>
    <p>補正下着そのもので体重が減るわけではありません。服を着たときのラインを整えるものとして考えるのが自然です。</p>
    <h3>きついサイズを選んだ方が効果がありますか？</h3>
    <p>小さすぎるサイズは苦しさや食い込みにつながります。毎日使うなら、対応サイズと着用シーンに合うものを選びましょう。</p>
    <h3>まず何から試すのが良いですか？</h3>
    <p>気になる場所が決まっているなら、その部分に合うタイプから。服の下で全体を整えたいならボディブリファー、お腹まわりならガードル、冷えが気になるなら腹巻タイプが選びやすいです。</p>
  </section>

  <section>
    <img src="banners/04_cta_banner.jpg" alt="きれい見えは無理しないところから" width="100%">
    <h2>まとめ</h2>
    <p>補正下着は、体を変える魔法ではありません。でも、服の見え方や着る日の気分を整える道具にはなります。大切なのは、無理な締め付けではなく、自分の目的に合った一枚を選ぶことです。</p>
    <p><a href="{RAKUTEN_SHOP}fcpg20/">ガードル・補正インナーを見比べる</a></p>
  </section>
</div>
"""
    (OUT / "content_page_completed.html").write_text(body, encoding="utf-8")


def make_upload_guide(products):
    guide = f"""# 027 納品データ

## コンテンツタイトル

{TITLE}

## 納品ファイル

- HTML: `content_page_completed.html`
- 動画: `video/v1_magazine_cm_bgm_17sec.mp4`
- 動画プレビュー: `video/preview_*.jpg`
- ファーストビュー・本文画像: `images/*.jpg`
- 差し込みバナー: `banners/*.jpg`
- 商品画像: `product_images/*.jpg`

## 動画の考え方

商品説明を詰め込まず、雑誌CMのように気になる目次を短く見せる構成です。

1. お肉は消えません
2. きれいごと抜きで
3. 今日の目次
4. 着るだけで痩せる、は言いすぎ
5. 目的で選ぶ
6. 無理しないきれい見えへ

## 商品紹介の扱い

本文では「着るだけで痩せる」などの過剰表現は避け、服のラインを整える、目的で選ぶ、続けやすさを見る、という流れで自然に商品へつなぎます。

## 代表商品

{chr(10).join(f"- `{p['code']}` {p['name'][:80]} / {p['price']:,}円" for p in products)}
"""
    (OUT / "upload_guide.md").write_text(guide, encoding="utf-8")


def main():
    ensure_dirs()
    products = load_products()
    download_product_images(products)
    make_hero(products)
    make_section_images(products)
    make_banners()
    make_scene_images(products)
    make_video(products)
    make_html(products)
    make_upload_guide(products)
    print(OUT)


if __name__ == "__main__":
    main()
