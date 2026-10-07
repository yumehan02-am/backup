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
    "title_banner.jpg": "call_j9OLOG48khOb6jJ02mDOczON.png",
    "person_banner.jpg": "call_8FYfxLEjpo9snbHQJWuk1FlA.png",
    "points_banner.jpg": "call_DaEzti5ddfBbW0SAOZJRcmEd.png",
    "absorbency_guide_banner.jpg": "call_lPEudB9J1xSoDhEw9nYXA1bn.png",
    "choice_banner.jpg": "call_iJ9RjNrKg8fsKb1PqFq8HAG2.png",
    "closing_banner.jpg": "call_qpifuAZqAWRbAJ97Fsc32IW8.png",
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
    candidates = [r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc"]
    for path in candidates:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def cover_crop(img, size):
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
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
    lines = fix_orphan_punctuation(lines)
    return lines


def fix_orphan_punctuation(lines):
    fixed = []
    orphans = set("。、，．・）」』】!?！？")
    for line in lines:
        if fixed and line and all(ch in orphans for ch in line):
            fixed[-1] += line
        else:
            fixed.append(line)
    return fixed


def shadow_text(draw, xy, text, fnt, fill, shadow=(255, 255, 255, 190)):
    x, y = xy
    draw.text((x + 2, y + 2), text, font=fnt, fill=shadow)
    draw.text((x, y), text, font=fnt, fill=fill)


def prepare_images():
    IMAGES.mkdir(parents=True, exist_ok=True)
    SCENES.mkdir(parents=True, exist_ok=True)
    for out_name, source_name in SOURCE_MAP.items():
        src = GENERATED / source_name
        if not src.exists():
            raise FileNotFoundError(src)
        Image.open(src).convert("RGB").save(IMAGES / out_name, quality=95)

    scene_order = [
        ("01_title.jpg", "title_banner.jpg"),
        ("02_person.jpg", "person_banner.jpg"),
        ("03_points.jpg", "points_banner.jpg"),
        ("04_absorbency.jpg", "absorbency_guide_banner.jpg"),
        ("05_choice.jpg", "choice_banner.jpg"),
        ("06_closing.jpg", "closing_banner.jpg"),
    ]
    for scene_name, src_name in scene_order:
        img = Image.open(IMAGES / src_name).convert("RGB")
        cover_crop(img, (1080, 1080)).save(SCENES / scene_name, quality=94)


def draw_banner_copy(img, title, body):
    draw = ImageDraw.Draw(img)
    title_font = mincho(52, True)
    body_font = gothic(28)
    x, y = 88, 122
    title_width = 1120 if len(title) <= 24 else 920
    for line in wrap_text(draw, title, title_font, title_width)[:2]:
        shadow_text(draw, (x, y), line, title_font, (48, 42, 40, 255))
        y += 66
    y += 10
    for line in wrap_text(draw, body, body_font, 790)[:2]:
        shadow_text(draw, (x, y), line, body_font, (68, 59, 55, 255))
        y += 38


def make_banners():
    rows = list(csv.DictReader((BASE / "data" / "banner_plan.csv").open(encoding="utf-8-sig")))
    for row in rows:
        path = IMAGES / row["file_name"]
        img = cover_crop(Image.open(path).convert("RGB"), (1600, 520))
        veil = Image.new("RGBA", img.size, (255, 255, 255, 0))
        grad = Image.new("L", img.size, 0)
        gd = ImageDraw.Draw(grad)
        for x in range(0, 850):
            gd.line([(x, 0), (x, img.height)], fill=int(105 * (1 - x / 850)))
        veil.putalpha(grad.filter(ImageFilter.GaussianBlur(24)))
        img = Image.alpha_composite(img.convert("RGBA"), veil)
        draw_banner_copy(img, row["overlay_title"], row["overlay_body"])
        img.convert("RGB").save(path, quality=94)


def make_bgm(duration):
    VIDEO.mkdir(parents=True, exist_ok=True)
    out = VIDEO / "bgm_apparel_soft_v3.wav"
    rate = 44100
    notes = [392.0, 493.88, 587.33, 659.25, 523.25, 440.0]
    with wave.open(str(out), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(int(duration * rate)):
            t = i / rate
            note = notes[int(t / 0.82) % len(notes)]
            env = 0.55 + 0.45 * math.sin(2 * math.pi * 0.18 * t)
            sample = math.sin(2 * math.pi * note * t) * 0.085 * env
            sample += math.sin(2 * math.pi * note * 2 * t) * 0.016 * env
            frames += int(sample * 32767).to_bytes(2, "little", signed=True)
        wf.writeframes(frames)
    return out


def typewriter_two_lines(draw, xy, line1, line2, fnt, progress):
    x, y = xy
    start_delay = 0.11
    hold = 0.24
    if progress < start_delay:
        return
    type_end = 1.0 - hold
    p = min(1, (progress - start_delay) / max(0.01, type_end - start_delay))
    full = line1 + "\n" + line2
    visible = max(1, math.ceil(len(full) * p))
    current = full[:visible]
    lines = current.split("\n")
    fill = (48, 42, 40, 255)
    shadow = (255, 255, 255, 198)
    for i, line in enumerate(lines[:2]):
        if line:
            shadow_text(draw, (x, y + i * 86), line, fnt, fill, shadow)


def draw_points_scene(draw, progress):
    title_font = mincho(58, True)
    point_font = mincho(48, False)
    x, y = 72, 290
    shadow_text(draw, (x, y), "このコラムのポイント", title_font, (48, 42, 40, 255))
    points = ["日常向けの吸水量", "パッドとの使い分け", "外出前の選び方"]
    start_y = y + 88
    for i, text in enumerate(points):
        threshold = 0.18 + i * 0.22
        local = max(0, min(1, (progress - threshold) / 0.18))
        if local <= 0:
            continue
        alpha = int(255 * local)
        yy = start_y + i * 62
        shadow_text(
            draw,
            (x + 8, yy),
            text,
            point_font,
            (54, 47, 44, alpha),
            (255, 255, 255, int(alpha * 0.75)),
        )


def draw_sentence(draw, main, sub, progress, mode):
    title_font = mincho(64, True)
    sub_font = mincho(52, False)
    x, y = 74, 352
    if mode == "slide":
        x += int((1 - min(1, progress * 2)) * 54)
    elif mode == "rise":
        y += int((1 - min(1, progress * 2)) * 34)
    alpha = min(255, int(255 * min(1, progress * 2.2)))
    shadow = (255, 255, 255, int(alpha * 0.78))
    shadow_text(draw, (x, y), main, title_font, (48, 42, 40, alpha), shadow)
    if sub:
        shadow_text(draw, (x, y + 78), sub, sub_font, (58, 50, 46, alpha), shadow)


def render_scene(bg, scene_idx, progress):
    zoom_amounts = [0.014, 0.018, 0.012, 0.016, 0.02, 0.014]
    pan_dirs = [-1, 1, 0, -1, 1, -1]
    zoom = 1.025 + zoom_amounts[scene_idx] * progress
    resized = bg.resize((int(1080 * zoom), int(1080 * zoom)), Image.Resampling.LANCZOS)
    pan = int(pan_dirs[scene_idx] * 14 * progress)
    left = (resized.width - 1080) // 2 + pan
    top = (resized.height - 1080) // 2
    frame = resized.crop((left, top, left + 1080, top + 1080)).convert("RGBA")
    draw = ImageDraw.Draw(frame)

    if scene_idx == 0:
        typewriter_two_lines(draw, (78, 360), "尿漏れ対策を", "ふつうの準備に。", mincho(66, True), progress)
    elif scene_idx == 1:
        draw_sentence(draw, "外出前の不安を、", "ひとりで抱え込まない。", progress, "rise")
    elif scene_idx == 2:
        draw_points_scene(draw, progress)
    elif scene_idx == 3:
        draw_sentence(draw, "20cc・30ccは、", "日常の“念のため”に。", progress, "slide")
    elif scene_idx == 4:
        draw_sentence(draw, "パッドだけが正解、", "ではありません。", progress, "rise")
    else:
        draw_sentence(draw, "気になる日も、", "いつもの私で出かける。", progress, "rise")
    return frame


def make_frames():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    scene_files = [
        "01_title.jpg",
        "02_person.jpg",
        "03_points.jpg",
        "04_absorbency.jpg",
        "05_choice.jpg",
        "06_closing.jpg",
    ]
    durations = [4.4, 3.0, 3.2, 3.0, 3.0, 3.0]
    fps = 30
    transition_frames = 10
    bgs = [Image.open(SCENES / name).convert("RGB") for name in scene_files]
    idx = 0
    previous = None
    for sidx, (bg, duration) in enumerate(zip(bgs, durations)):
        total = int(duration * fps)
        for frame_no in range(total):
            progress = frame_no / max(1, total - 1)
            frame = render_scene(bg, sidx, progress)
            if previous is not None and frame_no < transition_frames:
                alpha = frame_no / transition_frames
                frame = Image.blend(previous, frame, alpha)
            frame.convert("RGB").save(FRAMES / f"frame_{idx:04d}.jpg", quality=92)
            previous = frame
            idx += 1
    make_preview()
    return sum(durations)


def make_preview():
    picks = [110, 175, 270, 375, 465, 555]
    sheet = Image.new("RGB", (810, 540), "white")
    for i, idx in enumerate(picks):
        path = FRAMES / f"frame_{idx:04d}.jpg"
        img = Image.open(path).resize((270, 270), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 3) * 270, (i // 3) * 270))
    sheet.save(VIDEO / "preview_contact_sheet_v3.jpg", quality=92)


def encode_video(bgm):
    out = VIDEO / "opening_cm_v3.mp4"
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
    duration = make_frames()
    bgm = make_bgm(duration)
    print(encode_video(bgm))


if __name__ == "__main__":
    main()
