from __future__ import annotations

import csv
import math
import shutil
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "production"
REFS = ROOT / "references" / "generated_024_031"


PAGES = {
    "024": {
        "slug": "cover_swimwear_preparation",
        "title": "水着になる前に悩みすぎる私へ｜体型カバー水着という準備",
        "short_title": ["体型カバー水着という", "小さな準備"],
        "product_ids": ["h-mzg20", "c-mizugi_nbf", "usbswc", "usbswb", "b-mizugi-3"],
        "pattern": "magazine_column",
        "style": "common-prep",
        "palette": ((230, 241, 244), (78, 139, 157), (246, 235, 222), (80, 83, 91)),
        "lead": [
            "水着を着る予定が入ると、楽しみより先に少し身構えてしまうことがあります。",
            "お腹、二の腕、背中、太もも。気になる場所は人それぞれですが、悩みが増えるほど水辺へ行く前の支度は重くなります。体型カバー水着は、体を別人に変えるものではありません。けれど、今の自分で水辺に出るための準備にはなります。",
            "このコラムでは、上下セットで完結する体型カバー水着を、気持ちを軽くする道具として考えます。",
        ],
        "sections": [
            ("悩む時間が長くなる", "水着の予定は、服を選ぶ時より少しだけ緊張します。普段なら気にしない部分まで急に気になり、鏡の前で考える時間が長くなります。\n\nでも、その時間が長すぎると、水辺そのものを楽しむ前に疲れてしまいます。大切なのは、悩みをゼロにすることではなく、悩みすぎなくていい準備をしておくことです。"),
            ("上下セットは迷いを減らす", "トップスとボトムを別々に考えると、組み合わせだけで迷いが増えます。色は合うか、丈は足りるか、泳いだ時にずれないか。小さな確認が積み重なります。\n\n上下セットの水着は、最初から水辺用としてまとまっている安心感があります。支度の段階で迷いを減らせることは、意外と大きなメリットです。"),
            ("隠す場所は人それぞれ", "すっきり見せたい人もいれば、ふんわり覆いたい人もいます。どちらが正解というより、落ち着ける見え方が違うだけです。\n\n体型カバー水着を選ぶ時は、誰かの理想よりも、自分が水辺で何を気にせず過ごしたいかを基準にすると選びやすくなります。"),
            ("水辺で動けることも大切", "体型カバーを考えると、つい見た目ばかりに意識が向きます。けれど水着は、座る、歩く、しゃがむ、荷物を持つといった動きの中で使うものです。\n\n気になる部分を覆いながら、動きにくくないこと。水辺で過ごす時間を考えると、この現実的な安心感も欠かせません。"),
            ("準備ができると出かけやすい", "水着を選ぶことは、完璧になるための儀式ではありません。水辺に行く自分を少し助ける準備です。\n\n上下セットでまとまり、気になる部分に配慮があり、着る前の迷いが少ない。そんな水着があると、予定の日の気持ちは少し軽くなります。"),
        ],
        "points": ["このコラムのポイント", "› 悩みをゼロにしなくていい", "› 上下セットは迷いを減らす", "› 落ち着ける見え方で選ぶ"],
    },
    "025": {
        "slug": "slim_look_cover_swimwear",
        "title": "ほっそり見せたい水辺の日｜着やせタイプの体型カバー水着の話",
        "short_title": ["ほっそり見せたい", "水辺の日"],
        "product_ids": ["h-mzg20", "c-mizugi_nbf"],
        "pattern": "soft_textbook",
        "style": "slim",
        "palette": ((226, 237, 242), (43, 92, 124), (235, 238, 232), (62, 67, 76)),
        "lead": [
            "体型カバー水着の中でも、着やせタイプは「隠す」より「すっきり見せる」ことに重心があります。",
            "もちろん、水着を着ただけで体が細くなるわけではありません。けれど、色、切り替え、視線の流れ、丈のバランスによって、印象が整って見えることはあります。",
            "このコラムでは、ほっそり見せたい日に考えたい体型カバー水着の選び方を整理します。",
        ],
        "sections": [
            ("細さではなく印象の話", "着やせは、体そのものを変える言葉ではありません。鏡や写真で見た時に、どこへ視線が流れるかという印象の話です。\n\n水着では面積が限られるため、色の切り替えや柄の入り方がいつも以上に目に入りやすくなります。だから、すっきり見せたい日は、まず全体のまとまりを見ることが大切です。"),
            ("濃色は輪郭を落ち着かせる", "濃い色は、輪郭を引き締めて見せたい時に使いやすい選択です。特にサイドや中心に濃色が入ると、視線が散らばりにくくなります。\n\nただし、黒一色なら必ず細く見えるという単純な話ではありません。自分の肌や水辺の雰囲気に合うか、重く見えすぎないかも合わせて見たいところです。"),
            ("縦の流れを味方にする", "縦に流れる柄や切り替えは、視線を上下へ動かします。横へ広がる印象を抑えたい時は、この縦の流れが助けになります。\n\n水着選びでは、細部よりも遠目の印象を確認するとわかりやすくなります。近くで柄を見るより、少し離れて全体のラインを見る方が実際の見え方に近いからです。"),
            ("動いた時の安心も確認する", "すっきり見えを優先しすぎて、動くたびに気になる水着では落ち着きません。座る、歩く、腕を上げる。水辺の動作は意外と多いものです。\n\n着やせタイプでも、めくれにくさや丈感、肩まわりの動きやすさを確認しておくと安心です。見た目と動きやすさの両方がそろうと、水辺での気持ちが軽くなります。"),
            ("すっきりは自信の入口", "ほっそり見えるかどうかだけに縛られると、水着選びは苦しくなります。けれど、すっきりした印象に整えることで外へ出やすくなるなら、それは十分に意味があります。\n\n着やせタイプの体型カバー水着は、自分を責めるためではなく、水辺で少し背筋を伸ばすための選択肢です。"),
        ],
        "points": ["このコラムのポイント", "› 着やせは印象の整え方", "› 色と縦ラインを味方にする", "› 動きやすさも忘れない"],
    },
    "026": {
        "slug": "soft_hide_cover_swimwear",
        "title": "ふわっと隠す水着選び｜がんばって見せない体型カバーの考え方",
        "short_title": ["ふわっと隠す", "水着選び"],
        "product_ids": ["usbswc", "usbswb", "b-mizugi-3"],
        "pattern": "magazine_column",
        "style": "soft",
        "palette": ((241, 235, 226), (142, 111, 92), (222, 236, 232), (76, 70, 67)),
        "lead": [
            "体型カバーというと、細く見せることばかりに意識が向きがちです。",
            "でも、もう少し力を抜いた選び方もあります。ふんわりしたシルエットや重ね着風のデザインで、気になる部分をやさしく覆う。がんばって見せるより、落ち着いて過ごせることを優先する考え方です。",
            "このコラムでは、ふわっと隠すタイプの水着が向いている場面を考えます。",
        ],
        "sections": [
            ("隠したい日はある", "誰にでも、今日はあまり体のラインを出したくないという日があります。水辺の予定が楽しみでも、その気持ちがなくなるわけではありません。\n\nそんな時に、隠したい気持ちを無理に否定しなくてもいいと思います。気になる部分をやわらかく覆う水着は、水辺へ行くための現実的な味方になります。"),
            ("ふんわり感は余白になる", "体にぴったり沿う水着は動きやすい一方で、ラインが気になることもあります。ふんわりしたデザインは、体と服の間に少し余白を作ります。\n\nその余白があるだけで、座った時や歩いた時の気持ちは変わります。見た目のためだけではなく、過ごしやすさのためのふんわり感です。"),
            ("服っぽさが安心になる", "重ね着風やブラウジングタイプは、水着でありながら服に近い印象があります。プールサイドや休憩中に、急に水着姿だけになったような心細さが少なくなります。\n\n水辺では泳ぐ時間だけでなく、移動や待ち時間もあります。服っぽい安心感は、その間の居心地を支えてくれます。"),
            ("大きく見せない工夫も必要", "ふんわり隠す水着は、ただ大きければよいわけではありません。布が余りすぎると、かえって重く見えることがあります。\n\n丈、裾の広がり、色柄のバランスを見ながら、覆うところとすっきり見せるところの差を作る。ふんわりタイプほど、その加減が大切です。"),
            ("落ち着ける水着を選ぶ", "水着選びは、強く見せるためだけのものではありません。落ち着いて過ごすために選んでもいいのです。\n\nふんわり体型隠しタイプは、気になる部分をやさしく覆いながら、水辺の時間へ気持ちを向けるための選択肢です。"),
        ],
        "points": ["このコラムのポイント", "› 隠したい日があっていい", "› ふんわり感は余白になる", "› 服っぽさが安心を作る"],
    },
    "027": {
        "slug": "before_weight_loss_swimwear",
        "title": "「痩せてから水着」はいつ終わる？｜今の体で水辺に行くための話",
        "short_title": ["痩せてから水着は", "いつ終わる？"],
        "product_ids": ["h-mzg20", "c-mizugi_nbf", "usbswc", "usbswb", "b-mizugi-3"],
        "pattern": "editor_honest_voice",
        "style": "honest",
        "palette": ((238, 229, 224), (165, 91, 89), (224, 239, 242), (64, 58, 59)),
        "lead": [
            "水着の予定を前にすると、つい「もう少し痩せてから」と思うことがあります。",
            "けれど、その日は意外と来ません。体重や体型を整える努力は悪いことではありませんが、水辺の予定がすべてその後回しになると、楽しい時間まで遠ざかってしまいます。",
            "このコラムでは、今の体で水辺に行くための水着選びを、少し正直に考えます。",
        ],
        "sections": [
            ("予定は体重を待たない", "旅行、プール、子どもの水遊び。水辺の予定は、こちらの体重計の都合まで待ってくれません。\n\nだから、完璧に整ってから行くという考え方だけでは、予定そのものを楽しみにくくなります。今の自分でどう準備するかを考える方が、現実には役に立ちます。"),
            ("水着で体は消えない", "着るだけで体型が別物になる水着はありません。お肉がどこかへ消えるわけでもありません。\n\nでも、気になる部分を覆ったり、視線の流れを整えたり、動きやすさを確保したりすることはできます。体を変えるのではなく、過ごしやすくするための水着選びです。"),
            ("隠すことは逃げではない", "体型カバーを選ぶことを、負けのように感じる必要はありません。暑さ対策に帽子をかぶるように、水辺で落ち着くために水着を選ぶだけです。\n\n隠したいところを隠し、動きたい時に動ける。そう考えると、体型カバーは前向きな準備になります。"),
            ("比べる相手を減らす", "水辺では、つい周りの人と自分を比べてしまいます。けれど、実際には多くの人が自分の荷物、子ども、日差し、スマホ、次の予定で忙しいものです。\n\n比べる視線を少し減らすためにも、自分が落ち着ける水着を選ぶことは大切です。"),
            ("今の体で楽しむ準備", "水着を選ぶことは、今の体をあきらめることではありません。今の体で予定を楽しむための準備です。\n\n痩せてからではなく、行く日に困らないように。体型カバー水着は、その現実的な一歩を助けてくれます。"),
        ],
        "points": ["このコラムのポイント", "› 予定は体重を待たない", "› 体を消すより過ごしやすく", "› 今の体で楽しむ準備"],
    },
    "028": {
        "slug": "belly_self_conscious_swimwear",
        "title": "お腹だけを見ているのは自分だけかも｜水辺の自意識をゆるめるコラム",
        "short_title": ["お腹だけ見てるのは", "自分だけかも"],
        "product_ids": ["usbswc", "usbswb", "b-mizugi-3"],
        "pattern": "comic_first_person",
        "style": "comic-soft",
        "palette": ((244, 236, 222), (194, 137, 85), (224, 238, 240), (73, 67, 62)),
        "lead": [
            "水辺に行く前、鏡の前でなぜかお腹だけを見てしまうことがあります。",
            "顔でも髪でもなく、お腹。しかもかなり厳しい目で見ています。けれど実際の水辺で、他人のお腹をそこまで観察している人はどれくらいいるのでしょう。",
            "このコラムでは、少し笑いながら水辺の自意識をゆるめ、ふんわり隠せる水着の安心感を考えます。",
        ],
        "sections": [
            ("鏡の前だけ審査員", "家の鏡の前では、なぜか自分だけ審査員になります。角度を変え、息を吸い、もう一度見る。判定はだいたい厳しめです。\n\nでも、その審査は水辺に持ち込まなくてもいいのかもしれません。水辺には、水しぶき、荷物、日差し、子どもの声、休憩場所探し。見るものが多すぎます。"),
            ("みんな意外と忙しい", "プールや海で、他人は思ったほどこちらを見ていません。タオルはどこか、飲み物は冷えているか、子どもはどこか、自分の日焼けは大丈夫か。\n\nそれぞれが自分のことで忙しい場所では、自分が思うほど目立たないことも多いものです。"),
            ("ふんわり隠すと気が散らない", "それでも気になるものは気になります。だからこそ、精神論だけで片づけず、水着で先に安心を作っておくのは現実的です。\n\nふんわりしたトップスや重ね着風のデザインは、気になる部分へ意識が向き続けるのをやわらげてくれます。"),
            ("動ける安心も欲しい", "お腹を隠せても、座るたびに裾を直すようでは落ち着きません。水辺ではしゃがむ、歩く、荷物を持つ、子どもを追うなど動作が多いものです。\n\n体型カバーは、見た目だけでなく動きやすさも合わせて考えると失敗しにくくなります。"),
            ("笑って出かけるくらいでいい", "水着の日に少し緊張するのは自然です。でも、その緊張を笑いに変えられるくらいの余白があると、出かけやすくなります。\n\nお腹だけを見ていた自分に少しツッコミを入れて、ふんわり水着を味方にする。水辺の一日は、そのくらい軽く始めてもいいはずです。"),
        ],
        "points": ["このコラムのポイント", "› 鏡の前だけ審査員になる", "› みんな自分のことで忙しい", "› ふんわり隠して気を散らさない"],
    },
    "029": {
        "slug": "poolside_set_preparation",
        "title": "プールサイドで慌てないために｜上下セット水着が楽な理由",
        "short_title": ["上下セット水着が", "楽な理由"],
        "product_ids": ["h-mzg20", "c-mizugi_nbf", "usbswc", "usbswb", "b-mizugi-3"],
        "pattern": "magazine_column",
        "style": "practical",
        "palette": ((226, 240, 242), (55, 132, 150), (242, 234, 218), (64, 72, 77)),
        "lead": [
            "水辺の支度は、思っているより小さな確認が多いものです。",
            "水着、羽織り、ボトム、タオル、帽子、日焼け対策。ひとつ忘れるだけで、プールサイドで急に落ち着かなくなります。上下セットで完結する水着は、その迷いを減らしてくれる道具です。",
            "このコラムでは、プールサイドで慌てないための水着準備を考えます。",
        ],
        "sections": [
            ("支度の小物は多い", "水辺に行く日は、いつもの外出より荷物が増えます。タオル、着替え、飲み物、日焼け止め。さらに水着の組み合わせまで考えると、出発前から疲れてしまいます。\n\nだからこそ、メインの水着が上下セットでまとまっていることは、支度の負担を減らしてくれます。"),
            ("組み合わせ迷子を防ぐ", "トップスとボトムを別々に選ぶと、色や丈、露出感のバランスで迷うことがあります。家ではよく見えても、水辺で急に不安になることもあります。\n\nセット水着なら、最初から一体感を前提に作られているため、組み合わせ迷子になりにくいのが魅力です。"),
            ("更衣室でも慌てにくい", "プールサイドの前には更衣室があります。限られたスペースで着替え、荷物をまとめ、人の流れにも気を配る。ここで手間取ると、気持ちまで焦ります。\n\n着る順番がわかりやすく、上下の組み合わせに迷わない水着は、更衣室での小さな慌ただしさを減らします。"),
            ("休憩中の見え方も大切", "水辺では、泳ぐ時間より休憩や移動の時間の方が気になることもあります。座る、歩く、タオルを取る。水から上がった時の見え方も大切です。\n\n体型カバー水着は、水の中だけでなくプールサイドで落ち着けるかどうかも選ぶポイントになります。"),
            ("準備が整うと楽しめる", "支度で慌てないと、気持ちは水辺そのものへ向かいやすくなります。何を着るかで疲れすぎないことは、楽しむための土台です。\n\n上下セットで完結する体型カバー水着は、出発前からプールサイドまでの不安を少しずつ減らしてくれます。"),
        ],
        "points": ["このコラムのポイント", "› 支度の迷いを減らす", "› 更衣室で慌てにくい", "› 休憩中の見え方も大切"],
    },
    "030": {
        "slug": "family_waterplay_cover_swimwear",
        "title": "子どもの水遊びに付き合う日の水着｜動きやすく隠せる安心感",
        "short_title": ["子どもの水遊びに", "付き合う日の水着"],
        "product_ids": ["usbswc", "usbswb", "b-mizugi-3"],
        "pattern": "magazine_column",
        "style": "family",
        "palette": ((237, 242, 224), (91, 142, 115), (241, 226, 205), (68, 76, 67)),
        "lead": [
            "子どもの水遊びに付き合う日は、自分が主役ではないようで、実はかなり動きます。",
            "しゃがむ、立つ、荷物を持つ、写真を撮る、日陰を探す。水に入る時間より、周りで動く時間の方が長いこともあります。そんな日には、体型をふんわり隠しながら動きやすい水着が助けになります。",
            "このコラムでは、家族の水辺で落ち着いて過ごすための水着選びを考えます。",
        ],
        "sections": [
            ("水辺の付き添いは忙しい", "子どもの水遊びは、見守っているだけのようで意外と忙しいものです。タオルを渡し、飲み物を出し、写真を撮り、荷物を守る。気づけば何度も立ったり座ったりしています。\n\nだから、動くたびに気になる水着では疲れてしまいます。付き添いの日こそ、安心して動けることが大切です。"),
            ("しゃがむ動作に備える", "小さな子どもと一緒だと、しゃがむ場面が増えます。サンダルを直す、浮き輪を持つ、濡れた荷物を拾う。水辺のしゃがむ動作は思った以上に多いものです。\n\n丈感や裾の落ち着きがある水着なら、動くたびに直す手間を減らせます。"),
            ("ふんわり隠せる安心", "家族の水遊びでは、泳ぐというより水辺で過ごす時間が中心になることがあります。だからこそ、服に近い安心感やふんわりしたカバー感があると落ち着きます。\n\n体にぴったりしすぎないデザインは、休憩中や移動中の見え方にも安心感を作ります。"),
            ("写真に残る日でもある", "家族の水辺は、写真に残りやすい日でもあります。あとで見返した時に、表情より体型ばかり気になるのは少しもったいないものです。\n\n自分が落ち着ける水着を選んでおくと、写真を撮る側でも写る側でも気持ちが楽になります。"),
            ("楽しむ余裕を残す", "子どもに付き合う水辺の日は、自分のことを後回しにしがちです。けれど、着るものの不安が少ないだけで、見守る気持ちにも余裕が生まれます。\n\n動きやすく、ふんわり隠せる体型カバー水着は、家族の水遊びを支える実用的な準備です。"),
        ],
        "points": ["このコラムのポイント", "› 付き添いの日ほど動く", "› しゃがむ動作に備える", "› 写真の日にも安心を"],
    },
    "031": {
        "slug": "slim_or_soft_cover_swimwear",
        "title": "着やせ派？ふんわり派？｜体型カバー水着の選び分け",
        "short_title": ["着やせ派？", "ふんわり派？"],
        "product_ids": ["h-mzg20", "c-mizugi_nbf", "usbswc", "usbswb", "b-mizugi-3"],
        "pattern": "soft_textbook",
        "style": "compare",
        "video_scene_fit": "contain_on_blur",
        "palette": ((230, 238, 244), (68, 102, 137), (242, 230, 219), (79, 72, 69)),
        "lead": [
            "体型カバー水着には、大きく分けると二つの考え方があります。",
            "ひとつは、色やラインですっきり見せる着やせタイプ。もうひとつは、ふんわりしたデザインで気になる部分をやさしく覆うタイプです。どちらが上という話ではなく、向いている不安が違います。",
            "このコラムでは、着やせ派とふんわり派の選び分けを整理します。",
        ],
        "sections": [
            ("見せ方の目的が違う", "着やせタイプは、全体の印象をすっきり整えることが目的です。色の配置や縦の流れで、視線をコントロールします。\n\nふんわりタイプは、体のラインを出しすぎないことが目的です。服に近い安心感や、余白のあるシルエットで落ち着きを作ります。"),
            ("着やせ派に向く日", "写真に残る予定や、少しきちんと見せたい水辺の日には、着やせタイプが選びやすくなります。遠目の印象を整えたい時にも向いています。\n\nただし、すっきり見えだけを優先せず、動いた時に不安がないかも確認しておきたいところです。"),
            ("ふんわり派に向く日", "家族の水遊びやリゾート、休憩時間が長い日は、ふんわりタイプが安心です。水着姿で過ごす時間に、服っぽさがあると落ち着きます。\n\n体のラインを気にしすぎず、水辺の時間に集中したい人にも向いています。"),
            ("迷ったら不安で選ぶ", "どちらにするか迷ったら、自分が一番気になる場面を思い浮かべます。写真なのか、座った時なのか、歩く時なのか、休憩中なのか。\n\nその不安を減らせる方を選ぶと、見た目の好みだけで選ぶより失敗しにくくなります。"),
            ("水辺で落ち着ける方へ", "体型カバー水着の役割は、完璧に見せることではありません。水辺で落ち着いて過ごすための準備です。\n\n着やせ派でも、ふんわり派でも、自分が水辺で何を忘れて過ごしたいかを基準にすると選びやすくなります。"),
        ],
        "points": ["このコラムのポイント", "› 着やせとふんわりは目的が違う", "› 不安な場面で選ぶ", "› 落ち着ける方が正解"],
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


def contain_on_blur(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    bg = cover_crop(img, size).filter(ImageFilter.GaussianBlur(18))
    veil = Image.new("RGB", size, (246, 246, 242))
    bg = Image.blend(bg, veil, 0.18)
    scale = min(target_w / img.width, target_h / img.height)
    fitted = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    x = (target_w - fitted.width) // 2
    y = (target_h - fitted.height) // 2
    bg.paste(fitted, (x, y))
    return bg


def glow_box(size: tuple[int, int], alpha: int = 76) -> Image.Image:
    w, h = size
    pad = 74
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=28, fill=(255, 255, 255, alpha))
    return layer.filter(ImageFilter.GaussianBlur(34))


def draw_lines(img: Image.Image, lines: list[str], x: int, y: int, sizes: list[int], gaps: list[int], fill=(44, 40, 37)) -> None:
    frame = img.convert("RGBA")
    draw = ImageDraw.Draw(frame)
    current_y = y
    for idx, line in enumerate(lines):
        font = mincho(sizes[min(idx, len(sizes) - 1)], idx == 0)
        w, h = text_size(line, font)
        frame.alpha_composite(glow_box((w + 100, h + 48)), (x - 120, current_y - 82))
        draw.text((x, current_y), font=font, text=line, fill=(*fill, 255))
        current_y += gaps[min(idx, len(gaps) - 1)]
    img.paste(frame.convert("RGB"))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


def draw_soft_background(draw: ImageDraw.ImageDraw, w: int, h: int, palette) -> None:
    base, accent, warm, ink = palette
    for y in range(h):
        color = blend(base, warm, y / h * 0.38)
        draw.line((0, y, w, y), fill=color)
    for i in range(10):
        x = (i * 193) % w
        y = 70 + (i * 121) % (h - 180)
        r = 120 + (i % 4) * 46
        c = blend(base, accent, 0.13 + (i % 3) * 0.05)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(*c,))


def draw_pool(draw: ImageDraw.ImageDraw, w: int, h: int, palette, y0: int, perspective: bool = False) -> None:
    base, accent, warm, ink = palette
    water = blend(base, accent, 0.58)
    if perspective:
        draw.polygon([(w * 0.30, y0), (w, y0 + 30), (w, h), (0, h)], fill=water)
        for i in range(6):
            yy = y0 + 60 + i * 105
            draw.line((0, yy, w, yy + 38), fill=blend(water, (255, 255, 255), 0.38), width=4)
    else:
        draw.rounded_rectangle((90, y0, w - 90, h - 80), radius=34, fill=water)
        for i in range(8):
            yy = y0 + 42 + i * 80
            draw.arc((120, yy, w - 120, yy + 66), 180, 350, fill=blend(water, (255, 255, 255), 0.48), width=5)


def draw_person(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float, palette, pose: str = "stand") -> None:
    _base, accent, warm, ink = palette
    skin = (225, 180, 153)
    hair = (92, 67, 53)
    cloth = blend(accent, ink, 0.20)
    r = int(28 * scale)
    draw.ellipse((x - r, y - 82 * scale - r, x + r, y - 82 * scale + r), fill=skin, outline=hair, width=max(1, int(2 * scale)))
    draw.arc((x - r - 6, y - 82 * scale - r - 10, x + r + 8, y - 82 * scale + r + 8), 180, 345, fill=hair, width=max(3, int(6 * scale)))
    if pose == "sit":
        draw.rounded_rectangle((x - 34 * scale, y - 56 * scale, x + 42 * scale, y + 30 * scale), radius=int(18 * scale), fill=cloth)
        draw.line((x - 28 * scale, y + 25 * scale, x - 85 * scale, y + 62 * scale), fill=ink, width=max(3, int(5 * scale)))
        draw.line((x + 25 * scale, y + 25 * scale, x + 83 * scale, y + 56 * scale), fill=ink, width=max(3, int(5 * scale)))
    else:
        draw.rounded_rectangle((x - 32 * scale, y - 54 * scale, x + 34 * scale, y + 70 * scale), radius=int(18 * scale), fill=cloth)
        draw.line((x - 22 * scale, y + 68 * scale, x - 42 * scale, y + 142 * scale), fill=ink, width=max(3, int(5 * scale)))
        draw.line((x + 18 * scale, y + 68 * scale, x + 37 * scale, y + 142 * scale), fill=ink, width=max(3, int(5 * scale)))
    draw.line((x - 28 * scale, y - 22 * scale, x - 76 * scale, y + 16 * scale), fill=skin, width=max(3, int(6 * scale)))
    draw.line((x + 28 * scale, y - 22 * scale, x + 74 * scale, y + 10 * scale), fill=skin, width=max(3, int(6 * scale)))


def draw_bag(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float, palette) -> None:
    _base, accent, warm, ink = palette
    draw.rounded_rectangle((x, y, x + 150 * scale, y + 92 * scale), radius=int(18 * scale), fill=blend(warm, (255, 255, 255), 0.28), outline=ink, width=max(2, int(3 * scale)))
    draw.arc((x + 34 * scale, y - 42 * scale, x + 116 * scale, y + 44 * scale), 190, 350, fill=accent, width=max(3, int(6 * scale)))
    draw.rectangle((x + 18 * scale, y + 18 * scale, x + 132 * scale, y + 34 * scale), fill=blend(accent, (255, 255, 255), 0.40))


def draw_style_motif(draw: ImageDraw.ImageDraw, w: int, h: int, palette, style: str, role: str, seed: int) -> None:
    base, accent, warm, ink = palette
    if style == "common-prep":
        # Closet and hanger mood.
        draw.rounded_rectangle((1030, 220, 1690, 1050), radius=32, fill=(*blend(warm, (255, 255, 255), 0.22), 175), outline=(*ink, 65), width=5)
        for x in [1160, 1340, 1520]:
            draw.line((x, 260, x, 940), fill=(*ink, 45), width=4)
        draw.arc((1220, 340, 1380, 510), 200, 340, fill=(*accent, 105), width=8)
        draw.line((1300, 505, 1208, 650), fill=(*accent, 105), width=8)
        draw.line((1300, 505, 1392, 650), fill=(*accent, 105), width=8)
    elif style == "slim":
        # Vertical panels and mirror lines.
        for x in [980, 1130, 1320, 1510]:
            draw.rounded_rectangle((x, 120, x + 80, 1240), radius=42, fill=(*blend(accent, ink, 0.22), 92))
        draw.rounded_rectangle((1180, 250, 1640, 1080), radius=52, outline=(*ink, 95), width=7)
        draw.line((1230, 330, 1590, 330), fill=(*blend(base, (255, 255, 255), 0.55), 90), width=5)
    elif style == "soft":
        # Flowing fabric and resort rest.
        for i in range(4):
            y = 340 + i * 155
            draw.arc((850, y, 1790, y + 360), 180, 355, fill=(*blend(warm, accent, 0.16), 110), width=34)
        draw.rounded_rectangle((1180, 870, 1720, 1030), radius=60, fill=(*blend(warm, (255, 255, 255), 0.18), 170))
    elif style == "honest":
        # Mirror, calendar, and quiet room.
        draw.rounded_rectangle((1040, 210, 1530, 1020), radius=44, fill=(*blend(base, (255, 255, 255), 0.68), 165), outline=(*ink, 90), width=7)
        draw.rounded_rectangle((1570, 260, 1740, 570), radius=22, fill=(*blend(warm, (255, 255, 255), 0.35), 160), outline=(*ink, 70), width=4)
        for yy in range(340, 540, 48):
            draw.line((1595, yy, 1715, yy), fill=(*ink, 45), width=3)
    elif style == "comic-soft":
        # Thought bubbles and small comic marks.
        for i, r in enumerate([150, 110, 75]):
            x = 1110 + i * 170
            y = 240 + i * 80
            draw.ellipse((x, y, x + r * 2, y + r * 2), fill=(*blend(warm, (255, 255, 255), 0.28), 170), outline=(*accent, 72), width=5)
        for x, y in [(1440, 680), (1510, 610), (1560, 735)]:
            draw.line((x, y, x + 44, y - 82), fill=(*accent, 145), width=9)
    elif style == "practical":
        # Packing/checklist mood without readable text.
        draw_bag(draw, 1130, 650, 2.2, palette)
        draw.rounded_rectangle((980, 250, 1310, 600), radius=28, fill=(*blend(base, (255, 255, 255), 0.72), 185), outline=(*ink, 80), width=5)
        for yy in [330, 410, 490]:
            draw.ellipse((1025, yy - 13, 1051, yy + 13), outline=(*accent, 140), width=5)
            draw.line((1080, yy, 1250, yy), fill=(*ink, 56), width=4)
    elif style == "family":
        # Water toys and family leisure cues.
        draw_pool(draw, w, h, palette, 720, False)
        for x, y, s in [(1220, 500, 0.85), (1390, 540, 0.72)]:
            draw.ellipse((x - 30, y - 76, x + 30, y - 16), fill=(*blend(warm, accent, 0.22), 160), outline=(*ink, 70), width=3)
            draw.rounded_rectangle((x - 36, y - 14, x + 36, y + 92), radius=22, fill=(*accent, 128))
        draw.ellipse((1500, 790, 1620, 910), outline=(*warm, 180), width=18)
    elif style == "compare":
        # Split comparison panels.
        draw.rounded_rectangle((945, 210, 1325, 1100), radius=44, fill=(*blend(accent, (255, 255, 255), 0.36), 130), outline=(*ink, 70), width=5)
        draw.rounded_rectangle((1375, 210, 1755, 1100), radius=44, fill=(*blend(warm, (255, 255, 255), 0.28), 150), outline=(*ink, 70), width=5)
        draw.line((1350, 245, 1350, 1070), fill=(*ink, 80), width=5)


def draw_scene(path: Path, page_no: str, role: str, style: str, palette, index: int) -> None:
    w, h = 1800, 1400
    seed = int(page_no) * 37 + index * 19 + sum(ord(ch) for ch in role) + sum(ord(ch) for ch in style)
    img = Image.new("RGB", (w, h), palette[0])
    draw = ImageDraw.Draw(img, "RGBA")
    draw_soft_background(draw, w, h, palette)
    base, accent, warm, ink = palette

    if style in {"slim", "compare"}:
        draw.rectangle((0, 0, 360, h), fill=(*blend(accent, ink, 0.08), 120))
        draw.rectangle((1420, 0, w, h), fill=(*blend(warm, (255, 255, 255), 0.15), 130))
    if style in {"soft", "family", "comic-soft"}:
        draw.ellipse((1020, 120, 1850, 980), fill=(*blend(warm, (255, 255, 255), 0.18), 180))
        draw.ellipse((80, 760, 720, 1370), fill=(*blend(base, accent, 0.18), 170))

    scene_mod = seed % 6
    if role == "title":
        title_base = {"common-prep": 0, "slim": 1, "soft": 2, "honest": 3, "comic-soft": 4, "practical": 5, "family": 2, "compare": 1}.get(style, 0)
        scene_mod = (title_base + int(page_no)) % 6

    # Role/page-specific editorial panels. These are intentionally visible enough
    # to prevent near-duplicate backgrounds across pages while keeping the mood soft.
    marker_color = blend(accent, warm, ((seed % 7) + 1) / 10)
    if seed % 4 == 0:
        draw.rounded_rectangle((80, 110, 620, 530), radius=54, fill=(*marker_color, 66))
    elif seed % 4 == 1:
        draw.ellipse((1160, 120, 1840, 760), fill=(*marker_color, 64))
    elif seed % 4 == 2:
        draw.polygon([(0, 1120), (520, 820), (760, 1400), (0, 1400)], fill=(*marker_color, 62))
    else:
        draw.rounded_rectangle((980, 930, 1760, 1340), radius=70, fill=(*marker_color, 62))

    stripe_color = blend(base, ink, 0.18)
    if seed % 3 == 0:
        for n in range(5):
            x = 1040 + n * 92
            draw.line((x, 0, x - 420, h), fill=(*stripe_color, 38), width=10)
    elif seed % 3 == 1:
        for n in range(4):
            y = 180 + n * 210
            draw.arc((980, y, 1740, y + 280), 190, 340, fill=(*stripe_color, 44), width=9)
    else:
        for n in range(6):
            draw.ellipse((1060 + n * 82, 150 + (n % 3) * 110, 1105 + n * 82, 195 + (n % 3) * 110), fill=(*stripe_color, 52))

    draw_style_motif(draw, w, h, palette, style, role, seed)

    if scene_mod == 0:
        draw.rounded_rectangle((980, 520, 1640, 980), radius=30, fill=(*blend(warm, (255, 255, 255), 0.28), 230))
        draw_person(draw, 1250, 770, 2.1, palette, "sit")
        draw_bag(draw, 1340, 930, 1.4, palette)
    elif scene_mod == 1:
        draw_pool(draw, w, h, palette, 650, True)
        draw_person(draw, 1260, 650, 1.55, palette)
        for x in [1110, 1420]:
            draw.line((x, 490, x + 90, 1060), fill=(*accent, 120), width=8)
    elif scene_mod == 2:
        draw.rounded_rectangle((930, 380, 1660, 930), radius=70, fill=(*blend(warm, (255, 255, 255), 0.18), 225))
        draw_person(draw, 1300, 685, 1.8, palette)
        for i in range(3):
            draw.arc((1020 + i * 100, 760 + i * 12, 1520 + i * 40, 1060 + i * 28), 200, 330, fill=(*accent, 150), width=7)
    elif scene_mod == 3:
        draw.rounded_rectangle((950, 500, 1680, 1050), radius=35, fill=(*blend(base, (255, 255, 255), 0.55), 230))
        draw.rectangle((1010, 560, 1620, 880), fill=(*blend(warm, (255, 255, 255), 0.20), 220))
        draw_person(draw, 1280, 820, 1.75, palette, "sit")
        draw_bag(draw, 1110, 930, 1.1, palette)
    elif scene_mod == 4:
        draw_pool(draw, w, h, palette, 560, False)
        draw_person(draw, 1280, 650, 1.55, palette)
        for dx, dy in [(120, -120), (210, -20), (-120, -60)]:
            draw.ellipse((1280 + dx - 16, 450 + dy - 16, 1280 + dx + 16, 450 + dy + 16), fill=(*accent, 130))
    else:
        draw.rectangle((1010, 420, 1700, 1020), fill=(*blend(warm, (255, 255, 255), 0.22), 220))
        draw_bag(draw, 1160, 760, 2.1, palette)
        draw_person(draw, 1470, 720, 1.55, palette)
        draw.line((980, 1080, 1700, 1080), fill=(*ink, 100), width=4)

    # Foreground plants and light strokes for editorial texture.
    for i in range(12):
        x = 60 + i * 54
        y = 1010 + (i % 4) * 42
        draw.line((x, h, x + 70, y), fill=(*blend(accent, ink, 0.10), 115), width=4)
        draw.ellipse((x + 50, y - 18, x + 104, y + 22), fill=(*blend(base, accent, 0.45), 110))
    for i in range(4):
        draw.arc((880 + i * 130, 1080 + i * 16, 1500 + i * 50, 1270 + i * 12), 185, 345, fill=(*blend(base, (255, 255, 255), 0.60), 90), width=5)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=94)


def ensure_sources(content_no: str, page: dict[str, object]) -> list[dict[str, str]]:
    source_rows = []
    roles = ["title", "points", "accent_01", "accent_02"] + [f"section_{i}" for i in range(1, len(page["sections"]) + 1)]  # type: ignore[arg-type]
    missing = []
    for role in roles:
        found = REFS / f"{content_no}_{role}.png"
        if not found.exists():
            found = None
        if found is None:
            missing.append(f"{content_no}_{role}.png")
            continue
        filename = found.name
        source_rows.append({"role": role, "source_file": filename, "work_file": ""})
    if missing:
        raise FileNotFoundError(
            "Generated source images are missing. Do not create simplified or placeholder backgrounds. "
            f"Create/copy real generated images into {REFS}: " + ", ".join(missing)
        )
    return source_rows


def make_bgm(base: Path, content_no: str) -> None:
    video = base / "video"
    video.mkdir(parents=True, exist_ok=True)
    path = video / f"bgm_cover_swimwear_{content_no}.wav"
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


def make_scenes(base: Path, content_no: str, scene_sources: list[str], fit_mode: str = "cover") -> None:
    scenes = base / "video" / "scene_backgrounds"
    if scenes.exists():
        shutil.rmtree(scenes)
    scenes.mkdir(parents=True, exist_ok=True)
    for idx, name in enumerate(scene_sources, 1):
        img = Image.open(base / "images" / "work" / name).convert("RGB")
        if fit_mode == "contain_on_blur":
            scene = contain_on_blur(img, (1200, 1200))
        else:
            scene = cover_crop(img, (1200, 1200), 0, 0)
        scene.save(scenes / f"{content_no}_scene{idx:02d}.jpg", quality=94)


def page_copy(page: dict[str, object]) -> str:
    lines = [f"# {page['title']}", ""]
    lines.extend(str(p) for p in page["lead"])  # type: ignore[index]
    for title, body in page["sections"]:  # type: ignore[assignment]
        lines.extend(["", f"## {title}", "", body])
    return "\n".join(lines).strip() + "\n"


def build_page(content_no: str, page: dict[str, object]) -> None:
    base = PRODUCTION / f"{content_no}_{page['slug']}" / "納品用"
    delivery = base / "images" / "delivery"
    work = base / "images" / "work"
    originals = work / "generated_originals"
    data = base / "data"
    for path in [delivery, work, originals, data, base / "video"]:
        path.mkdir(parents=True, exist_ok=True)

    (base / "page_copy.md").write_text(page_copy(page), encoding="utf-8")

    source_rows = ensure_sources(content_no, page)
    for row in source_rows:
        src = Image.open(REFS / row["source_file"]).convert("RGB")
        bg_name = f"{content_no}_{row['role']}_bg.png"
        row["work_file"] = bg_name
        src.save(originals / bg_name)
        src.save(work / bg_name)
    write_csv(data / "image_source_manifest.csv", ["role", "source_file", "work_file"], source_rows)

    title = cover_crop(Image.open(work / f"{content_no}_title_bg.png").convert("RGB"), (1600, 900), -0.13, 0.0)
    draw_lines(title, page["short_title"], 94, 294, [70, 82], [104, 108])  # type: ignore[arg-type]
    title.save(delivery / f"{content_no}_title.jpg", quality=94)
    title.save(delivery / f"{content_no}_thumbnail.jpg", quality=94)

    points = cover_crop(Image.open(work / f"{content_no}_points_bg.png").convert("RGB"), (1600, 520), -0.16, 0.0)
    draw_lines(points, page["points"], 98, 70, [46, 34, 34, 34], [74, 56, 56, 56])  # type: ignore[arg-type]
    points.save(work / f"{content_no}_points.jpg", quality=94)

    banner_rows = []
    sections = page["sections"]  # type: ignore[assignment]
    for idx, (section_title, _body) in enumerate(sections, 1):
        role = f"section_{idx}"
        img = cover_crop(Image.open(work / f"{content_no}_{role}_bg.png").convert("RGB"), (1600, 520), -0.18, 0.0)
        words = str(section_title)
        if len(words) > 10:
            split = min(range(5, len(words)), key=lambda n: abs(n - len(words) / 2))
            lines = [words[:split], words[split:]]
        else:
            lines = [words]
        draw_lines(img, lines, 92, 148, [54, 54], [78, 72])
        out = f"{content_no}_section_{idx}.jpg"
        img.save(delivery / out, quality=94)
        banner_rows.append({"filename": out, "headline": "\n".join(lines), "subcopy": "", "asset_type": f"section_{idx}"})

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
        {"order": "2", "part_type": "video", "file_or_source": f"video/opening_cm_{content_no}_vertical.mp4", "note": "タイトル直下の動く目次CM", "placement": "", "after_section": ""},
        {"order": "3", "part_type": "points_image", "file_or_source": f"images/work/{content_no}_points.jpg", "note": "動画用ポイント画像 TSVには出さない", "placement": "", "after_section": ""},
    ]
    order = 4
    for idx in range(1, len(sections) + 1):
        parts.append({"order": str(order), "part_type": "banner", "file_or_source": f"images/delivery/{content_no}_section_{idx}.jpg", "note": "章バナー", "placement": "before_body", "after_section": str(idx)})
        order += 1
        if idx == 2:
            parts.append({"order": str(order), "part_type": "accent_image", "file_or_source": f"images/delivery/{content_no}_accent_01.jpg", "note": "文字なし正方形アクセント", "placement": "after_body", "after_section": "2"})
            order += 1
        if idx == 4:
            parts.append({"order": str(order), "part_type": "accent_image", "file_or_source": f"images/delivery/{content_no}_accent_02.jpg", "note": "文字なし正方形アクセント", "placement": "after_body", "after_section": "4"})
            order += 1
    parts.append({"order": str(order), "part_type": "product_parts", "file_or_source": "product_ids.csv", "note": "関連商品パーツ", "placement": "", "after_section": ""})
    write_csv(data / "rakuten_parts_plan.csv", ["order", "part_type", "file_or_source", "note", "placement", "after_section"], parts)

    scene_files = [f"{content_no}_title_bg.png", f"{content_no}_section_1_bg.png", f"{content_no}_points_bg.png", f"{content_no}_section_2_bg.png", f"{content_no}_section_4_bg.png", f"{content_no}_section_5_bg.png"]
    make_scenes(base, content_no, scene_files, str(page.get("video_scene_fit", "cover")))
    video_copy = [
        (f"{content_no}_scene01.jpg", "\n".join(page["short_title"]), "title_type"),  # type: ignore[arg-type]
        (f"{content_no}_scene02.jpg", str(sections[0][0]), "rise_fade"),
        (f"{content_no}_scene03.jpg", "\n".join(page["points"]), "points"),  # type: ignore[arg-type]
        (f"{content_no}_scene04.jpg", str(sections[1][0]), "slide_left"),
        (f"{content_no}_scene05.jpg", str(sections[3][0]), "rise_fade"),
        (f"{content_no}_scene06.jpg", str(sections[4][0]), "slide_right"),
    ]
    storyboard = []
    for idx, (background, copy, animation) in enumerate(video_copy, 1):
        storyboard.append({"scene": str(idx), "background_file": background, "duration_sec": "5.2" if idx == 1 else ("4.1" if idx == 3 else "3.6"), "display_copy": copy, "text_animation": animation, "crop_x": "0", "crop_y": "0"})
    write_csv(data / "video_storyboard.csv", ["scene", "background_file", "duration_sec", "display_copy", "text_animation", "crop_x", "crop_y"], storyboard)

    write_csv(base / "product_ids.csv", ["product_id", "role", "note"], [{"product_id": pid, "role": "関連商品", "note": "体型カバー水着 上下セット"} for pid in page["product_ids"]])  # type: ignore[union-attr]

    notes = f"""# 制作メモ {content_no}

- 元タイトル案: h-mzg20 / c-mizugi_nbf / usbswc / usbswb / b-mizugi-3
- タイトル: {page['title']}
- column_pattern: {page['pattern']}
- visual_style: {page['style']}
- 商品画像確認: 楽天CSVから対象SKUの説明、画像パス、サイズ展開を確認。今回は特殊商品として `reference_mode=ai_product_reference_generation` を採用し、商品画像を参照しながら生成AIで新規画像を作成。実商品画像そのものは納品画像へ貼り込まない。
- 差別化: 024共通準備、025着やせ、026ふんわり、027本音、028コミカル、029実用、030家族水遊び、031比較。
- 画像: タイトル、章バナー、アクセント画像、動画背景は用途ごとに別の生成元画像を使用。簡易図形、仮背景、プレースホルダーは不採用。
- 生成元: `references/generated_024_031` 内の実生成画像のみを参照。生成元が不足する場合はビルドを停止し、簡易データで代替しない。
- 注意: 納品画像は生成AIによる新規画像。商品画像は参照のみで、リンクは関連商品パーツで行う。
"""
    (base / "notes.md").write_text(notes, encoding="utf-8")
    make_bgm(base, content_no)


def build() -> None:
    requested = sys.argv[1:]
    targets = requested or list(PAGES)
    unknown = [content_no for content_no in targets if content_no not in PAGES]
    if unknown:
        raise SystemExit(f"Unknown content numbers: {', '.join(unknown)}")
    for content_no in targets:
        page = PAGES[content_no]
        build_page(content_no, page)


if __name__ == "__main__":
    build()
