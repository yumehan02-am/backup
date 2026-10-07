import csv
import math
import pathlib
import shutil
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import imageio_ffmpeg


BASE = pathlib.Path(__file__).resolve().parent
IMAGES = BASE / "images"
VIDEO = BASE / "video"
SCENES = VIDEO / "scene_backgrounds"
FRAMES = VIDEO / "frames"

GENERATED = pathlib.Path(r"C:\Users\i58400am\.codex\generated_images\01a03bd9-3f16-70d1-81ca-80d9bbc91430")
SOURCE_MAP = {
    "title_banner.jpg": "call_LXdlA22K8GN2EFbE2cvPBMUx.png",
    "person_banner.jpg": "call_Fs4SzUUZQSZmZ3ELGPZkj982.png",
    "points_banner.jpg": "call_TdqW5Khqk23QzfN2zRYaBAaL.png",
    "absorbency_guide_banner.jpg": "call_bpPFOO1O9C38zCJNZi57eIbF.png",
    "closing_banner.jpg": "call_akFAD4d5tKfq630IY3y3e7ma.png",
}


def mincho(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\yumindb.ttf" if bold else r"C:\Windows\Fonts\yumin.ttf",
        r"C:\Windows\Fonts\YuMincho.ttc",
        r"C:\Windows\Fonts\meiryo.ttc",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def gothic(size):
    candidates = [
        r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\meiryo.ttc",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def cover_crop(img, size, anchor="center"):
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    img = img.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    if anchor == "left":
        left = 0
    elif anchor == "right":
        left = img.width - target_w
    else:
        left = (img.width - target_w) // 2
    top = (img.height - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def wrap_text(draw, text, fnt, max_width):
    lines = []
    line = ""
    for char in text:
        test = line + char
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width or not line:
            line = test
        else:
            lines.append(line)
            line = char
    if line:
        lines.append(line)
    return lines


def shadow_text(draw, xy, text, fnt, fill, shadow=(255, 255, 255, 190)):
    x, y = xy
    draw.text((x + 2, y + 2), text, font=fnt, fill=shadow)
    draw.text((x, y), text, font=fnt, fill=fill)


def draw_banner_copy(img, title, body):
    draw = ImageDraw.Draw(img)
    title_font = mincho(56, True)
    body_font = gothic(28)
    x, y = 92, 126
    color = (49, 43, 41, 255)
    for line in wrap_text(draw, title, title_font, 760)[:2]:
        shadow_text(draw, (x, y), line, title_font, color)
        y += 68
    y += 8
    for line in wrap_text(draw, body, body_font, 760)[:2]:
        shadow_text(draw, (x, y), line, body_font, (67, 58, 54, 255))
        y += 38


def prepare_images():
    IMAGES.mkdir(parents=True, exist_ok=True)
    SCENES.mkdir(parents=True, exist_ok=True)
    for out_name, source_name in SOURCE_MAP.items():
        src = GENERATED / source_name
        if not src.exists():
            raise FileNotFoundError(src)
        img = Image.open(src).convert("RGB")
        img.save(IMAGES / out_name, quality=95)

    # Choice uses the same generated object scene as a separate banner name, without reusing old assets.
    shutil.copy2(IMAGES / "closing_banner.jpg", IMAGES / "choice_banner.jpg")

    scene_order = [
        ("01_title.jpg", "title_banner.jpg"),
        ("02_person.jpg", "person_banner.jpg"),
        ("03_points.jpg", "points_banner.jpg"),
        ("04_absorbency.jpg", "absorbency_guide_banner.jpg"),
        ("05_choice.jpg", "choice_banner.jpg"),
        ("06_closing.jpg", "closing_banner.jpg"),
    ]
    for scene, src in scene_order:
        img = Image.open(IMAGES / src).convert("RGB")
        cover_crop(img, (1080, 1080)).save(SCENES / scene, quality=94)


def make_banners():
    rows = list(csv.DictReader((BASE / "data" / "banner_plan.csv").open(encoding="utf-8-sig")))
    for row in rows:
        path = IMAGES / row["file_name"]
        img = Image.open(path).convert("RGB")
        img = cover_crop(img, (1600, 520))
        veil = Image.new("RGBA", img.size, (255, 255, 255, 0))
        grad = Image.new("L", img.size, 0)
        gd = ImageDraw.Draw(grad)
        for x in range(0, 850):
            gd.line([(x, 0), (x, img.height)], fill=int(105 * (1 - x / 850)))
        veil.putalpha(grad.filter(ImageFilter.GaussianBlur(24)))
        img = Image.alpha_composite(img.convert("RGBA"), veil)
        draw_banner_copy(img, row["overlay_title"], row["overlay_body"])
        img.convert("RGB").save(path, quality=94)


def make_bgm(duration=18.4):
    VIDEO.mkdir(parents=True, exist_ok=True)
    out = VIDEO / "bgm_apparel_soft_v2.wav"
    rate = 44100
    notes = [392.0, 493.88, 587.33, 659.25, 523.25, 440.0]
    with wave.open(str(out), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(int(duration * rate)):
            t = i / rate
            note = notes[int(t / 0.8) % len(notes)]
            env = 0.55 + 0.45 * math.sin(2 * math.pi * 0.18 * t)
            sample = math.sin(2 * math.pi * note * t) * 0.09 * env
            sample += math.sin(2 * math.pi * note * 2 * t) * 0.018 * env
            frames += int(sample * 32767).to_bytes(2, "little", signed=True)
        wf.writeframes(frames)
    return out


def draw_video_text(frame, main, sub, mode, progress):
    draw = ImageDraw.Draw(frame)
    title_font = mincho(70, True)
    sub_font = mincho(56, False)
    color = (48, 42, 40, 255)
    x = 76
    y = 335 if sub else 390
    alpha = min(255, int(255 * min(1, progress * 2.1)))

    if mode == "type":
        text = main
        shown = max(1, int(len(text) * min(1, progress * 1.25)))
        main = text[:shown]
    elif mode == "slide":
        x += int((1 - min(1, progress * 2)) * 54)
    elif mode == "rise":
        y += int((1 - min(1, progress * 2)) * 34)

    fill = (*color[:3], alpha)
    shadow = (255, 255, 255, int(alpha * 0.78))
    for n, text in enumerate([main, sub] if sub else [main]):
        fnt = title_font if n == 0 else sub_font
        yy = y + n * 82
        for line in wrap_text(draw, text, fnt, 850)[:2]:
            shadow_text(draw, (x, yy), line, fnt, fill, shadow)
            yy += 78 if n == 0 else 64


def make_frames():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    scenes = [
        ("01_title.jpg", "尿もれ対策を、", "ふつうの準備に。", "type"),
        ("02_person.jpg", "外出前の不安を、", "ひとりで抱え込まない。", "fade"),
        ("03_points.jpg", "このコラムのポイントは、", "少量の不安との付き合い方。", "rise"),
        ("04_absorbency.jpg", "20cc・30ccは、", "日常の“念のため”に。", "slide"),
        ("05_choice.jpg", "パッドだけが正解、", "ではありません。", "rise"),
        ("06_closing.jpg", "気になる日も、", "いつもの私で出かける。", "fade"),
    ]
    fps = 30
    idx = 0
    for sidx, (bg_name, main, sub, mode) in enumerate(scenes):
        bg = Image.open(SCENES / bg_name).convert("RGB")
        for frame_no in range(fps * 3):
            p = frame_no / (fps * 3 - 1)
            zoom = 1.03 + 0.018 * p
            resized = bg.resize((int(1080 * zoom), int(1080 * zoom)), Image.Resampling.LANCZOS)
            pan = int(((sidx % 3) - 1) * 14 * p)
            left = (resized.width - 1080) // 2 + pan
            top = (resized.height - 1080) // 2
            frame = resized.crop((left, top, left + 1080, top + 1080)).convert("RGBA")
            draw_video_text(frame, main, sub, mode, p)
            frame.convert("RGB").save(FRAMES / f"frame_{idx:04d}.jpg", quality=92)
            idx += 1
    make_preview()


def make_preview():
    picks = [80, 150, 240, 330, 420, 510]
    sheet = Image.new("RGB", (810, 540), "white")
    for i, idx in enumerate(picks):
        path = FRAMES / f"frame_{idx:04d}.jpg"
        img = Image.open(path).resize((270, 270), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 3) * 270, (i // 3) * 270))
    sheet.save(VIDEO / "preview_contact_sheet_v2.jpg", quality=92)


def encode_video(bgm):
    out = VIDEO / "opening_cm_v2.mp4"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        "30",
        "-i",
        str(FRAMES / "frame_%04d.jpg"),
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
        "96k",
        str(out),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(FRAMES)
    return out


def main():
    prepare_images()
    make_banners()
    make_frames()
    bgm = make_bgm()
    print(encode_video(bgm))


if __name__ == "__main__":
    main()
