import math
import pathlib
import shutil

from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE = pathlib.Path(__file__).resolve().parent
GENERATED = pathlib.Path(r"C:\Users\i58400am\.codex\generated_images\01a03bd9-3f16-70d1-81ca-80d9bbc91430")

SOURCES = {
    "003_pose_seated_base.jpg": "call_xLWNQTao1WOiIXfDNCtV5BXF.png",
    "003_pose_lie_base.jpg": "call_GSlpID5LMVdSLVBzavcY4ggo.png",
    "003_pose_stand_base.jpg": "call_SbpbefBphlYF2Rap4Vrf3FlC.png",
    "003_pose_prepare_base.jpg": "call_UOERgbIGMg4q1jPAacKtH0BH.png",
    "003_pose_relax_base.jpg": "call_tGyGiBOYF8Qx649H6J2SroJJ.png",
    "003_pose_ng_base.jpg": "call_nk41D2AOHtrX89iZCbxe5Vwn.png",
    "003_pose_daily_base.jpg": "call_fff4cV77Pv7rGMJbJmcKWKhr.png",
}


def font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\yumindb.ttf" if bold else r"C:\Windows\Fonts\yumin.ttf",
        r"C:\Windows\Fonts\YuMincho.ttc",
        r"C:\Windows\Fonts\meiryo.ttc",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def line_font(size):
    candidates = [r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\YuGothM.ttc"]
    for path in candidates:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def label(img, xy, number, text):
    x, y = xy
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    fill = (58, 51, 47, 245)
    bubble = (255, 252, 247, 225)
    accent = (173, 117, 106, 245)
    body = line_font(34)
    small = line_font(28)
    tw = max(draw.textlength(text, font=body), 180)
    draw.rounded_rectangle((x, y, x + tw + 96, y + 78), radius=28, fill=bubble)
    draw.ellipse((x + 18, y + 16, x + 62, y + 60), fill=accent)
    draw.text((x + 31, y + 22), str(number), font=small, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((x + 76, y + 20), text, font=body, fill=fill)
    overlay = overlay.filter(ImageFilter.GaussianBlur(0.2))
    img.alpha_composite(overlay)


def save_base_images():
    for out_name, source_name in SOURCES.items():
        src = GENERATED / source_name
        if not src.exists():
            raise FileNotFoundError(src)
        shutil.copy2(src, BASE / out_name)


def make_seated():
    img = Image.open(BASE / "003_pose_seated_base.jpg").convert("RGBA")
    label(img, (72, 110), 1, "背すじを長く")
    label(img, (72, 210), 2, "肩の力を抜く")
    label(img, (72, 310), 3, "足は自然に")
    img.convert("RGB").save(BASE / "003_pose_seated_text.jpg", quality=94)


def make_lie():
    img = Image.open(BASE / "003_pose_lie_base.jpg").convert("RGBA")
    label(img, (74, 120), 1, "息を止めない")
    label(img, (74, 220), 2, "お腹は固めすぎない")
    label(img, (74, 320), 3, "ゆっくり休む")
    img.convert("RGB").save(BASE / "003_pose_lie_text.jpg", quality=94)


def make_stand():
    img = Image.open(BASE / "003_pose_stand_base.jpg").convert("RGBA")
    label(img, (72, 110), 1, "背すじを長く")
    label(img, (72, 210), 2, "足幅は自然に")
    label(img, (72, 310), 3, "肩は楽に")
    img.convert("RGB").save(BASE / "003_pose_stand_text.jpg", quality=94)


def make_prepare():
    img = Image.open(BASE / "003_pose_prepare_base.jpg").convert("RGBA")
    label(img, (72, 110), 1, "まず呼吸を整える")
    label(img, (72, 210), 2, "肩を下げる")
    label(img, (72, 310), 3, "弱い力から始める")
    img.convert("RGB").save(BASE / "003_pose_prepare_text.jpg", quality=94)


def make_relax():
    img = Image.open(BASE / "003_pose_relax_base.jpg").convert("RGBA")
    label(img, (70, 110), 1, "ゆっくり吐く")
    label(img, (70, 210), 2, "力を抜く時間も")
    label(img, (70, 310), 3, "無理なら休む")
    img.convert("RGB").save(BASE / "003_pose_relax_text.jpg", quality=94)


def make_ng():
    img = Image.open(BASE / "003_pose_ng_base.jpg").convert("RGBA")
    label(img, (72, 110), 1, "肩が上がる")
    label(img, (72, 210), 2, "手に力が入る")
    label(img, (72, 310), 3, "気づいたら休む")
    img.convert("RGB").save(BASE / "003_pose_ng_text.jpg", quality=94)


def make_daily():
    img = Image.open(BASE / "003_pose_daily_base.jpg").convert("RGBA")
    label(img, (72, 110), 1, "朝のついでに")
    label(img, (72, 210), 2, "姿勢を思い出す")
    label(img, (72, 310), 3, "短く続ける")
    img.convert("RGB").save(BASE / "003_pose_daily_text.jpg", quality=94)


def make_contact_sheet():
    files = [
        "003_pose_prepare_text.jpg",
        "003_pose_seated_text.jpg",
        "003_pose_lie_text.jpg",
        "003_pose_stand_text.jpg",
        "003_pose_relax_text.jpg",
        "003_pose_ng_text.jpg",
        "003_pose_daily_text.jpg",
    ]
    sheet = Image.new("RGB", (2048, 1024), (255, 255, 255))
    for i, name in enumerate(files):
        im = Image.open(BASE / name).convert("RGB").resize((512, 512), Image.Resampling.LANCZOS)
        sheet.paste(im, ((i % 4) * 512, (i // 4) * 512))
    sheet.save(BASE / "003_pose_text_contact_sheet.jpg", quality=92)


def main():
    save_base_images()
    make_seated()
    make_lie()
    make_stand()
    make_prepare()
    make_relax()
    make_ng()
    make_daily()
    make_contact_sheet()


if __name__ == "__main__":
    main()
