import csv
import math
import pathlib
import shutil
import subprocess
import wave
import cv2
import numpy as np
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE = pathlib.Path(__file__).resolve().parent
IMAGES = BASE / "images"
VIDEO = BASE / "video"
SCENES = VIDEO / "scene_backgrounds"

GENERATED = pathlib.Path(r"C:\Users\i58400am\.codex\generated_images\01a03bd9-3f16-70d1-81ca-80d9bbc91430")
SOURCE_MAP = {
    "title_banner.jpg": "call_WbYZAsMXq3KBTwmcoRVg7SU4.png",
    "empathy_banner.jpg": "call_EFWFZ1ZcIQ14Ebhc13BYB7lq.png",
    "absorbency_guide_banner.jpg": "call_hpldpUCsvoNjFc8ZiKJV4Y0Y.png",
    "choice_banner.jpg": "call_K9j1rrr6Q5MDFhwmIlF8BwCn.png",
    "closing_banner.jpg": "call_pxY1HrB4bbIJrn6wP7wuGr0Y.png",
}


def font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\YuGothB.ttc" if bold else r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\meiryob.ttc" if bold else r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def cover_crop(img, size):
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_size = (int(src_w * scale), int(src_h * scale))
    img = img.resize(new_size, Image.Resampling.LANCZOS)
    left = (img.width - target_w) // 2
    top = (img.height - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def draw_text_block(draw, xy, title, body, max_width, title_size=58, body_size=28, color=(55, 48, 45)):
    x, y = xy
    title_font = font(title_size, True)
    body_font = font(body_size, False)
    line_gap = 12
    title_lines = wrap_text(draw, title, title_font, max_width)
    for line in title_lines:
        draw_text_with_shadow(draw, (x, y), line, title_font, color)
        y += title_size + line_gap
    y += 8
    for line in wrap_text(draw, body, body_font, max_width):
        draw_text_with_shadow(draw, (x, y), line, body_font, color)
        y += body_size + 10


def wrap_text(draw, text, fnt, max_width):
    lines = []
    current = ""
    for char in text:
        test = current + char
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def draw_text_with_shadow(draw, xy, text, fnt, fill):
    x, y = xy
    draw.text((x + 2, y + 2), text, font=fnt, fill=(255, 255, 255, 160))
    draw.text((x, y), text, font=fnt, fill=fill)


def prepare_backgrounds():
    IMAGES.mkdir(parents=True, exist_ok=True)
    SCENES.mkdir(parents=True, exist_ok=True)
    for out_name, source_name in SOURCE_MAP.items():
        src = GENERATED / source_name
        if not src.exists():
            raise FileNotFoundError(src)
        shutil.copy2(src, IMAGES / out_name)
    scene_names = [
        "01_title.jpg",
        "02_hook.jpg",
        "03_points.jpg",
        "04_knowledge.jpg",
        "05_compare.jpg",
        "06_closing.jpg",
    ]
    source_cycle = [
        "title_banner.jpg",
        "empathy_banner.jpg",
        "absorbency_guide_banner.jpg",
        "choice_banner.jpg",
        "empathy_banner.jpg",
        "closing_banner.jpg",
    ]
    for scene_name, source_name in zip(scene_names, source_cycle):
        img = Image.open(IMAGES / source_name).convert("RGB")
        img = cover_crop(img, (1080, 1080))
        img.save(SCENES / scene_name, quality=94)


def make_banners():
    rows = list(csv.DictReader((BASE / "data" / "banner_plan.csv").open(encoding="utf-8-sig")))
    for row in rows:
        path = IMAGES / row["file_name"]
        img = Image.open(path).convert("RGB")
        img = cover_crop(img, (1600, 520))
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        grad = Image.new("L", img.size, 0)
        gd = ImageDraw.Draw(grad)
        for x in range(0, 920):
            alpha = int(130 * (1 - x / 920))
            gd.line([(x, 0), (x, img.height)], fill=alpha)
        overlay.putalpha(grad.filter(ImageFilter.GaussianBlur(20)))
        img = Image.alpha_composite(img.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(img)
        draw_text_block(draw, (92, 128), row["overlay_title"], row["overlay_body"], 720)
        img.convert("RGB").save(path, quality=94)


def make_bgm(duration=18.2, out_path=VIDEO / "bgm_apparel_soft.wav"):
    VIDEO.mkdir(parents=True, exist_ok=True)
    rate = 44100
    notes = [440.0, 523.25, 659.25, 587.33, 493.88, 659.25]
    with wave.open(str(out_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        total = int(duration * rate)
        frames = bytearray()
        for i in range(total):
            t = i / rate
            beat = int(t / 0.75) % len(notes)
            tone = notes[beat]
            env = 0.5 + 0.5 * math.sin(2 * math.pi * 0.22 * t)
            sample = math.sin(2 * math.pi * tone * t) * 0.12 * env
            sample += math.sin(2 * math.pi * tone * 2 * t) * 0.025 * env
            frames += int(max(-1, min(1, sample)) * 32767).to_bytes(2, "little", signed=True)
        wf.writeframes(frames)
    return out_path


def make_video_frames():
    frames_dir = VIDEO / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    scenes = [
        ("01_title.jpg", "尿もれ対策を", "“ふつうの準備”へ", "type"),
        ("02_hook.jpg", "こっそり悩む朝に", "", "fade"),
        ("03_points.jpg", "このコラムのポイント", "少量の不安 / 吸水量 / 選び方", "list"),
        ("04_knowledge.jpg", "20cc・30ccは", "日常の目安", "slide"),
        ("05_compare.jpg", "パッドだけが", "正解じゃない", "page"),
        ("06_closing.jpg", "安心を一枚、", "外出前に", "fade"),
    ]
    fps = 30
    sec_per_scene = 3
    idx = 0
    for scene_idx, (bg_name, line1, line2, mode) in enumerate(scenes):
        bg = Image.open(SCENES / bg_name).convert("RGB")
        for f in range(fps * sec_per_scene):
            p = f / (fps * sec_per_scene - 1)
            zoom = 1.035 + 0.025 * p
            pan_x = int((scene_idx % 3 - 1) * 18 * p)
            img = bg.resize((int(1080 * zoom), int(1080 * zoom)), Image.Resampling.LANCZOS)
            left = (img.width - 1080) // 2 + pan_x
            top = (img.height - 1080) // 2
            frame = img.crop((left, top, left + 1080, top + 1080)).convert("RGBA")
            draw = ImageDraw.Draw(frame)
            alpha = min(255, int(255 * min(1, p * 2.2)))
            if mode == "type":
                shown = max(1, int(len(line1 + line2) * min(1, p * 1.2)))
                combined = (line1 + "\n" + line2)[:shown + (1 if shown > len(line1) else 0)]
                lines = combined.split("\n")
            else:
                lines = [line1] + ([line2] if line2 else [])
            base_x = 82
            base_y = 365 if len(lines) == 1 else 325
            if mode == "slide":
                base_x += int((1 - min(1, p * 2)) * 60)
            if mode == "page":
                base_y += int((1 - min(1, p * 2)) * 36)
            title_font = font(74, True)
            sub_font = font(48, False)
            for n, text in enumerate(lines):
                fnt = title_font if n == 0 else sub_font
                fill = (52, 45, 42, alpha)
                shadow = (255, 255, 255, int(alpha * 0.72))
                y = base_y + n * 92
                draw.text((base_x + 3, y + 3), text, font=fnt, fill=shadow)
                draw.text((base_x, y), text, font=fnt, fill=fill)
            frame.convert("RGB").save(frames_dir / f"frame_{idx:04d}.jpg", quality=92)
            idx += 1
    return frames_dir


def encode_video(frames_dir, bgm_path):
    out = VIDEO / "opening_cm.mp4"
    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = None
    if ffmpeg_exe:
        cmd = [
            ffmpeg_exe,
            "-y",
            "-framerate",
            "30",
            "-i",
            str(frames_dir / "frame_%04d.jpg"),
            "-i",
            str(bgm_path),
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
        return out

    temp_dir = pathlib.Path(r"C:\Users\i58400am\Desktop\newapp\work")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_out = temp_dir / "opening_cm_trial_tmp.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_out), fourcc, 30, (1080, 1080))
    written = 0
    for frame_path in sorted(frames_dir.glob("frame_*.jpg")):
        data = np.fromfile(str(frame_path), dtype=np.uint8)
        frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if frame is None:
            continue
        writer.write(frame)
        written += 1
    writer.release()
    if written == 0:
        raise RuntimeError("No frames were written to video.")
    shutil.copy2(temp_out, out)
    make_preview_contact_sheet(frames_dir)
    return out


def make_preview_contact_sheet(frames_dir):
    picks = [0, 90, 180, 270, 360, 450]
    thumbs = []
    for idx in picks:
        path = frames_dir / f"frame_{idx:04d}.jpg"
        if path.exists():
            img = Image.open(path).convert("RGB").resize((270, 270), Image.Resampling.LANCZOS)
            thumbs.append(img)
    sheet = Image.new("RGB", (810, 540), "white")
    for i, img in enumerate(thumbs):
        sheet.paste(img, ((i % 3) * 270, (i // 3) * 270))
    sheet.save(VIDEO / "preview_contact_sheet.jpg", quality=92)


def main():
    prepare_backgrounds()
    make_banners()
    bgm = make_bgm()
    frames = make_video_frames()
    video = encode_video(frames, bgm)
    print(video)


if __name__ == "__main__":
    main()
