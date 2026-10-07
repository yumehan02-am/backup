# custom

このフォルダは、配布用の共通ルールとは分けて、店舗・会社ごとの画像テイストや任意参照素材を置く場所です。

共通ルールを他社へ渡す場合、この `custom/{brand}/` 配下を各社の素材に差し替えます。

## 標準構成

```text
custom/
  yumehan/
    reference/
      illustration_style/
        character/
        explanation/
      photo_style/
        lifestyle/
    optional_assets/
      backgrounds/
      usable_people/
      textures/
      seasonal_props/
      color_mood/
```

## 参照モード

- 実写風生成画像の標準は `reference_mode=none`。
- 実写風生成では、ユーザーが明示した場合だけ `optional_assets` や `photo_style` を参照する。
- イラスト主体コンテンツの標準は `reference_mode=illustration_style`。
- イラスト主体では、ブランド別の人物イラスト・説明用イラストのリファレンスがあれば、線、色、人物の存在感の基本ラインとして参照する。
- 人物イラストでは、基準画像だけでなく同じフォルダの `style_notes.md` を必ず確認する。年齢感、露出制限、禁止事項、キャラクターの存在感は、画像参照よりテキストルールを優先する。

参照画像はそのまま再現しない。構図、色味、生活感、人物の存在感などの参考に留める。

使用した参照フォルダ、画像名、確認した `style_notes.md` は、各ページの `notes.md` に記録する。
