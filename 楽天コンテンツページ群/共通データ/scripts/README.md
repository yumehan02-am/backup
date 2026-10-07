# 共通スクリプト

## generate_video_standard_scene_images.py

現在の標準動画ラインのベーススクリプトです。

- 1000px正方形
- BGM付きMP4
- `MUSIC_STYLE` でジャンル別BGMを切り替え
- アパレル寄りの明朝フォント
- 商品表示シーン以外は1シーン1背景画像
- 商品画像は中央に1枚ずつ浮かばせる

次ページで使う場合は、ページ固有フォルダへコピーしてから以下を差し替えます。

- `SCENE_IMG`: そのページ用のシーン背景フォルダ
- `PRODUCT`: そのページ用の商品画像フォルダ
- `MUSIC_STYLE`: ページジャンルに合うBGMプロファイル
- `scenes`: タイトル、悩み、選び方、素材、ベネフィット、CTA文言
- `final_video`: 出力ファイル名

利用できる `MUSIC_STYLE`:

- `apparel_soft`: 下着、アパレル、インナー向け
- `senior_care`: 介護用品、シニア、高吸水系向け
- `beauty_clean`: 美容、肌ざわり、清潔感訴求向け
- `gift_warm`: ギフト、母の日、敬老の日向け
- `season_bright`: 季節商品、イベント、キャンペーン向け

## build_insert_banners_standard.py

横長バナーを作るための標準サンプルです。

- 背景画像は生成画像を使用
- 日本語テキストはPillowで後入れ
- サイズは1600px × 520px

次ページで使う場合は、ページ固有フォルダへコピーして、バナー文言と背景画像名を差し替えます。

## extract_pickup_products_sample.py

CSVから商品コード周辺の楽天商品URL・画像URLを探すためのサンプルです。

次ページで使う場合は、`CODES` に対象商品コードを入れて実行します。
