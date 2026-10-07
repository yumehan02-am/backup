# scripts

ここには、今後の実務用生成スクリプトを置きます。

過去の試作用スクリプトは移動せず、必要な考え方だけを新しい仕様に反映します。

## 今後作るスクリプト候補

- `generate_content_proposals.py`
  - CSVから企画案を作る
- `build_page_assets.py`
  - 選ばれた企画から本文、画像計画、動画絵コンテを作る
- `render_video_cm.py`
  - 動く目次CMを生成する
  - 新規作成の標準は `720 x 960` の縦長MP4
  - 背景素材は `1200 x 1200` の正方形生成画像を使い、編集工程で縦長へ切り出す
- `embed_mp4_thumbnail.py`
  - 完成MP4に `images/xxx_thumbnail.jpg` をカバー画像として埋め込む
  - 例: `python scripts/embed_mp4_thumbnail.py production/004_xxx/納品用/video/opening_cm_004.mp4 production/004_xxx/納品用/images/004_thumbnail.jpg`
- `export_paste_tsv.py`
  - `page_copy.md` と `rakuten_parts_plan.csv` を、楽天コンテンツページへ上から順番に貼りやすい `page_paste_blocks.tsv` に変換する
  - `page_copy.md` には本文だけを入れ、`画像案:` や `対象商品ID:` などの制作メモは入れない
  - TSVは `タイトル画像 → メインタイトル40文字以内 → 動画 → 動画下本文 → 小タイトル20文字以内 → バナー → 本文 → 関連商品` の順にする
  - アクセント用シチュエーション画像がある場合は、本文ブロックの後、次の小タイトルの前に挿入する
  - アクセント用シチュエーション画像は `rakuten_parts_plan.csv` で `part_type=accent_image`、`placement=after_body`、`after_section=章番号` を指定する
  - 通常の章バナーを明示配置する場合は `part_type=banner`、`placement=before_body`、`after_section=章番号` を指定する
  - `placement` と `after_section` がない既存データは、従来通り章バナーを上から順に割り当てる
  - 出力後は `小タイトル → 画像 → 本文` の対応を校正し、季節・清潔感・まとめなどの画像が不自然な章に入っていないか確認する
  - 本文ブロックはバナーとの余白用に、貼り付け内容の先頭へ改行を1つ入れる
  - 画像ブロックは `rakuten_parts_plan.csv` の `file_or_source` から作る
  - 関連商品ブロックは `product_ids.csv` から商品IDを展開する
  - 画像URLは `https://image.rakuten.co.jp/u-b-yumehan/cabinet/contents/` + ファイル名で作る
  - 例: `python scripts/export_paste_tsv.py 006 007 008 009`
