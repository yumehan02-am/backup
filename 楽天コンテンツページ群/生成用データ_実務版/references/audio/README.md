# BGM基準音量

基準音声:

```text
standard_bgm_ref.wav
```

この音声は、2026-09-03に確認して問題なしと判断した動画BGMから抽出したもの。

測定値:

```text
Integrated loudness: -32.8 LUFS
True peak: -21.8 dBFS
```

運用基準:

- 標準BGMは `-33 LUFS` を目標値にする。
- 許容範囲は `-34 LUFS から -32 LUFS`。
- True peak は `-9 dBTP 以下` を上限値にする。
- 迷う場合は、この基準音声と聴感を合わせる。

FFmpeg正規化の標準設定:

```text
loudnorm=I=-33:LRA=7:TP=-9
```
