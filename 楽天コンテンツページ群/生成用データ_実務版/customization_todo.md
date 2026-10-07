# 他社展開時の差し替えメモ

このファイルは、現在の制作ルールを変えずに、将来ほかの店舗・会社へ流用するときに差し替えるべき箇所を記録するためのメモです。

実務中に店舗固有、商材固有、読者固有、環境固有のルールを見つけたら、ここへ追記します。ここに書いた内容は現在の生成ルールへ自動反映しません。実制作への影響を避けるため、あくまで将来の汎用化、質問プロンプト作成、設定ファイル化の材料として扱います。

## 運用ルール

- 現在の制作ルールを直接変更しない。
- 差し替え候補を見つけたら、該当箇所、現在値、将来の差し替え方を残す。
- 他社展開時は、このメモをもとに質問プロンプトや `custom/{brand}/` の初期設定を作る。
- すぐ共通化しない。実務で問題が出た箇所から順次、設定化する。

## 差し替え候補一覧

### 1. 店舗ID・楽天画像URL

現在:

- `https://image.rakuten.co.jp/u-b-yumehan/cabinet/contents/`
- 店舗ID相当: `u-b-yumehan`

将来:

- 店舗ごとの楽天画像URLベースへ差し替える。
- RMS内の画像格納先、cabinetパス、ファイル命名ルールを確認する。

主な該当箇所:

- `production_workflow.md`
- `scripts/export_paste_tsv.py`
- `scripts/build_*`
- `page_paste_blocks.tsv` の画像URL

メモ:

- 共通ルールへ直書きせず、将来的には `brand_config` のような設定値にする候補。

### 2. 店舗名・ブランド名

現在:

- ゆめはん
- `custom/yumehan/`
- `ゆめはんオリジナル商品マークB.png`

将来:

- 店舗名、ブランド名、ロゴ、独自表現に差し替える。
- `custom/{brand}/` にブランド別の画像テイスト、禁止事項、任意素材を置く。

主な該当箇所:

- `custom/yumehan/`
- `README_ルール運用.md`
- `production_workflow.md`
- `scripts/add_logo_outro.py`
- 動画アウトロ関連スクリプト

### 3. 対象読者

現在:

- 主な読者は40代から50代の女性。
- 女性向けインナーショップの読み物。
- 清潔感、品のよさ、服の見え方、年齢による体型や体調の変化への戸惑いを軸にする。

将来:

- 年齢層、性別、読者の生活背景、悩みの種類を店舗・商材ごとに差し替える。
- 男性向け、ユニセックス、キッズ、シニア、スポーツ、ギフトなどの場合は文体と画像表現も変える。

主な該当箇所:

- `production_workflow.md`
- `prompts/content_planning_prompt.md`
- `prompts/page_copy_prompt.md`
- `prompts/readable_column_style_rule.md`
- `custom/{brand}/reference/illustration_style/character/style_notes.md`

### 4. 文体・読み物トーン

現在:

- 婦人誌コラム風。
- 電車の吊り広告、雑誌CMのような動画導入。
- 売り込みすぎない読み物 + 商品紹介 + SEO。

将来:

- 店舗ジャンルに合わせて、専門誌風、カタログ風、アウトドア誌風、育児メディア風、ビジネス向け、ギフト向けなどへ変更する。
- `column_pattern` の種類や標準採用する文体を差し替える。

主な該当箇所:

- `prompts/content_planning_prompt.md`
- `prompts/page_copy_prompt.md`
- `prompts/readable_column_style_rule.md`
- `production_workflow.md`

### 5. 商材カテゴリ・季節展開

現在:

- 婦人インナー、水着、フェムケア、吸水ショーツ、補整、姿勢、ペチパンツなど。
- 季節案もインナー商材を前提にしている。

将来:

- 店舗の商品カテゴリごとに、季節切り口、悩み、NG表現、画像モチーフを差し替える。
- 食品、雑貨、家電、スポーツ用品、ペット用品などでは、本文の広げ方と画像ルールを作り替える。

主な該当箇所:

- `production_workflow.md`
- `prompts/content_planning_prompt.md`
- `prompts/image_banner_prompt.md`
- `prompts/music_prompt.md`

### 6. 禁止表現・法務/安全表現

現在:

- 下着姿、露出、性的印象、身体の悩みを直接見せる描写を避ける。
- 痩身効果、医療効果、効果保証に見える表現を避ける。
- 体型比較、ビフォーアフター表現を避ける。

将来:

- 商材ごとに薬機法、景表法、食品表示、医療/健康、金融、子ども向け表現などの禁止事項を追加する。
- 店舗独自のNGワード、言い換えルールを持たせる。

主な該当箇所:

- `production_workflow.md`
- `prompts/page_copy_prompt.md`
- `prompts/image_banner_prompt.md`
- `custom/{brand}/`

### 7. 画像・イラスト基準

現在:

- ゆめはん用の人物イラストは `custom/yumehan/reference/illustration_style/character/` を基準にする。
- 基準画像程度の年齢感・雰囲気で、10代や幼い印象に見えない大人女性。
- 実写風画像は標準で参照なし。イラスト主体のみ基準フォルダを参照。

将来:

- 他社のイラスト基準、写真テイスト、ブランドカラー、許可済み人物画像、背景素材に差し替える。
- 説明用イラスト、人物イラスト、実写風参考を別フォルダで管理する。

主な該当箇所:

- `custom/{brand}/reference/`
- `custom/{brand}/optional_assets/`
- `prompts/image_banner_prompt.md`
- `prompts/page_copy_prompt.md`
- `production_workflow.md`

### 7-1. 商品画像へ寄せる度合い

現在:

- 商品画像は必ず確認する。
- 通常は商品写真そのものを再現せず、シルエット、丈感、ボリューム感、露出の程度、素材感、色味、使用シーンのヒントまでを参照する。
- 商品シルエットが特殊で、実写風だと商品との齟齬が目立つ場合だけ `reference_mode=product_inspired_illustration` を使い、商品に寄せたイラストを作る。
- 商品写真の正確な柄、ロゴ、商品ページ内文字、価格、サイズ表記、モデルの顔や体型、写真の構図そのものは再現しない。

将来:

- 店舗や商材ごとに、画像を商品へどの程度寄せるかを設定する。
- 例:
  - `low`: 商品カテゴリや使用シーンだけを参照し、商品自体は描かない。
  - `medium`: シルエット、丈感、色味、素材感だけをゆるく反映する。現在の標準。
  - `high`: 特殊形状や柄の方向性まで寄せる。ただしロゴ、文字、価格、商品写真そのものは再現しない。
  - `exact`: 原則使用しない。商品写真そのものを納品画像へ貼り込まず、商品画像は生成AIの参照資料として扱う。
- アパレル、インナー、水着、家具、雑貨、食品などで許容度が変わるため、他社展開時に必ず確認する。

主な該当箇所:

- `production_workflow.md`
- `prompts/image_banner_prompt.md`
- `prompts/content_planning_prompt.md`
- 各ページの `notes.md`
- `data/product_reference/`

メモ:

- 商品に寄せるほど、実物との差異、色柄の誤認、権利表現、販売中商品との不一致が問題になりやすい。
- 商品から離すほど、読み物としては安全だが商品紹介との接続が弱くなる。
- 特殊形状商品で実物に近い見せ方が必要な場合も、まず商品画像を参照した生成AI画像で調整する。納品画像へ実商品画像を貼り込む運用は標準化しない。
- 他社用の質問プロンプトでは「商品画像をどこまで再現してよいか」「商品そのものを出したいか、使用シーンだけでよいか」を必ず聞く。

追加メモ:

- 商品寄せ度を高くする場合でも、商品カテゴリを誤認しないシルエット、丈感、露出の程度を優先し、柄や色はページ間で散らす余地を残す。
- アパレル、下着、水着、バッグ、雑貨など、柄や色が第一印象に出る商材では、他社用の初期質問に「柄・色を商品にどこまで寄せるか」「ページ間でどこまで色柄を変えてよいか」を追加する。
- 画像のみ再生成の運用では、本文や企画を作り直さない場合でも、ページ間の散らし表を作る。再生成時ほど、直前の修正指示に引っ張られて同じ見た目に収束しやすい。

### 8. ロゴ・動画アウトロ

現在:

- `ゆめはんオリジナル商品マークB.png`
- 動画最後に白フェード + 店舗ロゴ。

将来:

- 店舗ロゴ、アウトロ表現、ブランドカラー、フェード色、表示時間を差し替える。
- ロゴなし運用や、動画末尾の定型文が必要な店舗にも対応する。

主な該当箇所:

- `scripts/add_logo_outro.py`
- `scripts/render_vertical_videos.py`
- `scripts/render_story_video_017.py`
- 各 `build_*` / 動画生成スクリプト

### 9. BGM・音量基準

現在:

- 標準BGM目標: `Integrated loudness: -33 LUFS`
- 商品ジャンルごとに控えめなBGMを生成。

将来:

- 店舗トーン、商材ジャンル、使用媒体に合わせて音楽ジャンルを差し替える。
- 音量基準、BGM有無、効果音有無を設定化する。

主な該当箇所:

- `prompts/music_prompt.md`
- `references/audio/`
- 動画生成スクリプト

### 10. 楽天コンテンツページ仕様

現在:

- 楽天コンテンツページ向け。
- 画像URL、関連商品パーツ、TSV貼り付け順序、RMSアップロードを前提。
- 標準順序: タイトル画像、メインタイトル、動画、動画下本文、小タイトル、バナー、本文、関連商品。

将来:

- 楽天以外、Yahoo!、自社EC、Shopify、Amazon、LPなどへ流用する場合は、パーツ構成、画像URL、商品リンク、動画配置、TSV形式を差し替える。

主な該当箇所:

- `production_workflow.md`
- `scripts/export_paste_tsv.py`
- `templates/`

### 11. CSV仕様・商品データ

現在:

- 楽天CSVはヘッダー名ベースで読む。
- 商品ID、商品管理番号、SKU管理番号など提示されたIDをCSV内で検索する。
- Yahoo! CSVも過去に使用。

将来:

- 店舗のCSV形式、商品管理番号、SKU体系、価格/在庫/利益率データの場所を差し替える。
- 楽天以外のECではCSVカラム名と画像URL形式が変わる。

主な該当箇所:

- `production_workflow.md`
- `prompts/content_planning_prompt.md`
- `scripts/generate_content_proposals_v1.py`
- 各企画作成スクリプト

### 12. 画像サイズ・動画サイズ

現在:

- メインタイトル画像: `1600 x 900`
- 章バナー: `1600 x 520`
- アクセント画像: `1200 x 1200`
- 動画: `720 x 960`
- 動画背景生成: 正方形ベース

将来:

- 店舗、媒体、モール仕様に合わせて差し替える。
- 横動画、正方形動画、SNS用リサイズ、LP用画像などの追加も候補。

主な該当箇所:

- `production_workflow.md`
- `prompts/image_banner_prompt.md`
- `scripts/render_vertical_videos.py`
- 各 `build_*` スクリプト

### 13. ファイル構成・納品形式

現在:

- アップロード用画像: `images/delivery/`
- 再利用可能な元画像: `images/work/generated_originals/`
- 作業背景: `images/work/*_bg.png`
- 動画: `video/`
- TSV: `page_paste_blocks.tsv`

将来:

- 他社の納品方法に合わせてフォルダ名、アップロード対象、命名規則、納品チェックリストを差し替える。
- zip納品、クラウド納品、CMS直接登録なども考慮する。

主な該当箇所:

- `production_workflow.md`
- `prompts/image_banner_prompt.md`
- `templates/`

### 14. スクリプト内の直書き定数

現在:

- 店舗URL、ロゴパス、各ページ固有コピー、画像名、BGM設定が一部スクリプトに直書きされている。

将来:

- `brand_config`、`page_config`、`asset_config` のような設定ファイル化を検討する。
- 他社展開時に最初に洗い出す必要がある。

主な該当箇所:

- `scripts/add_logo_outro.py`
- `scripts/render_vertical_videos.py`
- `scripts/export_paste_tsv.py`
- `scripts/build_*`

## 今後追加するたびに見る観点

新しいルールを追加した時、以下に該当する場合はこのメモへ追記する。

- 店舗名、ブランド名、URL、ロゴに関係する。
- 読者の年齢、性別、生活背景に関係する。
- 商材カテゴリ、季節、悩み、禁止表現に関係する。
- 画像テイスト、イラストテイスト、人物像に関係する。
- BGM、動画アウトロ、字幕、フォントに関係する。
- CSVの列名、商品ID体系、画像URLに関係する。
- 楽天以外では変わりそうなパーツ構成に関係する。
