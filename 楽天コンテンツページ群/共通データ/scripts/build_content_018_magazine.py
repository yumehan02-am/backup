import csv
import html
import io
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
BASE = ROOT / "楽天コンテンツページ群" / "018_静電気が起きやすい素材_起きにくい素材_冬インナーの組み合わせ講座"
OUT = BASE / "納品用"
IMAGES = OUT / "images"
BANNERS = OUT / "banners"
PRODUCT_IMAGES = OUT / "product_images"
SCENES = OUT / "scene_images"
SCENE_BACKGROUNDS = OUT / "scene_backgrounds"
VIDEO = OUT / "video"

TITLE = "静電気が起きやすい素材、起きにくい素材｜冬インナーの組み合わせ講座"
CODES = ["80g7b20", "80smb20", "yumeh-3btm", "clmhn3", "gz5bt30"]
RAKUTEN_SHOP = "https://item.rakuten.co.jp/u-b-yumehan/"

WIDE = (1600, 900)
BANNER = (1600, 520)
SQUARE = (1000, 1000)
INK = (50, 52, 55, 255)
MUTED = (92, 88, 82, 245)
WHITE = (255, 255, 255, 255)


def read_csv_text(path):
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", "replace")


def clean(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def yen(value):
    value = re.sub(r"[^\d]", "", value or "")
    return int(value) if value else 0


def font(size, style="mincho"):
    table = {
        "mincho_light": [r"C:\Windows\Fonts\yuminl.ttf", r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc"],
        "mincho": [r"C:\Windows\Fonts\yumin.ttf", r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc"],
        "gothic": [r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc"],
    }
    for name in table[style]:
        if pathlib.Path(name).exists():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default()


F92 = font(92, "mincho_light")
F72 = font(72, "mincho_light")
F58 = font(58, "mincho")
F32 = font(32, "gothic")
F26 = font(26, "gothic")


def ensure_dirs():
    for d in (IMAGES, BANNERS, PRODUCT_IMAGES, SCENES, SCENE_BACKGROUNDS, VIDEO):
        d.mkdir(parents=True, exist_ok=True)


def load_products():
    found = {}
    for row in csv.DictReader(io.StringIO(read_csv_text(CSV_PATH))):
        code = (row.get("code") or "").strip()
        if code not in CODES:
            continue
        urls = [u.strip() for u in (row.get("item-image-urls") or "").split(";") if u.strip()]
        found[code] = {
            "code": code,
            "name": clean(row.get("name")),
            "price": yen(row.get("sale-price") or row.get("price")),
            "image_url": urls[0] if urls else "",
            "rakuten_url": f"{RAKUTEN_SHOP}{code}/",
        }
    return [found[c] for c in CODES if c in found]


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


def wrap(draw, text, fnt, max_w):
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
    for line in wrap(draw, text, fnt, max_w):
        tw, th = text_size(draw, line, fnt)
        dx = x if align == "left" else x + (max_w - tw) / 2
        draw.text((dx, y), line, font=fnt, fill=fill)
        y += th + gap
    return y


def bg(size, mode="warm"):
    w, h = size
    x = np.linspace(0, 1, w)
    y = np.linspace(0, 1, h)
    xx, yy = np.meshgrid(x, y)
    palettes = {
        "warm": (np.array([249, 244, 237]), np.array([214, 204, 190])),
        "blue": (np.array([235, 244, 247]), np.array([128, 159, 176])),
        "dark": (np.array([38, 43, 49]), np.array([110, 132, 145])),
        "cotton": (np.array([253, 251, 247]), np.array([225, 219, 207])),
    }
    c1, c2 = palettes[mode]
    mix = np.clip(xx * 0.72 + yy * 0.5, 0, 1)
    arr = (c1 * (1 - mix[..., None]) + c2 * mix[..., None]).astype(np.uint8)
    img = Image.fromarray(arr, "RGB").convert("RGBA")
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(12):
        x0 = int(-120 + i * w / 6)
        y0 = int((i % 5) * h / 5)
        d.line((x0, y0, x0 + 420, y0 + 130), fill=(255, 255, 255, 30), width=6)
    d.rectangle((0, int(h * 0.72), w, h), fill=(255, 255, 255, 62))
    return Image.alpha_composite(img, layer)


def generated_bg(size, filename, mode="warm"):
    src_path = SCENE_BACKGROUNDS / filename
    if not src_path.exists():
        return bg(size, mode)
    src = Image.open(src_path).convert("RGBA")
    w, h = size
    ratio = max(w / src.width, h / src.height)
    src = src.resize((int(src.width * ratio), int(src.height * ratio)), Image.LANCZOS)
    x = (src.width - w) // 2
    y = (src.height - h) // 2
    img = src.crop((x, y, x + w, y + h))
    if mode == "dark":
        img = Image.alpha_composite(img, Image.new("RGBA", size, (0, 0, 0, 52)))
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if mode == "dark":
        d.rectangle((0, 0, w, h), fill=(0, 0, 0, 18))
    return Image.alpha_composite(img, layer)


def save_jpg(img, path):
    img.convert("RGB").save(path, quality=92, optimize=True)


def add_products(img, products, area):
    x0, y0, x1, y1 = area
    slot = (x1 - x0) // max(1, len(products))
    for i, p in enumerate(products):
        try:
            pic = Image.open(p["image_path"]).convert("RGBA")
        except Exception:
            continue
        pic.thumbnail((slot - 40, y1 - y0 - 40), Image.LANCZOS)
        card = Image.new("RGBA", (slot - 20, y1 - y0), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((10, 10, card.width - 10, card.height - 10), radius=22, fill=(255, 255, 255, 236))
        card.alpha_composite(pic, ((card.width - pic.width) // 2, 28))
        img.alpha_composite(card, (x0 + i * slot + 10, y0))


def make_images(products):
    specs = [
        ("001_first_view.jpg", "blue", "静電気が\n起きやすい素材、\n起きにくい素材", "冬インナーの組み合わせ講座"),
        ("002_static_story.jpg", "dark", "パチッとくる日には、\n理由があります。", "素材の組み合わせで変わる冬の不快感"),
        ("003_material_map.jpg", "cotton", "仲良し素材と、\nケンカしやすい素材。", "重ね着前に知っておきたい相性表"),
        ("004_winter_inner.jpg", "warm", "肌に近い一枚を\n変えてみる。", "綿、ガーゼ、なめらかな素材の考え方"),
        ("005_product_pickup.jpg", "cotton", "商品は素材と季節で選ぶ", "冬のボトム、肌着、ハイネックインナー"),
    ]
    for filename, mode, title, sub in specs:
        img = generated_bg(WIDE, filename.replace(".jpg", ".png"), mode)
        d = ImageDraw.Draw(img)
        fill = WHITE if mode == "dark" else INK
        sub_fill = (235, 240, 244, 230) if mode == "dark" else MUTED
        draw_lines(d, (110, 155), title, F72, fill, 760, gap=12)
        draw_lines(d, (118, 500), sub, F32, sub_fill, 720, gap=12)
        save_jpg(img, IMAGES / filename)


def make_banner(products, filename, title, body, mode, index=0):
    img = generated_bg(BANNER, filename.replace(".jpg", ".png"), mode)
    d = ImageDraw.Draw(img)
    d.rectangle((70, 70, 1530, 450), fill=(255, 255, 255, 190))
    d.line((130, 250, 1470, 250), fill=(92, 121, 139, 120), width=2)
    draw_lines(d, (135, 118), title, F58, INK, 1330, gap=8, align="center")
    draw_lines(d, (180, 294), body, F32, MUTED, 1240, gap=12, align="center")
    save_jpg(img, BANNERS / filename)


def make_banners(products):
    make_banner(products, "01_static_hook_banner.jpg", "静電気は、素材の相性で変わる", "冬のパチッは、乾燥だけでなく重ね着の組み合わせも関係します。", "blue", 0)
    make_banner(products, "02_material_pair_banner.jpg", "組み合わせ注意", "ポリエステル × ウール / ナイロン × アクリル は静電気が起きやすい組み合わせ。", "dark", 1)
    make_banner(products, "03_good_pair_banner.jpg", "合わせやすい組み合わせ", "綿 × 綿 / 綿 × レーヨン / 同じ系統の素材 は比較的まとまりやすい。", "cotton", 2)
    make_banner(products, "04_cta_banner.jpg", "冬インナーは、肌ざわりと重ね着で選ぶ", "静電気、冷え、チクチク感。冬の小さな不快感を一枚目から整える。", "warm", 3)


def make_scene_images(products):
    for filename, mode in [
        ("01_title.png", "blue"),
        ("02_hook.png", "dark"),
        ("03_toc.png", "cotton"),
        ("04_material.png", "blue"),
        ("05_pickup.png", "cotton"),
        ("06_cta.png", "warm"),
    ]:
        img = generated_bg(SQUARE, filename, mode)
        if filename == "05_pickup.png":
            add_products(img, products[:3], (150, 590, 850, 920))
        img.save(SCENES / filename)


def ease(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def cover_square(path, scale=1.06, dx=0, dy=0):
    img = Image.open(path).convert("RGBA")
    ratio = max(1000 / img.width, 1000 / img.height) * scale
    img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    x = max(0, min((img.width - 1000) // 2 + dx, img.width - 1000))
    y = max(0, min((img.height - 1000) // 2 + dy, img.height - 1000))
    return img.crop((x, y, x + 1000, y + 1000))


def overlay_text(base, title, sub, t, dark=False):
    layer = Image.new("RGBA", SQUARE, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    alpha = int(255 * min(1, t / 0.3) * (1 if t < 0.88 else max(0, (1 - t) / 0.12)))
    fill = (255, 255, 255, alpha) if dark else (42, 43, 45, alpha)
    sub_fill = (238, 244, 246, int(alpha * 0.86)) if dark else (82, 82, 78, int(alpha * 0.86))
    y = 405 - int((1 - ease(t)) * 26)
    shadow = (255, 255, 255, int(alpha * 0.45)) if not dark else (0, 0, 0, int(alpha * 0.46))
    offset = 2 if not dark else 3
    draw_lines(d, (90 - offset, y), title, F58, shadow, 810, gap=12)
    draw_lines(d, (90 + offset, y), title, F58, shadow, 810, gap=12)
    draw_lines(d, (90, y - offset), title, F58, shadow, 810, gap=12)
    draw_lines(d, (90, y + offset), title, F58, shadow, 810, gap=12)
    draw_lines(d, (90, y), title, F58, fill, 810, gap=12)
    draw_lines(d, (96 + offset, y + 165 + offset), sub, F26, shadow, 790, gap=10)
    draw_lines(d, (96, y + 165), sub, F26, sub_fill, 790, gap=10)
    return Image.alpha_composite(base, layer)


def product_float(products, t):
    img = generated_bg(SQUARE, "05_pickup.png", "cotton")
    d = ImageDraw.Draw(img)
    draw_lines(d, (82, 105), "素材と季節で選ぶ", F58, INK, 830, gap=10)
    draw_lines(d, (90, 220), "冬インナーを見比べる", F26, MUTED, 790)
    show = products[:4]
    if not show:
        return img
    cycle = min(0.999, t) * len(show)
    active = min(len(show) - 1, int(cycle))
    local = cycle - active
    try:
        pic = Image.open(show[active]["image_path"]).convert("RGBA")
    except Exception:
        return img
    pic.thumbnail((560, 560), Image.LANCZOS)
    presence = ease(min(1, local / 0.22)) * ease(min(1, (1 - local) / 0.18))
    presence = max(0.78, presence)
    card = Image.new("RGBA", (660, 600), (0, 0, 0, 0))
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((52, 40, 608, 570), radius=30, fill=(62, 82, 94, int(42 * presence)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    card.alpha_composite(shadow)
    ImageDraw.Draw(card).rounded_rectangle((42, 34, 618, 558), radius=24, fill=(255, 255, 255, int(248 * presence)))
    card.alpha_composite(pic, ((card.width - pic.width) // 2, 60))
    card.putalpha(card.split()[-1].point(lambda v: int(v * presence)))
    y = int(340 - 24 * np.sin(np.pi * ease(local)))
    img.alpha_composite(card, (170, y))
    return img


def make_bgm(seconds, path):
    rate = 44100
    n = int(seconds * rate)
    t = np.linspace(0, seconds, n, endpoint=False)
    audio = np.zeros(n, dtype=np.float32)
    chords = [[261.63, 329.63, 392], [293.66, 349.23, 440], [246.94, 329.63, 392], [220, 277.18, 329.63]]
    for i, notes in enumerate(chords * 2):
        start_i = int(i * 2.25 * rate)
        end_i = min(n, start_i + int(2.5 * rate))
        if start_i >= n:
            break
        local = np.linspace(0, (end_i - start_i) / rate, end_i - start_i, endpoint=False)
        env = np.minimum(1, local / 0.4) * np.minimum(1, (local[-1] - local + 0.001) / 0.8)
        for note in notes:
            audio[start_i:end_i] += 0.034 * np.sin(2 * np.pi * note * local) * env
    melody = [659.25, 587.33, 523.25, 493.88, 440, 523.25]
    for i, note in enumerate(melody * 4):
        start_i = int((0.7 + i * 0.68) * rate)
        end_i = min(n, start_i + int(0.55 * rate))
        if start_i >= n:
            break
        local = np.linspace(0, (end_i - start_i) / rate, end_i - start_i, endpoint=False)
        audio[start_i:end_i] += 0.062 * np.sin(2 * np.pi * note * local) * np.exp(-5 * local)
    audio *= np.minimum(1, t / 0.9)
    audio *= np.minimum(1, (seconds - t) / 1.3)
    pcm = (np.clip(audio, -0.9, 0.9) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())


def make_video(products):
    fps = 30
    scenes = [
        ("01_title.png", "冬のパチッ、\n理由があります", "静電気と素材の相性", False, 3.0, "right"),
        ("02_hook.png", "肌着は地味だけど重要", "一枚目で変わる冬の不快感", True, 2.7, "left"),
        ("03_toc.png", "このコラムのポイント", "起きやすい素材 / 避けたい組み合わせ / 選び方", False, 3.0, "up"),
        ("04_material.png", "素材同士にも、\n相性があります", "同じ系統でまとめると選びやすい", False, 2.8, "right"),
        ("05_pickup.png", "", "", False, 3.0, "in"),
        ("06_cta.png", "冬インナーを見直す", "続きは本文で", False, 2.7, "left"),
    ]
    silent = VIDEO / "v1_magazine_cm_silent.mp4"
    final = VIDEO / "v1_magazine_cm_bgm_17sec.mp4"
    bgm_path = VIDEO / "v1_apparel_magazine_soft_bgm.wav"
    writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*"mp4v"), fps, SQUARE)
    prev = None
    for filename, title, sub, dark, seconds, direction in scenes:
        frames = int(seconds * fps)
        for i in range(frames):
            t = i / max(1, frames - 1)
            if filename == "05_pickup.png":
                frame = np.array(product_float(products, t).convert("RGB"))
            else:
                dx = int((ease(t) - 0.5) * 30) if direction in ("left", "right") else 0
                if direction == "left":
                    dx *= -1
                dy = int((ease(t) - 0.5) * 24) if direction == "up" else 0
                base = cover_square(SCENES / filename, 1.05 + 0.035 * ease(t), dx, dy)
                frame = np.array(overlay_text(base, title, sub, t, dark).convert("RGB"))
            if prev is not None:
                fade = min(1, i / 10)
                frame = (prev.astype(np.float32) * (1 - fade) + frame.astype(np.float32) * fade).astype(np.uint8)
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            prev = frame
    writer.release()
    seconds = sum(s[4] for s in scenes)
    make_bgm(seconds, bgm_path)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, "-y", "-i", str(silent), "-i", str(bgm_path), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(final)], check=True)
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
    if p["code"] in ("80g7b20", "80smb20"):
        return "綿100％の7分丈ボトム。冬の重ね着や肌ざわりを重視したい日に。"
    if p["code"] == "yumeh-3btm":
        return "やわらかフィットの3分丈ボトム。短め丈で使いやすいインナー。"
    if p["code"] == "clmhn3":
        return "首元までカバーするハイネックインナー。冬の重ね着や首まわりの冷え対策に。"
    if p["code"] == "gz5bt30":
        return "綿100％ガーゼの5分丈ボトム。やさしい肌ざわりを重視する方へ。"
    return p["name"][:80]


def make_html(products):
    product_blocks = []
    for p in products:
        product_blocks.append(f"""
    <div class="rb-product">
      <img src="product_images/{p['code']}.jpg" alt="{html.escape(p['name'])}" width="100%">
      <h3>{html.escape(p['name'])}</h3>
      <p>{html.escape(product_summary(p))}</p>
      <p class="rb-price">参考価格：{p['price']:,}円</p>
      <p><a href="{p['rakuten_url']}">商品を見る</a></p>
    </div>""")
    body = f"""<div class="rb-content rb-content-018">
  <section>
    <img src="images/001_first_view.jpg" alt="{TITLE}" width="100%">
    <h1>{TITLE}</h1>
    <p>冬にセーターを脱いだ瞬間、パチッ。スカートが足にまとわりつく。髪がふわっと広がる。静電気は乾燥だけでなく、服の素材の組み合わせでも起きやすさが変わります。</p>
    <p>ここでは、冬インナーを選ぶ前に知っておきたい素材の相性を、むずかしくなりすぎない範囲で整理します。商品紹介は後半で、肌ざわりや重ね着のしやすさから自然につなげます。</p>
  </section>

  <section>
    <video src="video/v1_magazine_cm_bgm_17sec.mp4" controls playsinline muted width="100%"></video>
  </section>

  <section>
    <img src="banners/01_static_hook_banner.jpg" alt="静電気は素材の相性で変わる" width="100%">
    <h2>静電気は、素材同士の相性でも変わる</h2>
    <p>静電気は、素材がこすれたときに電気を帯びることで起こります。乾燥した冬は空気中に電気が逃げにくいため、重ね着の組み合わせによってパチッとしやすくなります。</p>
    <p>完全に防ぐのは難しくても、起きやすい組み合わせを避けるだけで、冬の小さな不快感は減らしやすくなります。</p>
  </section>

  <section>
    <img src="images/003_material_map.jpg" alt="素材の相性を考える" width="100%">
    <h2>避けたい組み合わせ、合わせやすい組み合わせ</h2>
    <table>
      <tr><th>組み合わせ</th><th>目安</th><th>考え方</th></tr>
      <tr><td>ポリエステル × ウール</td><td>起きやすい</td><td>冬服でよくあるが、パチッとしやすい組み合わせ。</td></tr>
      <tr><td>ナイロン × アクリル</td><td>起きやすい</td><td>タイツやニットの組み合わせで注意したい。</td></tr>
      <tr><td>綿 × 綿</td><td>起きにくい</td><td>同じ系統でまとめると摩擦の不快感も抑えやすい。</td></tr>
      <tr><td>綿 × レーヨン</td><td>比較的合わせやすい</td><td>肌着やインナーで取り入れやすい組み合わせ。</td></tr>
    </table>
  </section>

  <section>
    <img src="banners/02_material_pair_banner.jpg" alt="静電気が起きやすい組み合わせ" width="100%">
    <h2>冬インナーは「一枚目」で考える</h2>
    <p>肌に近いインナーを綿やガーゼなどのやわらかな素材にすると、重ね着したときのチクチク感やまとわりつきが気になりにくくなります。</p>
    <p>特にボトムインナーは、スカートやパンツ、タイツとの摩擦が起きやすい部分。丈や素材を見直すと、体感が変わることがあります。</p>
  </section>

  <section>
    <img src="banners/03_good_pair_banner.jpg" alt="合わせやすい素材の組み合わせ" width="100%">
    <h2>商品を選ぶなら、素材・丈・重ね着で見る</h2>
    <ul>
      <li><strong>素材：</strong>綿100％、ガーゼ、なめらかな編み地など、肌ざわりを確認。</li>
      <li><strong>丈：</strong>3分丈、5分丈、7分丈など、合わせる服に響きにくい長さを選ぶ。</li>
      <li><strong>首元：</strong>ハイネックは冷え対策に便利。重ね着したときの見え方も確認。</li>
      <li><strong>季節：</strong>冬だけでなく、冷房対策や季節の変わり目にも使いやすいかを見る。</li>
    </ul>
  </section>

  <section>
    <img src="images/005_product_pickup.jpg" alt="冬インナーの商品ピックアップ" width="100%">
    <h2>記事の内容から選ぶピックアップ商品</h2>
    <div class="rb-products">
{''.join(product_blocks)}
    </div>
  </section>

  <section>
    <h2>よくある質問</h2>
    <h3>綿なら静電気は絶対に起きませんか？</h3>
    <p>絶対ではありませんが、綿は比較的静電気が起きにくい素材として選びやすいです。乾燥や合わせる服によっても変わります。</p>
    <h3>一番避けたい組み合わせは？</h3>
    <p>冬によくある組み合わせでは、ポリエステルとウール、ナイロンとアクリルなどは静電気が気になる場合があります。</p>
    <h3>商品選びでは何を優先すれば良いですか？</h3>
    <p>肌に近い一枚は、素材、丈、重ね着したときの響きにくさを優先すると選びやすくなります。</p>
  </section>

  <section>
    <img src="banners/04_cta_banner.jpg" alt="冬インナーは肌ざわりと重ね着で選ぶ" width="100%">
    <h2>まとめ</h2>
    <p>冬の静電気は、乾燥だけでなく素材の組み合わせでも起きやすくなります。肌に近いインナーを見直すことは、パチッとする不快感や重ね着のストレスを減らすための小さな工夫です。</p>
    <p><a href="{RAKUTEN_SHOP}80g7b20/">綿100％の冬インナーを見てみる</a></p>
  </section>
</div>
"""
    (OUT / "content_page_completed.html").write_text(body, encoding="utf-8")


def make_upload_guide(products):
    guide = f"""# 018 納品データ

## コンテンツタイトル

{TITLE}

## 納品ファイル

- HTML: `content_page_completed.html`
- 動画: `video/v1_magazine_cm_bgm_17sec.mp4`
- 動画プレビュー: `video/preview_*.jpg`
- 本文画像: `images/*.jpg`
- 差し込みバナー: `banners/*.jpg`
- 商品画像: `product_images/*.jpg`

## 動画の考え方

商品説明ではなく、静電気と素材相性の「気になる目次」を雑誌CM風に見せる構成です。
表示文言は視聴者向けの短文だけにし、制作指示文は入れていません。

## 代表商品

{chr(10).join(f"- `{p['code']}` {p['name'][:80]} / {p['price']:,}円" for p in products)}
"""
    (OUT / "upload_guide.md").write_text(guide, encoding="utf-8")


def main():
    ensure_dirs()
    products = load_products()
    download_product_images(products)
    make_images(products)
    make_banners(products)
    make_scene_images(products)
    make_video(products)
    make_html(products)
    make_upload_guide(products)
    print(OUT)


if __name__ == "__main__":
    main()
