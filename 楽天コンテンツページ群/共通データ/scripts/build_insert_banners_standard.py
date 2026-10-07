import pathlib

from PIL import Image, ImageDraw, ImageFont, ImageFilter


BASE = pathlib.Path(__file__).resolve().parent
BG = BASE / "generated_banners" / "backgrounds"
OUT = BASE / "generated_banners"
OUT.mkdir(exist_ok=True)

W, H = 1600, 520
INK = (78, 45, 56, 255)
SOFT = (112, 83, 88, 235)
WHITE = (255, 255, 255, 245)


def font(size, style="mincho"):
    if style == "mincho_light":
        names = [r"C:\Windows\Fonts\yuminl.ttf", r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc"]
    elif style == "mincho":
        names = [r"C:\Windows\Fonts\yumin.ttf", r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc"]
    else:
        names = [r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc"]
    for name in names:
        if pathlib.Path(name).exists():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default()


F78 = font(78, "mincho_light")
F56 = font(56, "mincho_light")
F38 = font(38, "mincho")
F30 = font(30, "gothic")


def cover(path):
    img = Image.open(path).convert("RGBA")
    ratio = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    x = (img.width - W) // 2
    y = (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def tracked_width(draw, text, fnt, tracking):
    total = 0
    for i, ch in enumerate(text):
        box = draw.textbbox((0, 0), ch, font=fnt)
        total += box[2] - box[0]
        if i < len(text) - 1:
            total += tracking
    return total


def draw_tracked(draw, xy, text, fnt, fill, tracking=0):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        box = draw.textbbox((0, 0), ch, font=fnt)
        x += box[2] - box[0] + tracking


def draw_lines(draw, x, y, rows, fnt, fill, tracking=0, gap=16, shadow=True):
    for row in rows:
        if shadow:
            draw_tracked(draw, (x + 2, y + 2), row, fnt, (255, 255, 255, 210), tracking)
        draw_tracked(draw, (x, y), row, fnt, fill, tracking)
        box = draw.textbbox((0, 0), row, font=fnt)
        y += (box[3] - box[1]) + gap


def add_soft_panel(img, align):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if align == "left":
        box = (70, 64, 785, 456)
    elif align == "right":
        box = (815, 64, 1530, 456)
    else:
        box = (250, 66, 1350, 454)
    d.rounded_rectangle(box, radius=22, fill=(255, 255, 255, 176))
    blur = layer.filter(ImageFilter.GaussianBlur(8))
    return Image.alpha_composite(img, blur), box


def banner(filename, bg_name, title, body, align="left"):
    img = cover(BG / bg_name)
    img, box = add_soft_panel(img, align)
    d = ImageDraw.Draw(img)
    x = box[0] + 54
    y = box[1] + 62
    draw_lines(d, x, y, title.split("\n"), F56, INK, tracking=3, gap=12)
    d.line((x, y + 160, box[2] - 54, y + 160), fill=(130, 94, 100, 115), width=2)
    draw_lines(d, x, y + 194, body.split("\n"), F30, SOFT, tracking=1, gap=14, shadow=False)
    img.convert("RGB").save(OUT / filename, quality=92, optimize=True)


def guide_banner():
    img = cover(BG / "02_absorbency_bg.png")
    img, box = add_soft_panel(img, "center")
    d = ImageDraw.Draw(img)
    title = "吸水量で選ぶ"
    x = (W - tracked_width(d, title, F56, 4)) / 2
    draw_tracked(d, (x + 2, 94 + 2), title, F56, WHITE, 4)
    draw_tracked(d, (x, 94), title, F56, INK, 4)
    items = [
        ("20cc〜30cc", "軽失禁・尿もれ用"),
        ("50cc", "中等度・長時間用"),
        ("150cc以上", "介護用・重度用"),
    ]
    card_w = 330
    for i, (amount, desc) in enumerate(items):
        cx = 292 + i * 390
        d.rounded_rectangle((cx, 230, cx + card_w, 382), radius=16, fill=(255, 255, 255, 218), outline=(155, 112, 120, 120), width=2)
        aw = tracked_width(d, amount, F38, 1)
        draw_tracked(d, (cx + (card_w - aw) / 2, 260), amount, F38, INK, 1)
        dw = tracked_width(d, desc, F30, 0)
        draw_tracked(d, (cx + (card_w - dw) / 2, 323), desc, F30, SOFT, 0)
    img.convert("RGB").save(OUT / "02_absorbency_guide_banner.jpg", quality=92, optimize=True)


def main():
    banner(
        "01_problem_banner.jpg",
        "01_problem_bg.png",
        "外出中の不安を\n少し軽く",
        "予定を楽しみたい日も\n下着選びで心地よく備える",
        "left",
    )
    guide_banner()
    banner(
        "03_material_banner.jpg",
        "03_material_bg.png",
        "肌にふれるものだから\n素材で選ぶ",
        "やわらかな肌ざわりと\n普段使いしやすいデザインへ",
        "right",
    )
    banner(
        "04_cta_banner.jpg",
        "04_cta_bg.png",
        "自分に合う一枚を\n見つける",
        "吸水量・素材・形から\n毎日に寄りそうショーツ選びを",
        "center",
    )


if __name__ == "__main__":
    main()
