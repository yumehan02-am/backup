# 納品フォルダテンプレート

## フォルダ

- `images/`
  - 生成イメージ画像
  - バナー
  - 章タイトル画像
- `video/`
  - 動く目次CM
  - 動画用背景
  - BGM
- `product_images/`
  - 商品ページ画像
  - RMSの商品紹介パーツ用
- `data/`
  - 商品ID
  - 使用したCSV抜粋
  - パーツ設計
  - 参照素材の使用記録

## ファイル

- `page_copy.md`
- `rakuten_parts_plan.csv`
- `video_storyboard.csv`
- `banner_plan.csv`
- `product_ids.csv`
- `asset_notes.md`

## 参照素材

実写風生成画像の標準は `reference_mode=none`。

イラスト主体コンテンツの標準は `reference_mode=illustration_style`。

任意参照素材を使った場合は、参照フォルダ、画像名、参照目的を `notes.md` または `asset_notes.md` に記録する。

## 注意

`images/` はリンクできない画像として扱うため、商品画像を入れない。

商品画像は `product_images/` に分け、楽天のリンク可能な商品紹介パーツで使う。
