# pywebview版 モータ電流値受信アプリ 解説書

## 1. はじめに

このアプリは、キーエンスPLCからモータ電流値を受信し、CSVファイルへ保存するアプリです。

対象モータは3台あり、PCはPLCの要求デバイスを一定周期で監視します。要求がONになったモータについて、PLCから1000点の電流値を読み込み、モータ別のフォルダへCSVファイルとして保存します。保存完了後はPLCの完了デバイスをONします。

GUIには **pywebview**
を使用しており、画面には次の操作だけを用意しています。

-   監視開始
-   監視停止
-   ウィンドウ右上の「×」によるアプリ終了

このアプリを理解するうえで最も重要なのは、単に「PLCと通信するプログラム」と見るのではなく、次の3つの役割に分けて考えることです。

``` text
┌─────────────────────────────┐
│  GUI                         │
│  pywebview + HTML + JS       │
│                             │
│  [監視開始]   [監視停止]     │
└──────────────┬──────────────┘
               │
               │ pywebview.api
               ▼
┌─────────────────────────────┐
│  AppApi                     │
│  GUIとPython処理の橋渡し      │
└──────────────┬──────────────┘
               │
               │ 監視開始
               ▼
┌─────────────────────────────┐
│  MotorReceiver              │
│  PLC要求監視                 │
│                             │
│  plc-monitor スレッド        │
└──────────────┬──────────────┘
               │ submit()
               ▼
┌─────────────────────────────┐
│  ThreadPoolExecutor         │
│                             │
│  worker ── motor1受信        │
│  worker ── motor2受信        │
│  worker ── motor3受信        │
└─────────────────────────────┘
```

この「GUI」「PLC監視」「実際のデータ受信」を分離していることが、本アプリの設計上の大きな特徴です。

------------------------------------------------------------------------

## 2. ファイル構成

アプリの主要ファイルは次の4つです。

``` text
motor_receiver_gui/
│
├─ app.py
├─ index.html
├─ style.css
├─ script.js
│
├─ common_lib_mw/
│   └─ kv_com.py
│
└─ data/
    ├─ motor1/
    ├─ motor2/
    └─ motor3/
```

### app.py

Python側の本体です。

主な役割は次のとおりです。

-   PLC通信条件の設定
-   モータごとの設定管理
-   PLC要求監視
-   ThreadPoolExecutorによるデータ受信
-   CSV保存
-   pywebviewとJavaScriptの橋渡し
-   アプリ終了処理

### index.html

GUIの画面構造を定義します。

表示するものは非常にシンプルです。

-   アプリ名
-   PLC IPアドレス
-   現在状態
-   監視開始ボタン
-   監視停止ボタン

### style.css

画面の見た目を担当します。

今回の方針は「CSSを極力シンプルにする」なので、余計な装飾は行わず、文字サイズ、余白、ボタンサイズ程度しか設定していません。

### script.js

HTMLのボタン操作とPython側の `AppApi` をつなぎます。

例えば「監視開始」ボタンを押すと、

``` javascript
pywebview.api.start_monitoring()
```

が実行され、Python側の `AppApi.start_monitoring()` が呼び出されます。

------------------------------------------------------------------------

## 3. app.py全体の構成

`app.py` は大きく次のように分けて考えると理解しやすくなります。

``` text
app.py
│
├─ import
│
├─ 設定
│
├─ MotorConfig
│
├─ MOTOR_CONFIGS
│
├─ MotorReceiver
│   ├─ PLC監視
│   ├─ 要求判定
│   ├─ ThreadPoolExecutor
│   └─ データ受信
│
├─ AppApi
│   ├─ 監視開始
│   ├─ 監視停止
│   ├─ 状態取得
│   └─ アプリ終了
│
├─ save_csv()
├─ current_time()
│
└─ main()
    └─ pywebview起動
```

`MotorReceiver` と `AppApi` の役割を混同しないことが重要です。

-   `MotorReceiver` = PLC側の仕事
-   `AppApi` = GUIからPLC側を操作する仕事

というイメージです。

------------------------------------------------------------------------

# 4. MotorConfig ― モータごとの設定

``` python
@dataclass(frozen=True)
class MotorConfig:
    name: str
    request_device: str
    completion_device: str
    data_start_device: str
    output_directory: Path
```

3台のモータでは、処理そのものはほぼ同じです。

違うのは、

-   モータ名
-   要求デバイス
-   完了デバイス
-   データ先頭デバイス
-   CSV保存先

だけです。

そこで、これらを `MotorConfig` にまとめています。

例えばmotor1は、

``` python
MotorConfig(
    name="motor1",
    request_device="B100",
    completion_device="B200",
    data_start_device="EM30000",
    output_directory=DATA_DIRECTORY / "motor1",
)
```

となっています。

これにより、motor1用、motor2用、motor3用の処理を別々に書く必要がありません。

同じ処理へ `config` を渡すだけで済みます。

------------------------------------------------------------------------

# 5. MotorReceiver ― PLC処理の中心

`MotorReceiver` は、このアプリのPLC処理を担当する中心クラスです。

``` python
class MotorReceiver:
```

主な仕事は次の3つです。

1.  PLCの要求デバイスを監視する
2.  要求があれば受信処理をThreadPoolExecutorへ投入する
3.  モータ電流値を受信してCSVへ保存する

------------------------------------------------------------------------

## 6. ThreadPoolExecutorの役割

コンストラクタでは、次のThreadPoolExecutorを作成しています。

``` python
self.executor = ThreadPoolExecutor(
    max_workers=len(MOTOR_CONFIGS),
    thread_name_prefix="motor-receiver",
)
```

現在はモータが3台なので、

``` python
len(MOTOR_CONFIGS)
```

は3です。

したがって最大3個のワーカースレッドを使用できます。

重要なのは、このThreadPoolExecutorが
**PLC監視そのものを担当しているわけではない** ことです。

担当するのは、

``` python
_receive_and_save()
```

です。

つまり、

``` text
PLC監視
   │
   ├─ motor1要求ON ──→ workerへ投入
   │
   ├─ motor2要求ON ──→ workerへ投入
   │
   └─ motor3要求ON ──→ workerへ投入
```

という関係です。

3台がほぼ同時に要求を出しても、それぞれの受信処理を並行して進めることができます。

------------------------------------------------------------------------

# 7. Event ― 監視ループを停止する仕組み

GUI版で新しく重要になったのが、

``` python
self.stop_event = threading.Event()
```

です。

以前のコンソール版では、

``` python
while True:
```

によってPLC監視を永久に続けていました。

しかしGUI版では、

-   監視開始
-   監視停止

をボタンで切り替える必要があります。

そのため、

``` python
while not self.stop_event.is_set():
```

としています。

Eventの状態は概念的には次のように考えられます。

``` text
clear()
  ↓
Event = OFF
  ↓
監視を続ける


set()
  ↓
Event = ON
  ↓
監視を終了する
```

監視開始時には、

``` python
self.receiver.stop_event.clear()
```

監視停止時には、

``` python
self.receiver.stop()
```

が実行され、その中で、

``` python
self.stop_event.set()
```

が実行されます。

------------------------------------------------------------------------

# 8. run() ― PLC要求監視ループ

`run()` はPLC監視の本体です。

概念的には、

``` text
run()
 │
 ├─ 保存フォルダ作成
 ├─ 起動情報表示
 │
 └─ Eventがsetされるまで繰り返す
       │
       ├─ motor1確認
       ├─ motor2確認
       ├─ motor3確認
       │
       └─ 0.1秒待機
```

となっています。

実際のループは、

``` python
while not self.stop_event.is_set():
```

です。

さらに各モータを確認している途中でも、

``` python
if self.stop_event.is_set():
    break
```

を確認しています。

そのため、「監視停止」が押されたあとに不要な新規要求確認を続けにくい構造になっています。

------------------------------------------------------------------------

## 9. sleep()ではなくEvent.wait()を使う理由

監視周期は0.1秒です。

``` python
POLL_INTERVAL_SECONDS = 0.1
```

以前であれば、

``` python
time.sleep(POLL_INTERVAL_SECONDS)
```

でも待機できます。

GUI版では、

``` python
self.stop_event.wait(POLL_INTERVAL_SECONDS)
```

を使用しています。

通常時は最大0.1秒待機するという点では似ています。

しかしEventが `set()` されると、待機時間の途中でも `wait()`
が解除されます。

したがって、

``` text
sleep()
    → 時間が来るまで基本的に待つ

Event.wait()
    → 時間を待つ
    → ただしEventがsetされたら早く戻れる
```

という違いがあります。

停止制御を行うアプリでは `Event.wait()` が非常に相性のよい方法です。

------------------------------------------------------------------------

# 10. \_check_request() ― PLC要求を確認する

`_check_request()` はモータ1台分の要求状態を確認します。

例えばmotor1ならB100を読みます。

``` python
response = kv_com.read_device_b(
    self.plc_ip_address,
    config.request_device,
)
```

PLCから、

``` text
"1" → ON
"0" → OFF
```

が返ってくることを前提にしています。

それ以外なら異常として、

``` python
raise RuntimeError(...)
```

します。

------------------------------------------------------------------------

# 11. request_latched ― ONの連続受付を防ぐ

PLC要求がONになったあと、すぐOFFになるとは限りません。

例えば、

``` text
監視1回目    ON
監視2回目    ON
監視3回目    ON
監視4回目    ON
```

だった場合、何も対策しなければ同じ要求を4回受け付ける可能性があります。

そこで、

``` python
self.request_latched
```

を使用しています。

考え方は、

``` text
要求OFF
   ↓
latch = False

要求ON
   ↓
latchがFalseなら受付
   ↓
latch = True

要求ON継続
   ↓
latchがTrueなので受付しない

要求OFF
   ↓
latch = False
   ↓
次の要求を受付可能
```

です。

これはPLCでいう立上り検出に近い考え方です。

------------------------------------------------------------------------

# 12. is_receiving ― 同じモータの二重受信を防ぐ

もう一つ、

``` python
self.is_receiving
```

があります。

これは、

> そのモータの受信処理が現在実行中か

を管理します。

例えばmotor1の受信中に、何らかの条件で再度要求受付の条件が成立しても、

``` python
if self.is_receiving[config.name]:
    return
```

によって二重実行を防ぎます。

`request_latched` と `is_receiving` は似ていますが、目的が違います。

  状態                目的
  ------------------- --------------------------------------
  `request_latched`   同じON信号を何度も受付しない
  `is_receiving`      同じモータの受信処理を同時実行しない

------------------------------------------------------------------------

# 13. state_lock ― 共有状態を安全に変更する

`request_latched` と `is_receiving`
は複数スレッドから参照・変更される可能性があります。

そこで、

``` python
self.state_lock = threading.Lock()
```

を使用しています。

例えば、

``` python
with self.state_lock:
    ...
```

の中では、同時に別スレッドが同じ保護区間へ入ることができません。

このアプリでは特に、

``` python
self.is_receiving[config.name]
```

を、

-   PLC監視スレッド
-   ThreadPoolExecutorのワーカースレッド

の両方から扱います。

そのためLockによる保護が重要になります。

------------------------------------------------------------------------

# 14. submit() ― 受信処理をスレッドプールへ渡す

要求受付が成立すると、

``` python
self.executor.submit(
    self._receive_and_save,
    config,
)
```

を実行します。

これは、

> `_receive_and_save(config)`
> をThreadPoolExecutorのワーカーで実行してください

という依頼です。

ここで重要なのは、

``` python
self._receive_and_save(config)
```

と直接呼んでいないことです。

直接呼ぶとPLC監視スレッド自身が1000点受信を行うため、その間ほかの要求監視が止まってしまいます。

`submit()` することで、

``` text
PLC監視スレッド
       │
       ├─ 要求を発見
       │
       ├─ submit()
       │       │
       │       └─ workerが受信処理
       │
       └─ PLC監視へ戻る
```

という動作になります。

------------------------------------------------------------------------

# 15. \_receive_and_save() ― 実際のデータ受信

このメソッドが、モータ電流値受信の実処理です。

流れは、

``` text
データ受信開始
    ↓
PLCから1000点読み込み
    ↓
CSV保存
    ↓
PLC完了デバイスON
    ↓
完了メッセージ
```

です。

PLCデータ読み込みには、

``` python
kv_com.read_devices_d(...)
```

を使用しています。

読み込んだ値は、

``` python
values
```

へ格納されます。

その後、

``` python
csv_path = save_csv(config, values)
```

でCSV保存します。

保存後、

``` python
kv_com.write_device_b(...)
```

によって完了通知をPLCへ返します。

------------------------------------------------------------------------

# 16. finallyが重要な理由

受信処理の最後には、

``` python
finally:
    with self.state_lock:
        self.is_receiving[config.name] = False
```

があります。

`finally` は、正常終了でも例外発生でも実行されます。

例えば通信エラーが起きても、

``` text
is_receiving = True
       ↓
通信エラー
       ↓
except
       ↓
finally
       ↓
is_receiving = False
```

となります。

これがないと、エラー発生後も永久に「受信中」と判断され、次の要求を受け付けられなくなる可能性があります。

------------------------------------------------------------------------

# 17. AppApi ― GUIとPythonをつなぐクラス

GUI化で最も新しい部分が `AppApi` です。

``` python
class AppApi:
```

このクラスはPLC処理そのものを行いません。

役割は、

> JavaScriptからの操作を受け取り、MotorReceiverを操作する

ことです。

関係は、

``` text
HTMLボタン
   ↓
JavaScript
   ↓
pywebview.api
   ↓
AppApi
   ↓
MotorReceiver
```

です。

`AppApi` には主に、

-   `start_monitoring()`
-   `stop_monitoring()`
-   `get_status()`
-   `shutdown()`

があります。

------------------------------------------------------------------------

# 18. PLC監視専用スレッド

ここはThreadPoolExecutorと混同しやすい重要ポイントです。

`run()` は監視中ずっと終了しません。

もしGUIを動かしているスレッドで、

``` python
receiver.run()
```

を直接実行すると、GUI側の処理を妨げます。

そこで、

``` python
self.monitor_thread = threading.Thread(
    target=self.receiver.run,
    name="plc-monitor",
    daemon=False,
)
```

として、PLC監視専用スレッドを1本作っています。

このアプリには大きく分けて、

``` text
① GUI
② PLC監視スレッド
③ ThreadPoolExecutorのワーカー
```

が存在します。

ここは本アプリを理解するうえで最重要ポイントの一つです。

------------------------------------------------------------------------

# 19. start_monitoring() ― 監視開始

「監視開始」ボタンから呼ばれるPython側メソッドです。

まず、

``` python
self.monitor_thread.is_alive()
```

で、すでに監視中でないか確認します。

監視中なら新しいスレッドを作りません。

次に、

``` python
self.receiver.stop_event.clear()
```

で停止要求を解除します。

そして、

``` python
self.monitor_thread = threading.Thread(...)
self.monitor_thread.start()
```

によって `MotorReceiver.run()` を別スレッドで開始します。

つまり、

``` text
監視開始ボタン
    ↓
start_monitoring()
    ↓
Event.clear()
    ↓
plc-monitorスレッド生成
    ↓
run()開始
```

です。

------------------------------------------------------------------------

# 20. stop_monitoring() ― 監視停止

「監視停止」ボタンから呼ばれます。

``` python
self.receiver.stop()
```

によってEventをsetします。

すると `run()` の、

``` python
while not self.stop_event.is_set():
```

が終了します。

その後、

``` python
monitor_thread.join()
```

によって、監視スレッドが実際に終了するまで待ちます。

ここで大事なのは、**ThreadPoolExecutorそのものはshutdownしていない**ことです。

したがって監視停止後も、もう一度「監視開始」を押せます。

------------------------------------------------------------------------

# 21. 「監視停止」と「アプリ終了」は別物

これは今回のGUI化で非常に重要な設計です。

## 監視停止

``` text
監視停止
   ↓
stop_event.set()
   ↓
run()終了
   ↓
GUIは残る
   ↓
ThreadPoolExecutorも残る
   ↓
再度「監視開始」可能
```

## アプリ終了

``` text
ウィンドウの×
   ↓
shutdown()
   ↓
PLC監視停止
   ↓
監視スレッド終了待ち
   ↓
ThreadPoolExecutor.shutdown(wait=True)
   ↓
アプリ終了
```

この2つを明確に分けています。

------------------------------------------------------------------------

# 22. 実行中の受信処理は監視停止で中断しない

例えばmotor1の受信中に「監視停止」を押したとします。

``` text
motor1要求ON
    ↓
ThreadPoolExecutorで受信開始
    ↓
1000点受信中
    ↓
「監視停止」
```

この場合、停止するのは **新しいPLC要求を探す監視ループ** です。

すでに開始した、

``` python
_receive_and_save()
```

は最後まで動作します。

つまり、

``` text
1000点受信
   ↓
CSV保存
   ↓
PLC完了通知
```

まで実行されます。

これはPLCとの一連の通信処理を途中で壊さないために重要です。

------------------------------------------------------------------------

# 23. get_status() ― GUIへ状態を返す

JavaScript側は、現在の監視状態を知る必要があります。

そこで、

``` python
get_status()
```

を用意しています。

監視スレッドが生きていれば、

``` python
{
    "status": "running",
    "message": "監視中",
}
```

を返します。

停止していれば、

``` python
{
    "status": "stopped",
    "message": "停止中",
}
```

を返します。

Pythonの辞書がpywebviewを通してJavaScript側へ渡され、JavaScriptでは、

``` javascript
result.status
result.message
```

として利用できます。

------------------------------------------------------------------------

# 24. shutdown() ― アプリ終了処理

ウィンドウ右上の「×」を押した場合は、

``` python
shutdown()
```

を実行します。

主な流れは、

``` text
終了開始
   ↓
新しい操作を受け付けない
   ↓
PLC監視停止
   ↓
monitor_thread.join()
   ↓
executor.shutdown(wait=True)
   ↓
終了
```

です。

特に、

``` python
self.receiver.executor.shutdown(wait=True)
```

が重要です。

`wait=True`
なので、ThreadPoolExecutorで実行中のデータ受信があれば、その処理が終了するまで待ちます。

つまり、×を押したからといって受信処理を乱暴に途中終了する設計にはしていません。

------------------------------------------------------------------------

# 25. is_shutting_down ― 終了処理の状態

`AppApi` には、

``` python
self.is_shutting_down = False
```

があります。

終了処理を開始すると、

``` python
self.is_shutting_down = True
```

になります。

これにより終了処理中に監視開始などを行わないようにしています。

また、`shutdown()` が重複して呼ばれた場合にも、

``` python
if self.is_shutting_down:
    return
```

で二重終了処理を防ぎます。

------------------------------------------------------------------------

# 26. AppApi側のLock

`AppApi` にも、

``` python
self.lock = threading.Lock()
```

があります。

これは `MotorReceiver.state_lock` とは別物です。

### MotorReceiver.state_lock

主に、

-   `request_latched`
-   `is_receiving`

を保護します。

### AppApi.lock

主に、

-   `monitor_thread`
-   `is_shutting_down`

などGUI制御側の状態を保護します。

同じLockでも守っている対象が違います。

------------------------------------------------------------------------

# 27. save_csv()

`save_csv()` はPLCから受信したデータをCSVへ保存します。

まず、

``` python
if len(values) != DATA_POINT_COUNT:
```

で1000点受信できたか確認します。

ファイル名は、

``` text
motor1_YYYYMMDD_HHMMSS.csv
```

の形式です。

同じ秒に複数ファイルが発生した場合には、

``` text
motor1_20260811_011704.csv
motor1_20260811_011704_001.csv
motor1_20260811_011704_002.csv
```

のように連番を付け、既存ファイルを上書きしないようにしています。

CSV内容は、

``` text
point_no,current_value
1,xxxx
2,xxxx
3,xxxx
...
1000,xxxx
```

という形式です。

------------------------------------------------------------------------

# 28. main() ― アプリの入口

アプリは、

``` python
if __name__ == "__main__":
    main()
```

から開始します。

`main()` では最初に、

``` python
receiver = MotorReceiver(PLC_IP_ADDRESS)
api = AppApi(receiver)
```

を作ります。

関係は、

``` text
MotorReceiver
      ↑
      │ 操作する
      │
   AppApi
```

です。

次に、

``` python
window = webview.create_window(...)
```

でGUIウィンドウを作ります。

ここで、

``` python
js_api=api
```

としていることが重要です。

これによってJavaScriptから、

``` javascript
pywebview.api.start_monitoring()
```

のように `AppApi` の公開メソッドを呼べるようになります。

------------------------------------------------------------------------

# 29. ×ボタンとshutdown()の接続

次のコードがあります。

``` python
window.events.closed += api.shutdown
```

これは、

> pywebviewのウィンドウが閉じられたら `api.shutdown()` を実行する

という意味です。

そのため、ユーザーは特別な「終了」ボタンを押す必要がありません。

通常のWindowsアプリと同じように、

``` text
右上の「×」
```

で終了できます。

------------------------------------------------------------------------

# 30. webview.start()

最後に、

``` python
webview.start()
```

でpywebviewのGUIを開始します。

ここからGUIイベントループが動作します。

そのためPLC監視の `run()` をメインスレッドで直接実行せず、別の
`plc-monitor` スレッドへ分離しているわけです。

------------------------------------------------------------------------

# 31. index.htmlの役割

HTMLは表示する部品だけを定義しています。

特に重要なのは、

``` html
<strong id="status">停止中</strong>
```

です。

JavaScriptがこの要素を取得して、

``` javascript
statusElement.textContent = result.message;
```

と書き換えます。

ボタンには、

``` html
<button id="start-button">
<button id="stop-button">
```

というIDを付けています。

JavaScriptはこのIDを使ってボタンを取得します。

------------------------------------------------------------------------

# 32. script.jsの役割

最初にHTML要素を取得します。

``` javascript
const statusElement = document.getElementById("status");
const startButton = document.getElementById("start-button");
const stopButton = document.getElementById("stop-button");
```

これによってJavaScriptから、

-   状態表示
-   監視開始ボタン
-   監視停止ボタン

を操作できます。

------------------------------------------------------------------------

# 33. JavaScript → Pythonの呼び出し

監視開始では、

``` javascript
const result = await pywebview.api.start_monitoring();
```

を実行します。

流れは、

``` text
JavaScript
startMonitoring()
      ↓
pywebview.api.start_monitoring()
      ↓
Python
AppApi.start_monitoring()
      ↓
結果をdictで返す
      ↓
JavaScript
result
```

です。

PythonとJavaScriptが直接同じ言語として動いているわけではありません。

**pywebviewが橋渡しをしています。**

------------------------------------------------------------------------

# 34. updateStatus()

Pythonから返された結果を画面へ反映する関数です。

``` javascript
function updateStatus(result) {
    statusElement.textContent = result.message;

    const isRunning = result.status === "running";

    startButton.disabled = isRunning;
    stopButton.disabled = !isRunning;
}
```

監視中なら、

``` text
監視開始 → disabled
監視停止 → enabled
```

停止中なら、

``` text
監視開始 → enabled
監視停止 → disabled
```

となります。

これによりユーザーが不自然な操作をしにくくなっています。

------------------------------------------------------------------------

# 35. pywebviewready

起動時には、

``` javascript
window.addEventListener("pywebviewready", async () => {
    const result = await pywebview.api.get_status();
    updateStatus(result);
});
```

があります。

HTMLが表示されたからといって、必ずしもその瞬間に `pywebview.api`
が使用可能とは限りません。

そこでpywebview側のAPIが準備できたことを示す `pywebviewready`
を待ってから、

``` javascript
pywebview.api.get_status()
```

を呼んでいます。

------------------------------------------------------------------------

# 36. style.css

CSSは意図的に非常に簡単です。

``` css
body
h1
button
#status
```

しか設定していません。

今回のアプリでは、見た目を凝ることよりも、

-   HTMLが読みやすい
-   JavaScriptが読みやすい
-   Pythonとの関係が追いやすい
-   メンテナンスしやすい

ことを優先しています。

この程度のGUIなら、CSSを複雑化しない方がアプリ全体を理解しやすくなります。

------------------------------------------------------------------------

# 37. アプリ起動から監視開始まで

全体の流れを改めて追います。

``` text
app.py実行
   ↓
main()
   ↓
MotorReceiver生成
   ↓
AppApi生成
   ↓
webview.create_window()
   ↓
webview.start()
   ↓
GUI表示
   ↓
pywebviewready
   ↓
get_status()
   ↓
「停止中」と表示
```

この時点ではPLC監視スレッドはまだ動いていません。

------------------------------------------------------------------------

# 38. 「監視開始」を押したとき

``` text
ユーザー
   ↓
「監視開始」
   ↓
JavaScript
startMonitoring()
   ↓
pywebview.api.start_monitoring()
   ↓
Python
AppApi.start_monitoring()
   ↓
stop_event.clear()
   ↓
plc-monitorスレッド生成
   ↓
MotorReceiver.run()
   ↓
PLC監視開始
   ↓
Pythonから
status="running"
message="監視中"
   ↓
JavaScript
updateStatus()
   ↓
画面「監視中」
```

------------------------------------------------------------------------

# 39. PLC要求がONになったとき

例えばmotor1のB100がONになった場合です。

``` text
run()
   ↓
_check_request(motor1)
   ↓
B100読み込み
   ↓
ON
   ↓
request_latched確認
   ↓
is_receiving確認
   ↓
受付可能
   ↓
request_latched = True
is_receiving = True
   ↓
executor.submit()
   ↓
workerスレッド
   ↓
_receive_and_save(motor1)
   ↓
EM30000から1000点受信
   ↓
CSV保存
   ↓
B200 ON
   ↓
is_receiving = False
```

一方、PLC監視スレッドは受信処理そのものを待たず、ほかのモータの要求監視を続けられます。

------------------------------------------------------------------------

# 40. 「監視停止」を押したとき

``` text
ユーザー
   ↓
「監視停止」
   ↓
JavaScript
stopMonitoring()
   ↓
AppApi.stop_monitoring()
   ↓
MotorReceiver.stop()
   ↓
stop_event.set()
   ↓
run()のwhile終了
   ↓
monitor_thread.join()
   ↓
監視スレッド終了
   ↓
画面「停止中」
```

ただしThreadPoolExecutorで既に開始済みの受信処理は、そのまま最後まで実行します。

------------------------------------------------------------------------

# 41. 再度「監視開始」を押したとき

ThreadPoolExecutorは監視停止時にはshutdownしていません。

そのため、

``` text
stop_event.clear()
   ↓
新しいplc-monitorスレッド生成
   ↓
run()再開
```

が可能です。

つまり、

``` text
開始 → 停止 → 開始 → 停止
```

を繰り返せます。

------------------------------------------------------------------------

# 42. 「×」を押したとき

``` text
ウィンドウ「×」
   ↓
window.events.closed
   ↓
AppApi.shutdown()
   ↓
is_shutting_down = True
   ↓
stop_event.set()
   ↓
PLC監視終了待ち
   ↓
executor.shutdown(wait=True)
   ↓
実行中の受信処理終了待ち
   ↓
アプリ完全終了
```

ここで初めてThreadPoolExecutorをshutdownします。

したがって、

> 監視停止 = 一時停止可能な状態

> × = アプリそのものを完全終了

という違いがあります。

------------------------------------------------------------------------

# 43. このアプリに存在するスレッドを整理する

本アプリでは「スレッド」という言葉が複数の場所に登場します。

ここを整理すると全体像がかなり見やすくなります。

``` text
┌──────────────────────────────┐
│ メイン側                      │
│ pywebview GUI                │
└──────────────────────────────┘

            │
            │ 監視開始
            ▼

┌──────────────────────────────┐
│ plc-monitor                  │
│ threading.Thread             │
│                              │
│ MotorReceiver.run()          │
│ PLC要求監視                   │
└──────────────┬───────────────┘
               │
               │ submit()
               ▼
┌──────────────────────────────┐
│ ThreadPoolExecutor           │
│                              │
│ worker 1                     │
│ worker 2                     │
│ worker 3                     │
│                              │
│ _receive_and_save()          │
└──────────────────────────────┘
```

### なぜ2種類使うのか

`plc-monitor` は、

> 監視ループを1本、長時間動かす

という明確な専用処理です。

ThreadPoolExecutorは、

> 要求が来たときだけ発生する受信処理を最大3件並行実行する

ための仕組みです。

目的が違うので、両方を使っています。

------------------------------------------------------------------------

# 44. ThreadとThreadPoolExecutorの役割分担

  処理               使用する仕組み         理由
  ------------------ ---------------------- --------------------------
  GUI                pywebview側            GUIイベント処理
  PLC要求監視        `threading.Thread`     1本の専用ループ
  モータデータ受信   `ThreadPoolExecutor`   複数モータを並行処理
  停止通知           `threading.Event`      スレッドへ安全に停止要求
  状態保護           `threading.Lock`       共有データの競合防止

この表は本アプリの並行処理設計を理解するうえで重要です。

------------------------------------------------------------------------

# 45. このアプリで特に理解しておきたい5項目

全部を再入力する前に、最低限次の5点を理解しておくとコードがかなり読みやすくなります。

## ① pywebviewは画面とPythonをつなぐ

``` text
HTML / JavaScript
       ↓
pywebview.api
       ↓
AppApi
```

## ② run()は専用スレッドで動く

GUIを止めないため、

``` python
threading.Thread(target=self.receiver.run)
```

で実行します。

## ③ Eventでrun()を停止する

``` python
clear() → 監視可能
set()   → 停止要求
```

です。

## ④ データ受信はThreadPoolExecutor

``` python
executor.submit(...)
```

で受信処理をワーカーへ渡します。

## ⑤ 監視停止とアプリ終了は違う

``` text
監視停止
→ run()だけ停止

アプリ終了
→ run()停止
→ executorもshutdown
→ 完全終了
```

です。

------------------------------------------------------------------------

# 46. 再入力するときのおすすめ順序

このアプリを学習目的で一から入力する場合、完成コードを上から機械的にコピーするより、役割単位で組み立てると理解しやすくなります。

### 第1段階：PLC処理

まず従来部分を作ります。

``` text
MotorConfig
MOTOR_CONFIGS
MotorReceiver
save_csv()
current_time()
```

この段階ではGUIを意識しすぎなくて構いません。

### 第2段階：停止可能にする

次に、

``` python
self.stop_event = threading.Event()
```

を追加し、

``` python
while not self.stop_event.is_set():
```

へ変更します。

ここで「Eventによってrun()を外部から止められる」ことを確認します。

### 第3段階：AppApi

次に、

``` python
class AppApi:
```

を作ります。

まずは、

``` text
start_monitoring()
stop_monitoring()
get_status()
shutdown()
```

の役割を理解します。

### 第4段階：pywebview

`main()` に、

``` python
webview.create_window(...)
webview.start()
```

を追加します。

ここで、

``` python
js_api=api
```

がPythonとJavaScriptをつなぐ重要部分です。

### 第5段階：HTML

画面部品だけを作ります。

### 第6段階：JavaScript

最後に、

``` javascript
pywebview.api.start_monitoring()
pywebview.api.stop_monitoring()
```

を接続します。

CSSは最後で構いません。

------------------------------------------------------------------------

# 47. 学習時に迷いやすいポイント

## 「ThreadPoolExecutorがあるのに、なぜthreading.Threadも使うのか？」

目的が違うからです。

``` text
threading.Thread
→ PLC監視専用

ThreadPoolExecutor
→ モータデータ受信用
```

です。

## 「Eventはスレッドを強制停止するのか？」

しません。

Eventは、

> 停止してほしい

という状態を伝えるだけです。

`run()` 自身が、

``` python
while not self.stop_event.is_set():
```

を確認して、自分でループを終了します。

これは協調的な停止です。

## 「監視停止したらexecutorもshutdownすべきでは？」

しません。

shutdownすると、そのThreadPoolExecutorへ再度 `submit()`
できなくなるためです。

再度「監視開始」できるように、executorのshutdownはアプリ終了時だけ行います。

## 「join()は停止命令か？」

違います。

`join()` は、

> そのスレッドが終了するまで待つ

処理です。

停止要求は `Event.set()` が担当し、終了待ちは `join()` が担当します。

------------------------------------------------------------------------

# 48. 設計思想を一言でまとめる

このアプリの構造は、

> **GUIは操作だけを担当し、PLC監視とデータ受信はGUIから分離してバックグラウンドで実行する**

とまとめられます。

さらに、

``` text
GUI操作
   ↓
AppApi
   ↓
監視スレッド
   ↓
ThreadPoolExecutor
   ↓
PLCデータ受信
```

という階層にすることで、それぞれの責任を分離しています。

この分離によって、

-   GUIが固まりにくい
-   PLC監視を開始・停止できる
-   複数モータを並行受信できる
-   同じモータの二重受付を防げる
-   実行中の受信を安全に完了できる
-   ×ボタンで安全に終了できる

という構成になっています。

------------------------------------------------------------------------

# 49. 最後に

このアプリは小規模ですが、PythonでGUI付きの実用アプリを作るうえで重要な要素がかなり含まれています。

特に、

-   pywebview
-   HTML / CSS / JavaScript
-   PythonとJavaScriptの連携
-   `threading.Thread`
-   `ThreadPoolExecutor`
-   `threading.Event`
-   `threading.Lock`
-   `join()`
-   `shutdown(wait=True)`
-   dataclass
-   PLC通信
-   CSV保存

を一つのアプリの中で実際に組み合わせています。

コードを一から再入力するときは、すべてを一度に理解しようとするより、

``` text
① GUI
② AppApi
③ PLC監視
④ Event
⑤ ThreadPoolExecutor
⑥ 終了処理
```

という役割ごとに追っていくのがおすすめです。

そして最も重要な全体像は、次の図です。

``` text
                 ┌────────────────────┐
                 │      pywebview     │
                 │   HTML / JS GUI    │
                 └─────────┬──────────┘
                           │
                           │ pywebview.api
                           ▼
                 ┌────────────────────┐
                 │       AppApi       │
                 │ GUIとPythonの橋渡し │
                 └─────────┬──────────┘
                           │
                    監視開始│監視停止
                           ▼
                 ┌────────────────────┐
                 │   plc-monitor      │
                 │ threading.Thread   │
                 │                    │
                 │ MotorReceiver.run  │
                 └─────────┬──────────┘
                           │
                       submit()
                           │
                           ▼
              ┌──────────────────────────┐
              │    ThreadPoolExecutor    │
              │                          │
              │ worker → motor1          │
              │ worker → motor2          │
              │ worker → motor3          │
              └────────────┬─────────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │        PLC         │
                 │  電流値1000点受信   │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │      CSV保存       │
                 │ data/motor1～3/    │
                 └────────────────────┘
```

この図を頭に置いた状態でコードを読むと、「今書いているコードがアプリ全体のどこを担当しているのか」を見失いにくくなります。
