# pywebviewにおける「Python監視 → JavaScriptへPush」設計

## 1. はじめに

pywebviewを使ったアプリでは、PythonとJavaScriptの両方で繰り返し処理を実装できます。

たとえばPLC監視であれば、次の2つの考え方があります。

1. Python側でPLCを繰り返し監視する
2. JavaScript側の `setInterval()` からPython APIを定期的に呼び出す

今回検討したモータ電流値受信アプリでは、PLCから受信した1000点の電流値をChart.jsでできるだけ早く表示したいという要求があります。

この場合の重要な結論は次の通りです。

> **PLC監視はPython側で継続し、データ受信が完了した瞬間にPythonからJavaScriptへ通知してChart.jsを更新する。**

つまり、

```text
Python監視 → JavaScriptへPush
```

というイベント駆動型の構成です。

これは今後のpywebviewアプリ設計において非常に重要な考え方になります。

---

# 2. 現在のアプリ構成

現在のモータ電流値受信アプリでは、Python側でPLC監視を実行しています。

代表的な部分は次の処理です。

```python
while not self.stop_event.is_set():
    try:
        for config in MOTOR_CONFIGS:
            if self.stop_event.is_set():
                break

            self._check_request(config)

    except (ConnectionError, OSError, TimeoutError, RuntimeError) as error:
        print(f"[{current_time()}] PLC通信エラー: {error}")

    except ValueError as error:
        print(f"[{current_time()}] PLCデータエラー: {error}")

    self.stop_event.wait(POLL_INTERVAL_SECONDS)
```

この監視ループは、

```python
POLL_INTERVAL_SECONDS = 0.1
```

なので、約100ms周期でPLC要求信号を確認します。

また、監視処理そのものはGUIスレッドとは別のスレッドで実行されています。

```python
self.monitor_thread = threading.Thread(
    target=self.receiver.run,
    name="plc-monitor",
    daemon=False,
)

self.monitor_thread.start()
```

したがって、GUIの操作とは独立してPLC監視を継続できます。

---

# 3. 現在のJavaScript側の役割

現在のJavaScriptは、PLCを直接監視していません。

JavaScriptからPython APIを呼び出して、

- 監視開始
- 監視停止
- 現在状態取得

を行っています。

例：

```javascript
async function startMonitoring() {
    try {
        const result = await pywebview.api.start_monitoring();
        updateStatus(result);
    } catch (error) {
        console.error(error);
        statusElement.textContent = "開始エラー";
    }
}
```

これは、

```text
JavaScript
    ↓
pywebview.api.start_monitoring()
    ↓
Python
```

という通信です。

つまり現在のアプリではすでに、

```text
JavaScript → Python
```

の通信を利用しています。

今回新しく検討したのは、その逆方向である、

```text
Python → JavaScript
```

です。

この2つを組み合わせることで、PythonとJavaScriptの**双方向通信**が可能になります。

---

# 4. PythonとJavaScriptの役割分担

pywebviewアプリでは、PythonとJavaScriptの役割を明確に分けると設計が非常に分かりやすくなります。

基本方針は次のように考えるとよいです。

```text
Python
    ├─ PLC通信
    ├─ PLC監視
    ├─ データ取得
    ├─ データ保存
    ├─ 状態管理
    ├─ ThreadPoolExecutor
    ├─ Lock / Event
    └─ 業務ロジック

JavaScript
    ├─ HTML画面操作
    ├─ ボタン操作
    ├─ 表示更新
    ├─ Chart.js
    └─ ユーザーインターフェース
```

簡単に表現すると、

> **Pythonは仕事をする側**
>
> **JavaScriptは人間に見せる側**

と考えると理解しやすいです。

---

# 5. JavaScript側でPLC監視する方法

技術的には、JavaScript側で次のような処理を書くこともできます。

```javascript
setInterval(async () => {
    await pywebview.api.check_plc();
}, 100);
```

この場合の処理は次のようになります。

```text
JavaScript
    ↓ 100msごと
pywebview API
    ↓
Python
    ↓
PLC通信
    ↓
Python
    ↓
JavaScript
```

この方式でも動作は可能です。

しかし、PLC監視の主体がJavaScriptになります。

---

# 6. JavaScriptのsetIntervalでPLC監視する場合の問題点

## 6.1 PythonとJavaScript間の往復が増える

PLC監視周期を100msとすると、

```text
1秒    = 10回
1分    = 600回
1時間  = 36,000回
```

JavaScriptからPython APIを呼び出すことになります。

PLC監視だけのために毎回、

```text
JavaScript
    ↓
Python
```

を経由する必要はありません。

Python自身がPLC通信を担当しているのであれば、Python内部だけで監視を完結させた方が自然です。

---

## 6.2 GUIとPLC監視が強く結び付く

JavaScript主導にすると、

```text
JavaScriptが監視を実行
        ↓
Python API
        ↓
PLC
```

となります。

つまりGUI側のJavaScriptが正常に動作していることがPLC監視の前提になります。

一方、現在のPython主体の構成なら、

```text
Python監視スレッド
        ↓
PLC監視
```

なので、GUI表示処理とは独立しています。

設備監視アプリでは、この独立性は大きな利点です。

---

# 7. Python側でPLC監視するメリット

現在のPython側では、

```python
while not self.stop_event.is_set():
```

によって監視処理を継続しています。

停止するときは、

```python
self.stop_event.set()
```

を実行します。

さらに終了時には、

```python
self.receiver.stop()

if monitor_thread is not None:
    monitor_thread.join()

self.receiver.executor.shutdown(wait=True)
```

という処理があります。

したがって、

```text
監視開始
    ↓
Python監視スレッド
    ↓
PLC監視
    ↓
停止要求
    ↓
Eventをset
    ↓
監視ループ終了
    ↓
thread.join()
    ↓
ThreadPoolExecutor終了
    ↓
アプリ終了
```

という処理のライフサイクルがPython側だけで完結しています。

これは非常に分かりやすい構造です。

---

# 8. Chart.jsを追加した場合の問題

今後、このアプリではPLCから受信したモータ電流値1000点をChart.jsで表示する予定です。

現在の受信処理では、次のように1000点を読み込んでいます。

```python
values = kv_com.read_devices_d(
    self.plc_ip_address,
    config.data_start_device,
    DATA_POINT_COUNT,
)
```

その後、

```python
csv_path = save_csv(config, values)
```

でCSV保存しています。

ここで新しく、

```text
受信した1000点をChart.jsへ表示したい
```

という要求が発生します。

---

# 9. JavaScript側から最新データを定期取得する方法

一つの方法はJavaScript側で、

```javascript
setInterval(async () => {
    const data = await pywebview.api.get_latest_data("motor1");

    chart.data.datasets[0].data = data;
    chart.update();
}, 1000);
```

などとする方法です。

処理は次のようになります。

```text
Python
    ↓
PLCデータ受信
    ↓
最新データとして保存


JavaScript
    ↓
一定時間ごとに確認
    ↓
最新データ取得
    ↓
Chart.js更新
```

これは比較的シンプルな方法です。

---

# 10. setInterval方式のタイムラグ

しかし、この方法には明確な欠点があります。

たとえば、

```javascript
setInterval(updateChart, 1000);
```

の場合、JavaScriptは1秒ごとしか確認しません。

タイミングによっては、

```text
Python側データ受信完了
        ↓
        │
        │ 最大約1秒待つ
        │
        ↓
次のsetInterval
        ↓
データ取得
        ↓
Chart.js描画
```

となります。

つまり、Python側ではすでにデータ受信が完了しているのに、JavaScriptが確認するまで待つ必要があります。

「受信したらすぐに波形を表示したい」という今回の要求では、この待ち時間はできるだけ無くしたいところです。

---

# 11. Python監視 → JavaScriptへPush

そこで有効なのが、

```text
Python監視 → JavaScriptへPush
```

という方式です。

考え方は非常に単純です。

```text
PLC
 ↓
Python
 ↓
1000点受信完了
 ↓
JavaScriptへ通知
 ↓
Chart.js更新
```

JavaScript側から確認しに行くのではありません。

Python側が、

> 「新しいデータを受信した」

というタイミングでJavaScriptへ通知します。

---

# 12. PullとPushの違い

この違いは、

```text
Pull
```

と、

```text
Push
```

で考えると理解しやすくなります。

## Pull方式

JavaScript側が定期的にPythonへ問い合わせます。

```text
JS「新しいデータある？」
Python「まだない」

JS「新しいデータある？」
Python「まだない」

JS「新しいデータある？」
Python「ある」
```

これが `setInterval()` を使った定期監視です。

---

## Push方式

Python側が新しいデータを受信した瞬間に通知します。

```text
Python「新しいデータを受信した」
        ↓
JavaScript
        ↓
Chart.js更新
```

JavaScript側は定期監視する必要がありません。

---

# 13. 今回の用途ではPush方式が適している理由

今回のモータ電流値は、常時1点ずつ流れてくるリアルタイムストリームではありません。

処理は、

```text
PLC要求ON
    ↓
1000点取得
    ↓
1本の波形完成
    ↓
表示
```

という形です。

つまり、

> **「1000点の波形データが完成した」というイベント**

が存在します。

このような処理はPush方式と非常に相性が良いです。

---

# 14. 目標とする処理フロー

最終的に目指す構成は次のようになります。

```text
PLC要求信号
    ↓
Python監視スレッド
    ↓
要求ON検出
    ↓
ThreadPoolExecutor
    ↓
_receive_and_save()
    ↓
1000点データ受信
    ↓
    ├─────────────→ CSV / SQLite保存
    │
    └─────────────→ JavaScriptへ通知
                         ↓
                    Chart.js
                         ↓
                    波形即表示
```

PLC通信処理とChart.js描画処理がきれいに分離されます。

---

# 15. Python → JavaScript通信

pywebviewでは、Python側からJavaScriptの処理を実行できます。

概念的には次のようになります。

```python
window.evaluate_js(
    "updateMotorChart(...)"
)
```

JavaScript側には、

```javascript
function updateMotorChart(values) {
    chart.data.datasets[0].data = values;
    chart.update();
}
```

のような関数を用意します。

Pythonが受信処理完了時にこのJavaScript関数を実行することで、

```text
Python
    ↓
JavaScript
    ↓
Chart.js
```

という通信が成立します。

---

# 16. PythonとJavaScriptの双方向通信

これまでのアプリでは、

```text
JavaScript → Python
```

が中心でした。

たとえば、

```javascript
await pywebview.api.start_monitoring();
```

です。

今回、

```text
Python → JavaScript
```

を追加すると、

```text
JavaScript
    ↓
Python
    ↓
JavaScript
```

という双方向通信が可能になります。

図にすると次のようになります。

```text
┌─────────────────────┐
│     JavaScript      │
│                     │
│ ボタン              │
│ Chart.js            │
└─────────┬───────────┘
          │
          │ JS → Python
          ↓
┌─────────────────────┐
│       Python        │
│                     │
│ PLC監視             │
│ PLC通信             │
│ データ保存          │
└─────────┬───────────┘
          │
          │ Python → JS
          ↓
┌─────────────────────┐
│     JavaScript      │
│                     │
│ Chart.js更新        │
└─────────────────────┘
```

この双方向通信が使えるようになると、pywebviewアプリの設計自由度が大きく上がります。

---

# 17. MotorReceiverから直接JavaScriptを呼ぶべきか

技術的には、`MotorReceiver` に `window` を渡して、

```python
self.window.evaluate_js(...)
```

とすることもできます。

しかし、この構造では、

```text
MotorReceiver
    ↓
PLC処理
    ↓
GUI操作
```

となり、PLC通信クラスがGUIの存在まで知ることになります。

これは責務が混ざりやすくなります。

---

# 18. AppApiを橋渡し役にする

より整理された設計では、

```text
MotorReceiver
    ↓
AppApi
    ↓
JavaScript
```

という構造にします。

役割は次のようになります。

## MotorReceiver

```text
PLC監視
PLC通信
モータ電流値受信
CSV / SQLite保存
```

だけを担当します。

---

## AppApi

```text
Python
    ↕
JavaScript
```

の橋渡しを担当します。

---

## JavaScript

```text
HTML
Chart.js
画面更新
```

を担当します。

この役割分担なら、

```text
MotorReceiver
    → PLCのことだけ知る

AppApi
    → PythonとGUIの接続を知る

JavaScript
    → 画面表示だけ知る
```

となり、メンテナンスしやすくなります。

---

# 19. コールバックを利用する考え方

さらに整理するなら、`MotorReceiver` がデータを受信したときにコールバックを呼ぶ方式が使えます。

概念的には、

```python
receiver = MotorReceiver(
    PLC_IP_ADDRESS,
    on_data_received=api.on_data_received,
)
```

のような構造です。

処理は、

```text
MotorReceiver
    ↓
1000点受信完了
    ↓
on_data_received()
    ↓
AppApi
    ↓
JavaScript
    ↓
Chart.js
```

となります。

この構造にすると、`MotorReceiver` はChart.jsやpywebviewの存在を知る必要がありません。

---

# 20. ただし最初から複雑にしすぎない

今回の重要な方針は、

> **まず動く最小構成を作る**

ことです。

いきなり、

- 3モータ
- 複数Chart.js
- 複雑なコールバック
- 状態管理
- SQLite
- エラー通知

をすべて追加すると理解が難しくなります。

まず、

```text
Motor1
    ↓
1000点受信
    ↓
Python → JavaScript
    ↓
Chart.js表示
```

だけを実装するのがよいです。

これが成功すれば、

```text
Motor2
Motor3
```

はほぼ同じ考え方で追加できます。

---

# 21. 3モータへ拡張した場合

最終的には次のような構成が考えられます。

```text
                    ┌─ Motor1 1000点
PLC → Python ───────┼─ Motor2 1000点
                    └─ Motor3 1000点
                           ↓
                       AppApi
                           ↓
                     JavaScript
                           ↓
                       Chart.js
```

受信したモータだけ対応するChart.jsを更新します。

たとえば、

```javascript
updateMotorChart("motor1", values);
```

のようにモータ名も一緒に渡せば、

```text
motor1 → Chart1
motor2 → Chart2
motor3 → Chart3
```

と振り分けられます。

---

# 22. setInterval方式は悪い設計ではない

ここは重要です。

JavaScriptの `setInterval()` を使うこと自体が悪いわけではありません。

たとえば、

- 現在時刻表示
- 画面上の状態更新
- CPU使用率表示
- 定期的なステータス取得
- 多少の遅延が問題にならない情報

には非常に便利です。

たとえば、

```javascript
setInterval(updateStatus, 1000);
```

という使い方は自然です。

---

# 23. PLC監視をsetIntervalにする場合

PLC監視そのものをJavaScript側へ移す方法も実装可能です。

```javascript
setInterval(async () => {
    await pywebview.api.check_plc();
}, 100);
```

小規模なアプリであれば、この方式でも十分動く可能性があります。

したがって、

> 「Push方式が難しすぎたらsetIntervalへ戻す」

という判断も現実的です。

しかし、今回のアプリでは、

- PLC通信
- ThreadPoolExecutor
- threading.Event
- Lock
- CSV保存

など、すでにPython側に多くの処理があります。

そのためPLC監視だけJavaScript側へ移動すると、かえって責務が分散します。

---

# 24. 3つの方式の比較

| 方式 | 構成 | 表示速度 | シンプルさ | おすすめ |
|---|---|---:|---:|---:|
| Python監視 → JSへPush | イベント駆動 | 非常に速い | 中 | ★★★★★ |
| Python監視 + JS polling | JSが最新データを定期確認 | 間隔分遅れる | 高 | ★★★★☆ |
| JS setInterval → PLC監視 | JSがPLC監視を指揮 | 周期依存 | 一見簡単 | ★★☆☆☆ |

今回の第一候補は、

```text
Python監視 → JSへPush
```

です。

---

# 25. 表示速度の考え方

Push方式では、

```text
PLCから1000点取得
    ↓
Python
    ↓
JavaScriptへ転送
    ↓
Chart.js描画
```

となります。

setInterval方式に存在する、

```text
次の確認タイミングまで待つ
```

という人工的な待ち時間がありません。

したがって、受信完了から表示までの時間をできるだけ短くできます。

1000点程度の波形表示であれば、Chart.jsで扱うデータ量としても現実的です。

---

# 26. PLC監視周期と画面更新周期は別物

非常に重要な点です。

たとえばPython側では、

```text
PLC監視周期 = 100ms
```

だとしても、JavaScript側の画面更新周期を100msにする必要はありません。

役割が違います。

```text
Python
    ↓
PLC監視
    ↓
100ms周期


JavaScript
    ↓
画面表示
```

Push方式ならJavaScript側にはそもそも監視周期が不要です。

新しいデータが来たときだけ更新します。

---

# 27. イベント駆動という考え方

今回の設計は、

```text
定期的に確認する
```

のではなく、

```text
何かが発生したら処理する
```

という考え方です。

これを一般に、

> **イベント駆動**

と考えることができます。

今回ならイベントは、

```text
モータ電流値1000点の受信完了
```

です。

そのイベントをきっかけとして、

```text
JavaScript通知
    ↓
Chart.js更新
```

を実行します。

---

# 28. 今後応用できる処理

この技術を覚えると、Chart.js以外にも使えます。

たとえば、

## PLCアラーム発生

```text
Python
    ↓
PLCアラーム検出
    ↓
JavaScriptへ通知
    ↓
画面にアラーム表示
```

## 通信異常

```text
Python
    ↓
PLC通信異常
    ↓
JavaScriptへ通知
    ↓
ステータス表示を赤色に変更
```

## データ保存完了

```text
Python
    ↓
SQLite保存完了
    ↓
JavaScriptへ通知
    ↓
「保存完了」表示
```

## 処理進捗

```text
Python
    ↓
処理進捗更新
    ↓
JavaScriptへ通知
    ↓
プログレスバー更新
```

つまり、

```text
Pythonで発生したイベント
        ↓
JavaScriptへPush
        ↓
画面即更新
```

というパターンを幅広く利用できます。

---

# 29. pywebviewアプリ設計の基本形

今後の標準構成として、次の形は非常に有力です。

```text
┌───────────────────────────────┐
│           Python              │
│                               │
│ PLC通信                       │
│ DB処理                        │
│ ファイル処理                  │
│ ThreadPoolExecutor            │
│ threading                     │
│ 業務ロジック                  │
└──────────────┬────────────────┘
               │
          pywebview
               │
          双方向通信
               │
┌──────────────┴────────────────┐
│         JavaScript            │
│                               │
│ HTML操作                      │
│ Chart.js                      │
│ ボタン                        │
│ 状態表示                      │
│ ユーザー操作                  │
└───────────────────────────────┘
```

PythonとJavaScriptの長所をそれぞれ活かす構成です。

---

# 30. 今回のアプリで推奨する最終方針

今回のモータ電流値受信アプリでは、次の方針を推奨します。

## PLC監視

現在のままPython側。

```python
while not self.stop_event.is_set():
```

を使用します。

---

## PLC要求検出

Python側。

現在の `_check_request()` を継続利用します。

---

## モータ電流値受信

Python側。

`ThreadPoolExecutor` でモータごとに並列処理します。

---

## CSV / SQLite保存

Python側。

---

## グラフ描画

JavaScript側のChart.js。

---

## グラフ更新タイミング

JavaScriptの `setInterval()` ではなく、

```text
Pythonが1000点受信完了
    ↓
JavaScriptへPush
    ↓
Chart.js即更新
```

を第一候補とします。

---

# 31. 実装するときの段階的な進め方

次回の改造では、次の順番で進めると理解しやすくなります。

```text
STEP 1
Chart.jsで固定データを表示する
        ↓
STEP 2
JavaScript関数からChart.jsを更新できるようにする
        ↓
STEP 3
PythonからJavaScript関数を呼ぶ
        ↓
STEP 4
Motor1の1000点を渡す
        ↓
STEP 5
Motor1受信完了時に自動更新
        ↓
STEP 6
Motor2 / Motor3へ拡張
```

いきなり全部を実装しないことがポイントです。

---

# 32. 最重要ポイント

今回の検討で最も重要なのは、

```text
PythonかJavaScriptのどちらで無限ループを書くか
```

という単純な話ではありません。

本質は、

> **どちらが処理の主体になるべきか**

です。

PLC通信はPythonの責務です。

Chart.js表示はJavaScriptの責務です。

したがって、

```text
Python
    ↓
PLCを監視
    ↓
必要なデータを取得
    ↓
イベント発生
    ↓
JavaScriptへ通知
    ↓
画面更新
```

という構成が自然です。

---

# 33. 結論

今回のアプリでは、PLC監視をJavaScriptの `setInterval()` へ移す必要はありません。

現在の、

```python
while not self.stop_event.is_set():
```

によるPython主体のPLC監視を維持します。

そしてChart.js追加時には、

```text
Python監視
    ↓
PLCデータ受信
    ↓
Python → JavaScript Push
    ↓
Chart.js即更新
```

という方式へ拡張します。

この構成には、

- PLC監視とGUIを分離できる
- 不要な定期問い合わせを減らせる
- 表示タイムラグを小さくできる
- PythonとJavaScriptの責務が明確になる
- PLCアラームや進捗表示などにも応用できる
- pywebviewの双方向通信を活用できる

という利点があります。

---

# 34. 今後の設計方針として覚えておきたい一文

```text
Pythonで「仕事」をする。
JavaScriptで「見せる」。

Python側でイベントが発生したら、
JavaScriptへPushして画面を更新する。
```

pywebviewアプリでは、この考え方を基本にすると、

```text
Pythonの強み
+
JavaScript / HTML / Chart.jsの強み
```

を組み合わせた非常に柔軟なアプリを作ることができます。

今回検討した、

> **Python監視 → JavaScriptへPush**

は、今後のpywebviewアプリを設計するうえで重要な基本パターンの一つとして覚えておく価値があります。
