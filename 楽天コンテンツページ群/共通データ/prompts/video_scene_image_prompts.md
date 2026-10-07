# 動画用シーン背景プロンプト

## 基本方針

- 1シーンにつき1枚の専用背景画像を生成する。
- 商品表示シーンは生成背景ではなく、指定商品画像を中央に1枚ずつ表示する。
- 同じ背景画像を使う場合は連続させない。
- 連続使用が必要な場合は、パン・スクロール・明るさを固定し、文字アニメーションだけを変える。
- 画像内に日本語テキストは入れない。文字は動画生成時に後入れする。
- 動画は商品説明を詰め込まず、雑誌CMのように「気になる見出し」「コラムのポイント」「本音の一言」をテンポよく見せる。
- 1シーンの文字量は短くする。タイトル、問いかけ、キーワード程度に抑え、詳しい説明はHTML本文で読ませる。
- 商品画像は終盤のピックアップに寄せ、記事の世界観から自然につなげる。
- 演出パターンは、タイピング、見出しカットイン、ページめくり風、写真スライド、商品浮遊、短い余韻を組み合わせる。
- `video_focus`、`banner_focus`、`soft_product_link` は制作者向けの内部指示。動画やバナーにそのまま表示しない。
- 画面に表示する文言は `display_copy` として別に作る。視聴者に見せて自然な短文だけを使う。
- 「終盤で見せる」「ふわっと表示」「記事へ誘導」などの制作指示語は画面表示に使わない。
- 背景は新規生成したイメージ画像を使う。商品画像を引き伸ばす、ぼかす、薄く敷く、壁紙のように使う処理は禁止。
- 背景は壁紙風・抽象グラデーション・単なる模様にしない。生活シーン、手元、着替え、クローゼット、素材、商品利用イメージなど、コラム内容が伝わる写真風イメージを生成する。
- 生成画像は、文字を後入れする前提で余白を設計する。左側または中央に40〜55％程度の落ち着いた余白を残し、被写体は端か下部に寄せる。
- 背景画像に文字、ロゴ、商品パッケージ文字、架空ブランド名を入れない。
- 生成画像の被写体は「商品そのものの再現」ではなく、コラム内容を連想させる生活イメージにする。商品カードや実商品の表示は、別のピックアップシーンで実商品画像を使う。
- `images/` に入れる本文画像・ファーストビュー画像には、商品ページ画像を合成しない。`images/` は生成イメージ、生活シーン、知識説明用の背景だけにする。
- 商品ページ画像は `product_images/` に保存し、商品紹介パーツ、商品カード、または動画内の商品ピックアップシーンでのみ使う。
- クリック導線が必要な商品画像は、HTML上のリンク付き商品紹介パーツとして配置する。リンクできない差し込み画像の中へ商品画像を埋め込まない。
- 画面表示で `今日の目次` は使わない。代わりに `このコラムのポイント`、`選ぶ前に知りたいこと`、`知っておきたいポイント` など自然な見出しにする。
- 動画合成時に、横帯・白帯・黒帯・大きな透過パネルを常時敷かない。文字は生成背景に設計した余白へ直接載せる。
- 読みやすさが不足する場合は、帯ではなく文字の影、薄い縁取り、局所的なごく弱いグラデーションで調整する。
- 背景ごとに文字色を固定しない。文字を置くエリアの明るさ・色・柄の強さを見て、文字色と影を選ぶ。

## 文字合成ルール

動画生成時は、各シーンの背景を見てから `text_style` を決める。

| 背景の状態 | 文字色 | 補助処理 | 使う場面 |
|---|---|---|---|
| 明るい無地・白壁・淡い布 | 墨黒、チャコール、濃いグレー | 白影は使わず、薄い黒影を1〜2px | 余白が十分にあるシーン |
| 明るいが柄や衣類が多い | チャコール | 文字の外側にごく薄い白縁取り、または弱い黒影 | 服・素材が背景に入るシーン |
| 暗めの背景・濃色の服 | 白、アイボリー | 弱い黒影、必要なら淡い光彩 | 本音コピー、夜・落ち着いたシーン |
| 背景の明暗差が大きい | 背景の反対色寄り | 文字の近くだけ弱い局所グラデーション | 窓際、逆光、商品ピックアップ |
| 商品画像が重なる場面 | 背景ではなく商品カード外の余白に合わせる | 商品カードには影、文字には最小限の影 | ピックアップシーン |

### 禁止

- 読みやすさのために画面全体を白く薄める。
- 横帯、白帯、黒帯を常時敷く。
- 背景の良さが消えるほど強い半透明レイヤーを重ねる。
- 文字と帯の位置ズレが目立つ構成にする。
- すべてのシーンで同じ文字色・同じ影を使い回す。

### 推奨

- 文字は背景の余白に直接置く。
- 影は1〜3px程度の控えめなものにする。
- 白文字には黒影、黒文字には白光彩または薄い白縁取りを使う。
- 背景が複雑な場合は、文字位置を変えることを優先し、装飾で無理に読ませない。
- 1シーン内でタイトルとサブコピーの色差を少し付ける。

## 共通スタイル

Use case: ads-marketing  
Asset type: square video background for Rakuten content page  
Style/medium: photorealistic editorial apparel lifestyle photography  
Composition/framing: square 1:1, editorial lifestyle scene with deliberate clean negative space for Japanese overlay text  
Lighting/mood: bright airy daylight, premium, calm, reassuring  
Color palette: ivory, blush pink, taupe, muted burgundy accents  
Constraints: no text, no logo, no watermark, no medical feeling, no dark vignette, no product-package text  
Avoid: abstract wallpaper, blurred product-photo background, gradient-only background, clutter, cheap stock photo look, distorted hands, harsh contrast, clinical blue, plastic medical pads

## Scene 1: タイトル

Primary request: elegant apparel magazine commercial opening background for `{content_title}`, no visible text  
Scene/backdrop: bright dressing table near a window, refined handbag, folded lace underwear, soft flowers, calm morning preparation  
Subject: feminine daily essentials, no face, no body exposure  
Composition/framing: strong negative space on the left-center for large Japanese title overlay, subject details on right side, no text inside image

## Scene 2: 悩み・共感

Primary request: stylish magazine column teaser background expressing `{reading_hook}` with a calm everyday mood, no visible text  
Scene/backdrop: soft bright entryway or bedroom corner, handbag being prepared, scarf, knitwear, neutral clothes, product category subtly implied as an everyday item  
Subject: partial hands preparing a handbag, no face, no explicit body  
Composition/framing: negative space on the left for text, visual focus on hands and bag on the lower right, no text inside image

## Scene 3: このコラムのポイント

Primary request: refined editorial lifestyle image suggesting key points of the column `{column_angle}`, no visible text  
Scene/backdrop: open magazine, coffee cup, fabric swatches, wardrobe or dressing table, bright natural light  
Subject: readable mood but no actual letters, no logo, no watermark  
Composition/framing: dynamic diagonal composition with clean space for short Japanese teaser overlays, no readable text inside image

## Scene 4: 知識・本音の一言

Primary request: refined close-up background for a surprising knowledge or honest column statement about `{content_title}`, no visible text  
Scene/backdrop: soft linen surface, close-up material texture, partial hand gently touching the product or fabric edge  
Subject: tactile detail, softness, no face, no full body  
Composition/framing: detail on lower left or lower edge, clean negative space on upper/right area, no text inside image

## Scene 5: 商品ピックアップ

Primary request: bright elegant product pickup transition background for `{soft_product_link}`, no visible text  
Scene/backdrop: sunlit outfit preparation, neutral clothes, handbag, product category subtly placed  
Subject: apparel styling flat lay or everyday-use scene, no model body, no face  
Composition/framing: clean central negative space for text overlay and real product images added later, objects arranged around edges, no text inside generated background

## Scene 6: CTA

Primary request: refined bright closing background inviting viewers to read the Rakuten content column `{content_title}`, no visible text  
Scene/backdrop: clean wardrobe shelf and dressing area, related items arranged neatly, soft flowers, gentle daylight  
Subject: neatly arranged category essentials, no people, no body  
Composition/framing: calm balanced arrangement around lower and side edges, open center for final Japanese copy, no text inside image

## Category Example: 静電気・冬インナー

Scene/backdrop examples:
- winter morning bedroom with a woman’s hands choosing knitwear, cotton innerwear, skirt, and coat from a wardrobe
- close-up of hands touching soft cotton fabric and a wool knit on a bed, bright window light
- open magazine, coffee, fabric swatches, folded winter innerwear, knit cardigan, clean editorial flat lay
- entryway before going out in winter, coat, scarf, skirt, tote bag, partial hands only

Required composition:
- leave a calm blank area on the left or center for Japanese overlay text
- place hands, fabrics, wardrobe items, or clothing details on the right/lower side
- no readable text, no logo, no product package, no abstract wallpaper
