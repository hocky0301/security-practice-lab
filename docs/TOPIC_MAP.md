# 分野とコードの対応

分野ごとに、読むモジュールと、それが扱う問いをまとめます。各分野には解説記事を書く予定です。記事が公開されたら、ここにリンクを足します。いまは対応するリンクはありません。

| 分野 | モジュール | 扱うこと |
|---|---|---|
| 公開 | `security_lab/release.py`, `security_lab/release_context.py` | レビューしたバイト列と、公開の文脈（作った工程・公開先）を別々に固定する |
| 依存・道具 | `security_lab/dependencies.py`, `security_lab/tool_contracts.py` | 検査が完了していること、期限つきの例外、道具の定義が変わったこと、許可する操作を狭く保つこと |
| 認可・予算 | `security_lab/authority.py`, `security_lab/capability_budget.py` | 内容に結びついた1回限りの承認、累積の予算、世代、再送、結果が分からない場合 |
| 記憶・復旧 | `security_lab/memory_authority.py`, `security_lab/audit.py`, `security_lab/recovery.py` | 記憶の文面を許可としない、現在の台帳と失効の状態を区別する、復旧で古い権限を戻さない |
| 観測 | `security_lab/observations.py`, `security_lab/evidence_age.py`, `demos/green_room.html` | 実測・予測・描画の時刻を混ぜない |

共通の部品は `security_lab/common.py` です。合成実験は `security_lab/experiments.py` と `security_lab/frontier_experiments.py` が走らせ、結果を `results/` に保存します。
