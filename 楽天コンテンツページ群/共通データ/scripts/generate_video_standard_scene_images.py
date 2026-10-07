import math
import pathlib
import subprocess
import wave

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter


BASE = pathlib.Path(__file__).resolve().parent
IMG = BASE / "generated_images_v7"
BG = BASE / "generated_images_v2" / "backgrounds"
PRODUCT = BASE / "generated_images_v9_pickups"
SCENE_IMG = BASE / "generated_scene_images_v11"
OUT = BASE / "generated_video_v11"
OUT.mkdir(exist_ok=True)

W = H = 1000
FPS = 30
MUSIC_STYLE = "apparel_soft"
_COVER_CACHE = {}

MUSIC_PROFILES = {
    "apparel_soft": {
        "tempo": 0.95,
        "volume": 0.9,
        "chords": [
            [261.63, 329.63, 392.00],
            [220.00, 329.63, 392.00],
            [246.94, 293.66, 369.99],
            [196.00, 293.66, 349.23],
            [220.00, 261.63, 329.63],
        ],
        "melody": [659.25, 587.33, 523.25, 493.88, 392.00, 440.00],
        "pad": 0.035,
        "bell": 0.075,
    },
    "senior_care": {
        "tempo": 0.78,
        "volume": 0.82,
        "chords": [
            [246.94, 293.66, 369.99],
            [196.00, 293.66, 349.23],
            [220.00, 261.63, 329.63],
            [174.61, 261.63, 329.63],
            [196.00, 246.94, 293.66],
        ],
        "melody": [493.88, 440.00, 392.00, 349.23, 392.00],
        "pad": 0.042,
        "bell": 0.045,
    },
    "beauty_clean": {
        "tempo": 1.05,
        "volume": 0.88,
        "chords": [
            [293.66, 369.99, 440.00],
            [246.94, 329.63, 415.30],
            [261.63, 329.63, 392.00],
            [220.00, 293.66, 369.99],
            [246.94, 311.13, 392.00],
        ],
        "melody": [739.99, 659.25, 587.33, 659.25, 554.37, 493.88],
        "pad": 0.03,
        "bell": 0.085,
    },
    "gift_warm": {
        "tempo": 0.9,
        "volume": 0.86,
        "chords": [
            [261.63, 329.63, 392.00],
            [196.00, 261.63, 329.63],
            [220.00, 277.18, 329.63],
            [174.61, 261.63, 349.23],
            [196.00, 246.94, 329.63],
        ],
        "melody": [523.25, 587.33, 659.25, 587.33, 523.25, 440.00],
        "pad": 0.038,
        "bell": 0.065,
    },
    "season_bright": {
        "tempo": 1.12,
        "volume": 0.84,
        "chords": [
            [329.63, 392.00, 493.88],
            [293.66, 369.99, 440.00],
            [261.63, 329.63, 392.00],
            [293.66, 349.23, 440.00],
            [329.63, 415.30, 493.88],
        ],
        "melody": [783.99, 659.25, 587.33, 659.25, 739.99, 659.25],
        "pad": 0.026,
        "bell": 0.092,
    },
}


def font(size, style="mincho"):
    if style == "mincho_light":
        names = [r"C:\Windows\Fonts\yuminl.ttf", r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc"]
    elif style == "mincho":
        names = [r"C:\Windows\Fonts\yumin.ttf", r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc"]
    elif style == "gothic_light":
        names = [r"C:\Windows\Fonts\YuGothL.ttc", r"C:\Windows\Fonts\YuGothR.ttc"]
    else:
        names = [r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc"]
    for name in names:
        if pathlib.Path(name).exists():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default()


F72 = font(82, "mincho_light")
F58 = font(68, "mincho_light")
F52 = font(62, "mincho_light")
F46 = font(56, "mincho")
F34 = font(40, "mincho")
F28 = font(32, "gothic_light")


def ease(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def cover(path):
    key = str(path)
    if key in _COVER_CACHE:
        return _COVER_CACHE[key].copy()
    img = Image.open(path).convert("RGBA")
    ratio = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    x = (img.width - W) // 2
    y = (img.height - H) // 2
    img = img.crop((x, y, x + W, y + H))
    _COVER_CACHE[key] = img
    return img.copy()


def kenburns(path, t, direction):
    src = cover(path)
    scale = 1.08
    zw = int(W / scale)
    zh = int(H / scale)
    if direction == "right":
        x = int((W - zw) * ease(t))
        y = int((H - zh) * 0.45)
    elif direction == "left":
        x = int((W - zw) * (1 - ease(t)))
        y = int((H - zh) * 0.42)
    elif direction == "up":
        x = int((W - zw) * 0.5)
        y = int((H - zh) * (1 - ease(t)))
    else:
        scale = 1.12 - 0.055 * ease(t)
        zw = int(W / scale)
        zh = int(H / scale)
        x = (W - zw) // 2
        y = (H - zh) // 2
    return src.crop((x, y, x + zw, y + zh)).resize((W, H), Image.LANCZOS)


def soft_readability(img, side="left"):
    xs = np.linspace(0, 1, W, dtype=np.float32)
    if side == "left":
        alpha = (95 * np.clip(1 - xs / 0.76, 0, 1)).astype(np.uint8)
    elif side == "right":
        alpha = (95 * np.clip((xs - 0.32) / 0.68, 0, 1)).astype(np.uint8)
    else:
        alpha = np.full(W, 42, dtype=np.uint8)
    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[:, :, 3] = alpha[None, :]
    overlay = Image.fromarray(rgba, "RGBA")
    return Image.alpha_composite(img, overlay)


def lines(draw, text, fnt, width):
    result = []
    for raw in text.split("\n"):
        buf = ""
        for ch in raw:
            test = buf + ch
            if draw.textbbox((0, 0), test, font=fnt)[2] <= width:
                buf = test
            else:
                if buf:
                    result.append(buf)
                buf = ch
        if buf:
            result.append(buf)
    return result


def tracked_width(draw, text, fnt, tracking):
    if not text:
        return 0
    width = 0
    for i, ch in enumerate(text):
        box = draw.textbbox((0, 0), ch, font=fnt)
        width += box[2] - box[0]
        if i < len(text) - 1:
            width += tracking
    return width


def draw_tracked(draw, xy, text, fnt, fill, tracking=0):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        box = draw.textbbox((0, 0), ch, font=fnt)
        x += box[2] - box[0] + tracking


def draw_title(layer, text, t, align="left", fnt=F58, typewrite=False, y=360):
    d = ImageDraw.Draw(layer)
    reveal = max(0, min(1, (t - 0.08) / 0.5))
    alpha = int(255 * min(1, t / 0.35) * (1 if t < 0.86 else max(0, (1 - t) / 0.14)))
    if typewrite:
        text = text[: int(len(text) * reveal)]
    max_w = 835 if align != "left" else 805
    text_lines = lines(d, text, fnt, max_w)
    tracking = 3
    heights = []
    total = 0
    for line in text_lines:
        box = d.textbbox((0, 0), line, font=fnt)
        h = box[3] - box[1]
        heights.append(h)
        total += h + 16
    total = max(0, total - 16)
    y0 = y - total / 2 + int((1 - ease(reveal)) * 20)
    for line, h in zip(text_lines, heights):
        tw = tracked_width(d, line, fnt, tracking)
        if align == "center":
            x = (W - tw) / 2
        elif align == "right":
            x = W - tw - 86
        else:
            x = 70
        draw_tracked(d, (x + 3, y0 + 3), line, fnt, (0, 0, 0, int(alpha * 0.26)), tracking)
        draw_tracked(d, (x, y0), line, fnt, (255, 255, 255, alpha), tracking)
        y0 += h + 20


def draw_caption(layer, text, t, y=700):
    d = ImageDraw.Draw(layer)
    alpha = int(235 * min(1, t / 0.35))
    tracking = 2
    x = (W - tracked_width(d, text, F34, tracking)) / 2
    draw_tracked(d, (x + 2, y + 2), text, F34, (0, 0, 0, int(alpha * 0.25)), tracking)
    draw_tracked(d, (x, y), text, F34, (255, 255, 255, alpha), tracking)


def editorial_scene(path, text, t, direction, align="left", fnt=F58, side="left", caption="", typewrite=False):
    img = soft_readability(kenburns(path, t, direction), side)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_title(layer, text, t, align=align, fnt=fnt, typewrite=typewrite)
    if caption:
        draw_caption(layer, caption, t)
    return Image.alpha_composite(img, layer)


def chapter_scene(path, title, sub, t):
    img = kenburns(path, t, "zoom")
    img = Image.alpha_composite(img, Image.new("RGBA", (W, H), (255, 250, 248, 74)))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    alpha = int(255 * min(1, t / 0.35))
    tracking = 4
    x = 500 - tracked_width(d, title, F58, tracking) / 2
    draw_tracked(d, (x + 2, 405 + 2), title, F58, (255, 255, 255, int(alpha * 0.55)), tracking)
    draw_tracked(d, (x, 405), title, F58, (78, 45, 56, alpha), tracking)
    d.line((170, 515, 830, 515), fill=(98, 56, 68, int(alpha * 0.45)), width=2)
    x = 500 - tracked_width(d, sub, F28, 2) / 2
    draw_tracked(d, (x, 554), sub, F28, (98, 56, 68, alpha), 2)
    return Image.alpha_composite(img, layer)


def product_glimpse(t):
    img = cover(BG / "bg_preparation.png").filter(ImageFilter.GaussianBlur(5))
    img = Image.alpha_composite(img, Image.new("RGBA", (W, H), (255, 250, 248, 174)))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    alpha = int(255 * min(1, t / 0.35))
    title = "自分に合う一枚へ"
    x = 500 - tracked_width(d, title, F46, 4) / 2
    draw_tracked(d, (x + 2, 110 + 2), title, F46, (255, 255, 255, int(alpha * 0.65)), 4)
    draw_tracked(d, (x, 110), title, F46, (78, 45, 56, alpha), 4)
    paths = [PRODUCT / "skinc00.jpg", PRODUCT / "fls3n00.jpg", PRODUCT / "150fwn.jpg"]

    cycle = min(0.999, t) * len(paths)
    active = min(len(paths) - 1, int(cycle))
    local_t = cycle - active

    for offset in (-1, 0, 1):
        idx = active + offset
        if idx < 0 or idx >= len(paths):
            continue
        rel = local_t - offset
        presence = min(1, rel / 0.24, (1 - rel) / 0.24)
        presence = ease(max(0, presence))
        if presence <= 0:
            continue

        p = Image.open(paths[idx]).convert("RGBA")
        p.thumbnail((565, 565), Image.LANCZOS)
        scale = 0.95 + 0.055 * ease(min(1, rel))
        pw = int(p.width * scale)
        ph = int(p.height * scale)
        p = p.resize((pw, ph), Image.LANCZOS)

        card = Image.new("RGBA", (650, 650), (0, 0, 0, 0))
        shadow = Image.new("RGBA", (650, 650), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((60, 60, 590, 590), radius=34, fill=(80, 48, 60, int(50 * presence)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(22))
        card.alpha_composite(shadow)
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((48, 45, 602, 600), radius=22, fill=(255, 255, 255, int(248 * presence)))
        card.alpha_composite(p, ((650 - p.width) // 2, (650 - p.height) // 2))
        card.putalpha(card.split()[-1].point(lambda v: int(v * presence)))

        x = 175
        y = int(270 - 18 * math.sin(math.pi * ease(max(0, min(1, rel)))))
        img.alpha_composite(card, (x, y))
    return Image.alpha_composite(img, layer)


def make_bgm(seconds, path, style=MUSIC_STYLE):
    profile = MUSIC_PROFILES.get(style, MUSIC_PROFILES["apparel_soft"])
    rate = 44100
    n = int(seconds * rate)
    t = np.linspace(0, seconds, n, endpoint=False)
    audio = np.zeros(n, dtype=np.float32)
    chord_len = 4.2 / profile["tempo"]
    for index, notes in enumerate(profile["chords"]):
        start = index * 4 / profile["tempo"]
        start_i = int(start * rate)
        end_i = min(n, int((start + chord_len) * rate))
        if start_i >= n:
            continue
        local = np.linspace(0, (end_i - start_i) / rate, end_i - start_i, endpoint=False)
        env = np.minimum(1, local / 0.9) * np.minimum(1, (local[-1] - local + 0.001) / 1.1)
        for note in notes:
            audio[start_i:end_i] += profile["pad"] * np.sin(2 * np.pi * note * local) * env
            audio[start_i:end_i] += profile["pad"] * 0.52 * np.sin(2 * np.pi * note * 2.01 * local) * env
    melody_gap = 0.95 / profile["tempo"]
    for i, note in enumerate(profile["melody"] * 4):
        start = 0.85 + i * melody_gap
        start_i = int(start * rate)
        end_i = min(n, start_i + int((0.82 / profile["tempo"]) * rate))
        if start_i >= n:
            break
        local = np.linspace(0, (end_i - start_i) / rate, end_i - start_i, endpoint=False)
        env = np.exp(-4.2 * local)
        audio[start_i:end_i] += profile["bell"] * np.sin(2 * np.pi * note * local) * env
    audio *= np.minimum(1, t / 1.2)
    audio *= np.minimum(1, (seconds - t) / 1.8)
    audio *= profile["volume"]
    audio = np.clip(audio, -0.95, 0.95)
    pcm = (audio * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())


def make_frame(scene, t):
    kind = scene[0]
    if kind == "editorial":
        _, path, text, direction, align, fnt, side, caption, typewrite, _seconds = scene
        return editorial_scene(path, text, t, direction, align, fnt, side, caption, typewrite)
    if kind == "chapter":
        _, path, title, sub, _seconds = scene
        return chapter_scene(path, title, sub, t)
    return product_glimpse(t)


def save_video():
    scenes = [
        ("editorial", SCENE_IMG / "01_title.png", "尿漏れが気になる女性へ\n吸水ショーツの選び方", "right", "left", F52, "left", "", True, 3.0),
        ("editorial", SCENE_IMG / "02_empathy.png", "外出中の不安を\n少し軽く", "left", "left", F58, "left", "", False, 2.4),
        ("chapter", SCENE_IMG / "03_absorbency.png", "吸水量で選ぶ", "20cc〜30cc / 50cc / 150cc以上", 2.4),
        ("chapter", SCENE_IMG / "04_material.png", "素材で選ぶ", "肌にふれるものだから", 2.3),
        ("editorial", SCENE_IMG / "05_benefit.png", "目立ちにくさも\n心地よさも", "up", "center", F52, "center", "", False, 2.5),
        ("product", "", "", "", "", "", "", "", "", 3.4),
        ("editorial", SCENE_IMG / "06_cta.png", "いつもの毎日を\n前向きに", "zoom", "center", F52, "center", "", True, 2.6),
    ]
    seconds = sum(s[-1] for s in scenes)
    silent_video = OUT / "v11_scene_images_large_text_silent.mp4"
    final_video = OUT / "v11_scene_images_large_text_bgm_19sec.mp4"
    bgm = OUT / "v11_original_soft_bgm.wav"
    writer = cv2.VideoWriter(str(silent_video), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    prev = None
    idx = 0
    for scene in scenes:
        frames = int(scene[-1] * FPS)
        for i in range(frames):
            t = i / max(frames - 1, 1)
            img = make_frame(scene, t)
            current = np.array(img.convert("RGB"))
            fade = min(1, i / 14)
            if prev is not None and fade < 1:
                current = (prev.astype(np.float32) * (1 - fade) + current.astype(np.float32) * fade).astype(np.uint8)
            writer.write(cv2.cvtColor(current, cv2.COLOR_RGB2BGR))
            prev = current
            idx += 1
    writer.release()
    make_bgm(seconds, bgm, MUSIC_STYLE)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(bgm),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(final_video),
        ],
        check=True,
    )
    print(final_video)


def previews():
    video = OUT / "v11_scene_images_large_text_bgm_19sec.mp4"
    cap = cv2.VideoCapture(str(video))
    for sec in (1, 4, 7, 10, 14, 17):
        cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        ok, encoded = cv2.imencode(".jpg", frame)
        if ok:
            (OUT / f"preview_{sec}s.jpg").write_bytes(encoded.tobytes())
    cap.release()


if __name__ == "__main__":
    save_video()
    previews()
