# 追加実験：何を比較したか（`frontier_experiments.py`）

出力：`results/frontier.json`。全てローカルの合成条件。実LLMは呼び出していません。

## 公開文脈
同じartifact hashでも、workflowが違えばWORKFLOW_MISMATCH、宛先が違えばDESTINATION_MISMATCH。想定どおりのものはALLOW_REVIEWED_RELEASE。入力のclaimは検証済みと仮定した固定値であり、暗号の検証自体ではありません。

## 道具定義
依存一覧を変えないという合成条件で、ツールのdescriptionだけ変えるとDESCRIPTOR_CHANGED。定義が同じでも、許可されていない操作はOPERATION_NOT_GRANTED。実ネットワーク遮断の試験ではありません。

## 合計予算
一回80単位・100要求、一回の上限100。単発検査だけの不十分な比較器は8,000単位を通す。共有の合計枠300を同一DBで予約すると3件240単位、残り97件は拒否。80・100・300という数は合成した単位で、物理量や金銭を測ったものではありません。未知の結果は予約を返さず、信頼された照合を必要にします。停止・再開後の古い予約はOLD_EPOCHです。

## 記憶と現在の許可
過去のgrantは実在しても、後のrevokeがあればNO_CURRENT_GRANT。古い台帳を現在のHeadと比較するとPOLICY_VIEW_NOT_CURRENT。新しい明示的なgrantは許可。Headも古く戻した場合はこの方法だけで検出できないという限界をテストへ残しています。

## 証拠の古さ
測定時刻1000msのまま、描画を2000msへ更新。表示は0ms、実測は1000ms古い。今回の特定操作では実測が必要なため拒否。これを制御一般での予測禁止と解釈しません。HTMLデモは同じ考え方を操作できます。

## 統合前の注意
各モジュールの入力契約は一つの完成APIではありません。authority.pyの秒時計と新しいevidence_age.pyのミリ秒時計、観測鮮度の350msと250msは別の模型設定です。配線のようにそのままつなげず、採用する一つの単位・clock domain・policiesを決めてから統合してください。
