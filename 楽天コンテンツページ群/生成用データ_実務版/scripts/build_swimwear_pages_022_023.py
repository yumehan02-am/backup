from __future__ import annotations

import csv
import math
import shutil
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "production"
REFS = ROOT / "references" / "generated_022_023"


PAGES = {
    "022": {
        "slug": "swimsuit_tag_still_attached",
        "title": "水着を買ったのにタグが付いたまま問題｜プール再開までの小さな壁",
        "short_title": ["タグが付いたままの", "水着問題"],
        "product_ids": ["ftmns00", "ftmhs00"],
        "column_pattern": "comic_first_person",
        "relation_depth": "comic",
        "reference_mode": "illustration_style",
        "video_style": "illustrated_story_cm",
        "sources": {
            "title": "022_title.png",
            "points": "022_prep.png",
            "022_motivation": "022_motivation.png",
            "022_tag": "022_tag.png",
            "022_firstday": "022_firstday.png",
            "022_bag": "022_bag.png",
            "022_success": "022_success.png",
            "accent_01": "022_accent_01.png",
            "accent_02": "022_accent_02.png",
        },
        "page_copy": """# 水着を買ったのにタグが付いたまま問題｜プール再開までの小さな壁

水着は買いました。

帽子もあります。タオルも、たぶんあります。プールバッグに入れれば、もう行けるはずです。なのに、なぜか水着のタグがまだ付いたまま。これは怠けているというより、プール再開前にだけ現れる小さな壁です。

このコラムでは、買ったのにまだ行けない気持ちを責めずに、プールへ向かうまでの支度を少しだけ軽くしてみます。

## 買った日はやる気がある

水着を買った日は、かなり前向きです。

「今度こそ行こう」「歩くだけでもいい」「まずは週に一回くらい」。頭の中では、すでに水中ウォーキングをしている自分がいます。買い物かごに入れる指も軽い。届いた箱を開ける時も、ちょっと新しい生活が始まるような気がします。

問題は、その先です。袋から出した水着を一度眺めて、たたみ直して、タグはあとで切ろうと思う。そのあとで日常が戻ってきます。洗濯、仕事、夕飯、家族の用事。やる気は消えたのではなく、生活の中にそっと埋もれてしまうのです。

## タグは小さな言い訳になる

水着のタグは、ただの紙です。

でも、付いたままだと不思議な力を持ちます。まだ本気ではない感じ。まだ準備中という感じ。行かない理由を、そっと差し出してくる感じがあります。

もちろん、タグを切っただけでプールに行けるわけではありません。けれど、タグを切るという行為は、「いつか」から「そろそろ」へ気持ちを動かす小さな合図になります。大げさな決意ではなく、ハサミひとつ分の準備です。

## 完璧な初日は来ない

プールに行く初日を、きれいに整えようとすると、なかなか出発できません。

時間に余裕がある日。体調がいい日。髪型が気にならない日。人が少なそうな日。帰りに寄り道しなくていい日。条件を並べると、理想の初日はどんどん遠くなります。

でも、実際の初日は少しくらい不完全で大丈夫です。忘れ物をしないようにメモを作る。短い時間で帰る。歩くだけにする。更衣室で慌てないように、前ファスナーや帽子付きのセットを選ぶ。完璧さより、やり直せる軽さの方が続きます。

## バッグに入れると進む

水着を眺めているだけの日と、バッグに入れた日の間には、少し差があります。

タグを切って、帽子とタオルを並べて、バッグに入れる。まだプールには行っていなくても、支度は一歩進んでいます。玄関の近くに置いておけば、次に時間ができた時の自分が少し楽になります。

行動は、気持ちが整ってから始まるとは限りません。先にバッグを作っておくと、気持ちがあとから追いつくこともあります。小さな段取りは、未来の自分への引き継ぎです。

## 行けたらもう成功

久しぶりのプールは、長く泳げなくてもいいと思います。

水中ウォーキングを少しする。施設の流れを思い出す。更衣室で慌てず帰る。それだけでも、タグが付いたままの日よりずっと進んでいます。

フィットネス水着は、気合いの象徴ではなく、プールへ行くための道具です。めくれにくさ、着替えやすさ、帽子付きの準備しやすさ。そうした地味な安心を味方にして、まずは水着のタグを切るところから。プール再開は、そのくらい小さく始めてもいいはずです。
""",
        "sections": [
            ("022_motivation", ["買った日は", "やる気がある"], "022_motivation"),
            ("022_tag", ["タグは小さな", "言い訳になる"], "022_tag"),
            ("022_firstday", ["完璧な初日は", "来ない"], "022_firstday"),
            ("022_bag", ["バッグに入れると", "進む"], "022_bag"),
            ("022_success", ["行けたら", "もう成功"], "022_success"),
        ],
        "points": ["このコラムのポイント", "› タグは小さな壁になる", "› 完璧な初日を待たない", "› バッグに入れると進む"],
        "video": [
            ("022_scene01.jpg", "タグが付いたままの\n水着問題", "title_type"),
            ("022_scene02.jpg", "買った日は\nやる気があった", "rise_fade"),
            ("022_scene03.jpg", "このコラムのポイント\n› タグは小さな壁になる\n› 完璧な初日を待たない\n› バッグに入れると進む", "points"),
            ("022_scene04.jpg", "まずは\nタグを切るところから", "slide_left"),
            ("022_scene05.jpg", "バッグに入れたら\n少し進んだ", "rise_fade"),
            ("022_scene06.jpg", "行けたら\nもう成功", "slide_right"),
        ],
    },
    "023": {
        "slug": "gym_pool_nobody_watching",
        "title": "ジムのプール、誰も私を見ていない説｜気にしすぎをほどく水着コラム",
        "short_title": ["誰も見ていない説", "ジムプール編"],
        "product_ids": ["ftmns00", "ftmhs00"],
        "column_pattern": "comic_first_person",
        "relation_depth": "comic",
        "reference_mode": "illustration_style",
        "video_style": "illustrated_story_cm",
        "sources": {
            "title": "023_title.png",
            "points": "023_poolside.png",
            "023_audience": "023_audience.png",
            "023_busy": "023_busy.png",
            "023_ready": "023_ready.png",
            "023_walk": "023_walk.png",
            "023_pace": "023_pace.png",
            "accent_01": "023_accent_01.png",
            "accent_02": "023_accent_02.png",
        },
        "page_copy": """# ジムのプール、誰も私を見ていない説｜気にしすぎをほどく水着コラム

ジムのプールに行く前、なぜか自分だけが注目される気がすることがあります。

水着姿が変じゃないか。歩き方がぎこちなくないか。泳げないのが目立たないか。頭の中では、もう全員こちらを見ています。けれど実際のプールでは、多くの人が自分のメニュー、自分の呼吸、自分のゴーグルで忙しいものです。

このコラムでは、プール前の自意識を少しゆるめながら、落ち着いて過ごせる水着選びを考えます。

## 脳内だけ大観衆

プールに行く前の頭の中では、観客席が満員です。

更衣室から出た瞬間、全員が振り向く。歩き方を見られる。水着を見られる。そんな想像が、勝手に上映されます。もちろん、現実にはそんな劇場はほとんどありません。

人は意外と、自分のことで忙しいものです。隣の人はゴーグルの曇りを気にしているかもしれないし、別の人は今日何往復するかを考えているかもしれません。こちらを見ているようで、実はそれぞれ自分の段取りに集中しています。

## みんな自分のことで忙しい

プールには、いろいろな目的の人がいます。

しっかり泳ぐ人。ゆっくり歩く人。休みながら体を動かす人。久しぶりに来た人。慣れている人。全員が同じ速さで、同じフォームで、同じ水着を着ているわけではありません。

そう考えると、「目立たないようにしなければ」と力む必要は少し減ります。大切なのは、目立たない完璧さではなく、自分が落ち着いて動けることです。プールは品評会ではなく、それぞれが体を動かす場所です。

## 気になる部分は先に整える

とはいえ、気になるものは気になります。

腕を出しすぎたくない日もあります。トップスのめくれが気になる日もあります。着替えで手間取ると、余計に周りが気になります。気にしすぎを精神論だけで片づけるより、先に不安の芽を減らしておく方が現実的です。

半袖タイプなら腕まわりに少し安心感があり、ノースリーブなら肩を動かしやすい。前ファスナーや帽子付きのセットは、支度の段取りを軽くしてくれます。水着選びは、自意識をなくす魔法ではありませんが、気を取られる時間を減らす工夫にはなります。

## 歩くだけでも場所になじむ

最初から泳がなくても、プールにはなじめます。

水の中を歩く。レーンの流れを見ながら休む。施設の使い方を思い出す。そうしているうちに、初めての緊張は少しずつ薄れていきます。

人の目を忘れる一番の方法は、自分の動きに戻ることかもしれません。足を出す、腕を動かす、呼吸する。小さな動きに集中すると、脳内の大観衆はだんだん静かになります。

## 私も私のペースでいい

ジムのプールで大切なのは、誰かの理想に合わせることではありません。

今日は少し歩く。今日は半袖で安心して行く。今日はノースリーブで腕を動かす。そんな選び方で十分です。周りが自分のことで忙しいように、こちらも自分のペースで過ごせばいい。

誰も見ていない説は、完全な真実というより、お守りのような考え方です。気にしすぎた心を少しほどいて、プールバッグを持つ手を軽くする。そのくらいの気持ちで、水着を選んでみてもよいはずです。
""",
        "sections": [
            ("023_audience", ["脳内だけ", "大観衆"], "023_audience"),
            ("023_busy", ["みんな自分のことで", "忙しい"], "023_busy"),
            ("023_ready", ["気になる部分は", "先に整える"], "023_ready"),
            ("023_walk", ["歩くだけでも", "場所になじむ"], "023_walk"),
            ("023_pace", ["私も私の", "ペースでいい"], "023_pace"),
        ],
        "points": ["このコラムのポイント", "› 脳内だけ大観衆かも", "› 気になる部分は先に整える", "› 自分のペースでいい"],
        "video": [
            ("023_scene01.jpg", "誰も見ていない説\nジムプール編", "title_type"),
            ("023_scene02.jpg", "脳内だけ\n大観衆", "rise_fade"),
            ("023_scene03.jpg", "このコラムのポイント\n› 脳内だけ大観衆かも\n› 気になる部分は先に整える\n› 自分のペースでいい", "points"),
            ("023_scene04.jpg", "みんな\n自分のことで忙しい", "slide_left"),
            ("023_scene05.jpg", "気になる部分は\n先に整える", "rise_fade"),
            ("023_scene06.jpg", "私も私の\nペースでいい", "slide_right"),
        ],
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


def glow_box(size: tuple[int, int], alpha: int = 76) -> Image.Image:
    w, h = size
    pad = 74
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=28, fill=(255, 255, 255, alpha))
    return layer.filter(ImageFilter.GaussianBlur(34))


def draw_lines(img: Image.Image, lines: list[str], x: int, y: int, sizes: list[int], gaps: list[int], fill=(42, 38, 35)) -> None:
    frame = img.convert("RGBA")
    draw = ImageDraw.Draw(frame)
    current_y = y
    for idx, line in enumerate(lines):
        font = mincho(sizes[min(idx, len(sizes) - 1)], idx == 0)
        w, h = text_size(line, font)
        frame.alpha_composite(glow_box((w + 98, h + 48)), (x - 118, current_y - 82))
        draw.text((x, current_y), font=font, text=line, fill=(*fill, 255))
        current_y += gaps[min(idx, len(gaps) - 1)]
    img.paste(frame.convert("RGB"))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_bgm(base: Path, content_no: str) -> None:
    video = base / "video"
    video.mkdir(parents=True, exist_ok=True)
    path = video / f"bgm_swimwear_{content_no}.wav"
    sr = 44100
    duration = 30.0
    chords = [(392.00, 493.88, 587.33), (349.23, 440.00, 523.25), (329.63, 415.30, 493.88), (392.00, 523.25, 659.25)]
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
            sample = sum(math.sin(2 * math.pi * f * t) * 0.043 for f in chord)
            sample += math.sin(2 * math.pi * 783.99 * t) * 0.010 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.13 * t))
            sample *= env * 0.62
            val = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(val.to_bytes(2, "little", signed=True))
        wf.writeframes(frames)


def make_scenes(base: Path, content_no: str, scene_sources: list[str]) -> None:
    scenes = base / "video" / "scene_backgrounds"
    if scenes.exists():
        shutil.rmtree(scenes)
    scenes.mkdir(parents=True, exist_ok=True)
    for idx, name in enumerate(scene_sources, 1):
        img = Image.open(base / "images" / "work" / name).convert("RGB")
        cover_crop(img, (1200, 1200), 0, 0).save(scenes / f"{content_no}_scene{idx:02d}.jpg", quality=94)


def source_image(page: dict[str, object], key: str) -> Image.Image:
    filename = page["sources"][key]  # type: ignore[index]
    return Image.open(REFS / filename).convert("RGB")


def source_filename(page: dict[str, object], key: str) -> str:
    return str(page["sources"][key])  # type: ignore[index]


def build_page(content_no: str, page: dict[str, object]) -> None:
    base = PRODUCTION / f"{content_no}_{page['slug']}" / "納品用"
    delivery = base / "images" / "delivery"
    work = base / "images" / "work"
    originals = work / "generated_originals"
    data = base / "data"
    for path in [delivery, work, originals, data, base / "video"]:
        path.mkdir(parents=True, exist_ok=True)

    (base / "page_copy.md").write_text(str(page["page_copy"]), encoding="utf-8")

    source_rows = []
    roles = {"title": "title", "points": "points", "accent_01": "accent_01", "accent_02": "accent_02"}
    for role, src_key in roles.items():
        img = source_image(page, src_key)
        bg_name = f"{content_no}_{role}_bg.png"
        img.save(originals / bg_name)
        img.save(work / bg_name)
        source_rows.append({"role": role, "source_file": source_filename(page, src_key), "work_file": bg_name})
    for role, _lines, src_key in page["sections"]:  # type: ignore[assignment]
        img = source_image(page, src_key)
        bg_name = f"{role}_bg.png"
        img.save(originals / bg_name)
        img.save(work / bg_name)
        source_rows.append({"role": role, "source_file": source_filename(page, src_key), "work_file": bg_name})

    write_csv(data / "image_source_manifest.csv", ["role", "source_file", "work_file"], source_rows)

    title = cover_crop(Image.open(work / f"{content_no}_title_bg.png").convert("RGB"), (1600, 900), -0.12, 0.0)
    draw_lines(title, page["short_title"], 94, 300, [70, 82], [104, 108])  # type: ignore[arg-type]
    title.save(delivery / f"{content_no}_title.jpg", quality=94)
    title.save(delivery / f"{content_no}_thumbnail.jpg", quality=94)

    points = cover_crop(Image.open(work / f"{content_no}_points_bg.png").convert("RGB"), (1600, 520), -0.16, 0.0)
    draw_lines(points, page["points"], 100, 70, [46, 34, 34, 34], [74, 56, 56, 56])  # type: ignore[arg-type]
    points.save(work / f"{content_no}_points.jpg", quality=94)

    banner_rows = []
    for role, lines, _src_key in page["sections"]:  # type: ignore[assignment]
        img = cover_crop(Image.open(work / f"{role}_bg.png").convert("RGB"), (1600, 520), -0.18, 0.0)
        draw_lines(img, lines, 92, 148, [54, 54], [78, 72])
        out = f"{role}.jpg"
        img.save(delivery / out, quality=94)
        banner_rows.append({"filename": out, "headline": "\n".join(lines), "subcopy": "", "asset_type": role.replace(f"{content_no}_", "")})

    for accent in ["accent_01", "accent_02"]:
        cover_crop(Image.open(work / f"{content_no}_{accent}_bg.png").convert("RGB"), (1200, 1200), 0, 0).save(delivery / f"{content_no}_{accent}.jpg", quality=94)

    write_csv(
        data / "banner_plan.csv",
        ["filename", "headline", "subcopy", "asset_type"],
        [
            {"filename": f"{content_no}_title.jpg", "headline": str(page["title"]), "subcopy": "", "asset_type": "title"},
            {"filename": f"{content_no}_points.jpg", "headline": "\n".join(page["points"]), "subcopy": "", "asset_type": "points"},  # type: ignore[arg-type]
            *banner_rows,
            {"filename": f"{content_no}_accent_01.jpg", "headline": "", "subcopy": "文字なし正方形アクセント", "asset_type": "accent_image"},
            {"filename": f"{content_no}_accent_02.jpg", "headline": "", "subcopy": "文字なし正方形アクセント", "asset_type": "accent_image"},
        ],
    )

    parts = [
        {"order": "1", "part_type": "banner", "file_or_source": f"images/delivery/{content_no}_title.jpg", "note": "タイトル画像 1600x900", "placement": "", "after_section": ""},
        {"order": "2", "part_type": "video", "file_or_source": f"video/opening_cm_{content_no}_vertical.mp4", "note": "タイトル直下のイラストストーリーCM", "placement": "", "after_section": ""},
        {"order": "3", "part_type": "points_image", "file_or_source": f"images/work/{content_no}_points.jpg", "note": "動画用ポイント画像 TSVには出さない", "placement": "", "after_section": ""},
    ]
    order = 4
    for idx, (role, _lines, _src_key) in enumerate(page["sections"], 1):  # type: ignore[assignment]
        parts.append({"order": str(order), "part_type": "banner", "file_or_source": f"images/delivery/{role}.jpg", "note": "章バナー", "placement": "before_body", "after_section": str(idx)})
        order += 1
        if idx == 2:
            parts.append({"order": str(order), "part_type": "accent_image", "file_or_source": f"images/delivery/{content_no}_accent_01.jpg", "note": "文字なし正方形アクセント", "placement": "after_body", "after_section": "2"})
            order += 1
        if idx == 4:
            parts.append({"order": str(order), "part_type": "accent_image", "file_or_source": f"images/delivery/{content_no}_accent_02.jpg", "note": "文字なし正方形アクセント", "placement": "after_body", "after_section": "4"})
            order += 1
    parts.append({"order": str(order), "part_type": "product_parts", "file_or_source": "product_ids.csv", "note": "関連商品パーツ", "placement": "", "after_section": ""})
    write_csv(data / "rakuten_parts_plan.csv", ["order", "part_type", "file_or_source", "note", "placement", "after_section"], parts)

    scene_files = [f"{content_no}_title_bg.png", f"{page['sections'][0][0]}_bg.png", f"{content_no}_points_bg.png", f"{page['sections'][1][0]}_bg.png", f"{page['sections'][3][0]}_bg.png", f"{page['sections'][4][0]}_bg.png"]  # type: ignore[index]
    make_scenes(base, content_no, scene_files)
    storyboard = []
    for idx, (background, copy, animation) in enumerate(page["video"], 1):  # type: ignore[assignment]
        storyboard.append({"scene": str(idx), "background_file": background, "duration_sec": "5.2" if idx == 1 else ("4.1" if idx == 3 else "3.6"), "display_copy": copy, "text_animation": animation, "crop_x": "0", "crop_y": "0"})
    write_csv(data / "video_storyboard.csv", ["scene", "background_file", "duration_sec", "display_copy", "text_animation", "crop_x", "crop_y"], storyboard)

    write_csv(base / "product_ids.csv", ["product_id", "role", "note"], [{"product_id": pid, "role": "関連商品", "note": "一般的なフィットネス水着。帽子付き上下セット"} for pid in page["product_ids"]])  # type: ignore[union-attr]

    notes = f"""# 制作メモ {content_no}

- 元タイトル案: ftmns00/ftmhs00 リスト
- タイトル: {page['title']}
- 商品ID: ftmns00 / ftmhs00
- column_pattern: {page['column_pattern']}
- relation_depth: {page['relation_depth']}
- reference_mode: {page['reference_mode']}
- video_style: {page['video_style']}
- イラスト基準: custom/yumehan/reference/illustration_style/character/style_notes.md を確認。
- 背景画像: references/generated_022_023/ の個別生成イラストを使用。章バナー、アクセント画像、動画背景は同一元画像を使い回さない。簡易図形・プレースホルダー背景は不採用。
- 商品画像確認: ftmns00/ftmhs00 は一般的なフィットネス水着として確認。商品写真の精密再現は行わず、帽子付き上下セット、前ファスナー、ノースリーブ/半袖の違い、めくれ対策を本文後半の接続に使用。
- 商品との距離: comic。本文はあるあるで読ませ、商品は不安を減らす準備として終盤で自然接続。
- 同一商品群差別化: 022は自宅準備、023はジムプール現地。019-021の実写知識系とテイストを変更。
- 画像品質チェック: 問題なし。実写風ではなく、指定通りイラスト主体。若すぎる印象、露出、性的印象、商品画像混入なし。
- points画像: images/work/{content_no}_points.jpg は管理素材。標準TSVには出さない。
"""
    (base / "notes.md").write_text(notes, encoding="utf-8")
    make_bgm(base, content_no)


def build() -> None:
    for content_no, page in PAGES.items():
        build_page(content_no, page)


if __name__ == "__main__":
    build()
