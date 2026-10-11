# 確認したこと、していないこと

版 0.1.0（2026-10-11）の時点の記録です。

## 確認したこと

- 139件の単体テストが、Python 3.11.7 と 3.12.14（macOS）で、失敗0・エラー0・スキップ0で通った。それぞれ新しい仮想環境で、標準ライブラリだけを使って実行した。
- `verify_reproduction.py` が、両方のPythonで正常終了した。合成実験を計算し直した結果は、`results/experiments.json` と `results/frontier.json` に構造が一致した。
- `scripts/verify_fresh_clone.sh` を、手元のリポジトリのパスを取得元にして実行し、一時ディレクトリへのクローン、新しい仮想環境での `pip install -e .`、テスト、`verify_reproduction.py` が最後まで通った。
- `demos/green_room.html` を手元の簡易サーバー経由でブラウザに読み込み、観測を止めて1秒進める操作で、描画の古さ0ms・実測の古さ1000ms・判定 `MEASUREMENT_TOO_OLD` になることを確かめた。画面幅ごとの表示崩れは確かめていない。
- Python 3.10.22 でも `PYTHON=/opt/homebrew/bin/python3.10 scripts/verify_fresh_clone.sh` を実行した。139件のテストと `verify_reproduction.py` が通った。

139は、テストのメソッドの数です。守れる範囲の広さや、安全性の点数ではありません。

## 確認していないこと

- GitHub Actions上での実行。ワークフローは書いてあるが、2026-10-11 の時点では GitHub 上で一度も走っていない。
- 本物のMCPやOAuthとの接続、本物のLLMの振る舞い、本物の署名の生成と検証、実際の脆弱性データベースを使ったスキャン。
- 実機、カメラ、モーター、停止距離の測定。
- 人が使ったときの使いやすさの評価。
- 本番の運用や、障害からの復旧。
- Windowsでの実行。

## 結果の読み方

`results/experiments.json` と `results/frontier.json` は、どちらも合成した場面を走らせた結果です。実際の運用で測った数字ではありません。追加実験の比較相手は、意図的に単純にした規則です。既存の製品と性能を比べたものではありません。

`results/frontier.json` の記憶の実験は、EAL-Bench（Cerruti, Okamoto & Erol, arXiv:2609.01836）の再現ではありません。手で書いた要約を使った、合成の確認です。
