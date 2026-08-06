# MotorReceiverクラス完全解説
## PLC要求監視・マルチスレッド受信・CSV保存の設計を理解する

## 1. はじめに

`MotorReceiver` は、PLCからの受信要求を常時監視し、要求が発生したモータの電流値を別スレッドで受信・保存する、アプリの中核クラスです。

主な役割は次のとおりです。

- PLC要求デバイスの常時監視
- モータごとの受信要求の判定
- `ThreadPoolExecutor` を使った並行処理
- PLCからの電流値受信
- CSVファイルへの保存
- PLCへの受信完了通知
- 同じ要求の重複受付防止
- 同じモータの受信処理の二重実行防止
- エラー処理
- プログラム終了時の安全なスレッド停止

---

## 2. クラス全体の役割

```python
class MotorReceiver:
    """PLC要求監視とモータ電流データ受信を管理する。"""
```

`MotorReceiver` は、設定だけを保持するクラスではありません。

`MotorConfig` が「モータ1台分の設定」を表すのに対し、`MotorReceiver` は、その設定を使って実際にPLC監視・データ受信・保存処理を実行します。

```text
MotorConfig
    モータごとの設定を保持する

MotorReceiver
    その設定を使って監視・受信・保存を実行する
```

全体像は次のようになります。

```text
MotorReceiver
├─ PLC接続先を保持する
├─ スレッドプールを管理する
├─ 要求受付状態を管理する
├─ 実行中タスクを管理する
├─ PLC要求信号を監視する
├─ データ受信処理を別スレッドへ登録する
├─ CSVへ保存する
├─ PLCへ完了通知を返す
└─ 終了時にスレッドを安全に停止する
```

---

## 3. `__init__()` メソッド

```python
def __init__(self, plc_ip_address: str) -> None:
```

`__init__()` は、`MotorReceiver` オブジェクトを作成したときに自動で呼ばれる初期化メソッドです。

```python
receiver = MotorReceiver("192.168.8.1")
```

このとき、PLCのIPアドレス、スレッドプール、状態管理用辞書、ロックなどが準備されます。

### 引数

```python
plc_ip_address: str
```

PLCのIPアドレスを文字列として受け取ります。

### 戻り値

```python
-> None
```

`__init__()` は初期化用メソッドなので、通常の戻り値を返しません。

---

## 4. `self` の意味

`self` は、現在操作している `MotorReceiver` オブジェクト自身を表します。

```python
receiver = MotorReceiver("192.168.8.1")
```

この場合、`__init__()` 内の `self` は `receiver` を指します。

```python
self.plc_ip_address
```

は、外部から見れば次と同じ属性です。

```python
receiver.plc_ip_address
```

---

## 5. PLC IPアドレスの保存

```python
self.plc_ip_address = plc_ip_address
```

右辺の `plc_ip_address` は、`__init__()` の引数です。

左辺の `self.plc_ip_address` は、作成したオブジェクトが保持する属性です。

```python
receiver = MotorReceiver("192.168.8.1")
print(receiver.plc_ip_address)
```

結果は次のとおりです。

```text
192.168.8.1
```

この値は、他のメソッドでも `self.plc_ip_address` として利用できます。

---

## 6. `ThreadPoolExecutor` の作成

```python
self.executor = ThreadPoolExecutor(
    max_workers=len(MOTOR_CONFIGS),
    thread_name_prefix="motor-receiver",
)
```

ここでは、複数の受信処理を並行して実行するためのスレッドプールを作成しています。

### `ThreadPoolExecutor` とは

`ThreadPoolExecutor` は、一定数のワーカースレッドを管理し、登録された処理を別スレッドで実行する仕組みです。

毎回 `threading.Thread` を自分で生成・開始・終了管理するより、簡潔で安全にマルチスレッド処理を実装できます。

### `max_workers`

```python
max_workers=len(MOTOR_CONFIGS)
```

`max_workers` は、同時実行できる最大ワーカースレッド数です。

`MOTOR_CONFIGS` にモータ1～モータ3の3件が登録されている場合、

```python
len(MOTOR_CONFIGS)
```

は `3` です。

つまり実質的には次と同じです。

```python
max_workers=3
```

最大3つの受信処理を同時に実行できます。

```text
メインスレッド
    │
    ├─ motor1受信 → ワーカースレッド1
    ├─ motor2受信 → ワーカースレッド2
    └─ motor3受信 → ワーカースレッド3
```

### モータ数と同じスレッド数にする理由

同じモータについて、同時に複数の受信処理を動かす必要はありません。

一方、3台のモータが同時に要求を出す可能性はあります。

そのため、モータ台数と同じ最大3スレッドを準備しています。

### `thread_name_prefix`

```python
thread_name_prefix="motor-receiver"
```

ワーカースレッド名の先頭文字列です。

概ね次のような名前になります。

```text
motor-receiver_0
motor-receiver_1
motor-receiver_2
```

デバッグやログ確認時に、どのスレッドなのかを判別しやすくなります。

---

## 7. `request_latched`

```python
self.request_latched = {
    config.name: False
    for config in MOTOR_CONFIGS
}
```

これは辞書内包表記です。

実際には次の辞書が作られます。

```python
{
    "motor1": False,
    "motor2": False,
    "motor3": False,
}
```

### 役割

`request_latched` は、PLCの要求信号をすでに受け付けたかどうかを記録します。

監視ループは0.1秒ごとに動きます。

PLCの要求信号が3秒間ONのままだと、単純な処理では次のようになります。

```text
0.0秒  要求ON → 受信開始
0.1秒  要求ON → 再び受信開始
0.2秒  要求ON → 再び受信開始
...
```

これを防ぐため、最初の受付時に次のようにします。

```python
self.request_latched["motor1"] = True
```

ONのままなら再受付しません。

要求信号がOFFへ戻ったときに、

```python
self.request_latched["motor1"] = False
```

へ戻します。

次に再びONになったとき、新しい要求として受け付けます。

### PLCの立上り検出に近い考え方

```text
要求信号  OFF ─── ON ───────── OFF ─── ON
                   ↑                     ↑
                  受付                  受付
```

ONレベルを毎回処理するのではなく、OFFからONへ変わった1回だけを受け付けます。

---

## 8. `futures`

```python
self.futures: dict[str, Future[None] | None] = {
    config.name: None
    for config in MOTOR_CONFIGS
}
```

初期状態では次の辞書が作られます。

```python
{
    "motor1": None,
    "motor2": None,
    "motor3": None,
}
```

### `Future` とは

`Future` は、別スレッドで実行される処理の状態や結果を表す管理オブジェクトです。

```python
future = executor.submit(...)
```

`submit()` で登録した処理について、次のように完了状態を確認できます。

```python
future.done()
```

```text
False
    実行待ち、または実行中

True
    完了済み
```

### 型ヒントの意味

```python
dict[str, Future[None] | None]
```

分解すると次の意味です。

```text
dict[
    str,
    Future[None] または None
]
```

キーはモータ名、値はそのモータの受信タスクを表す `Future`、または未登録を表す `None` です。

`Future[None]` の `None` は、別スレッドで実行する `_receive_and_save()` が戻り値を返さないことを示します。

### `request_latched` との違い

```text
request_latched
    同じON信号を何度も受け付けない

futures
    同じモータの処理を同時に二重実行しない
```

前者はPLC信号の状態、後者はPC側タスクの実行状態を管理します。

---

## 9. `state_lock`

```python
self.state_lock = threading.Lock()
```

`threading.Lock()` は、複数のスレッドが同じ状態を同時に変更しないようにする排他制御です。

今回の共有状態は主に次の2つです。

```python
self.request_latched
self.futures
```

状態確認と更新の途中に別のスレッドが割り込むと、判定結果が不整合になる可能性があります。

そこでロックを使い、重要な処理をひとまとまりとして実行します。

---

## 10. `run()` メソッド

```python
def run(self) -> None:
    """要求デバイスを常時監視する。"""
```

`run()` は、PLC監視を開始するメイン処理です。

### 出力フォルダの作成

```python
self._create_output_directories()
```

モータごとのCSV保存先フォルダを作成します。

### 起動メッセージの表示

```python
self._print_startup_message()
```

PLC IPアドレス、監視周期、受信点数、最大並列数などを表示します。

---

## 11. 外側の `try` と `finally`

```python
try:
    while True:
        ...
finally:
    ...
```

`finally` は、正常終了でも例外終了でも、最後に必ず実行されます。

例えば次の場合です。

- `Ctrl + C` が押された
- 予期しない例外が発生した
- 終了処理へ進んだ

このコードでは、最後にスレッドプールを安全に閉じるために使っています。

---

## 12. 無限監視ループ

```python
while True:
```

停止操作があるまで処理を繰り返します。

PLC監視アプリなので、通常は常時動作します。

---

## 13. モータを順番に監視

```python
for config in MOTOR_CONFIGS:
    self._check_request(config)
```

`MOTOR_CONFIGS` のモータ設定を1件ずつ取り出します。

```text
motor1を確認
    ↓
motor2を確認
    ↓
motor3を確認
```

各モータについて `_check_request()` が呼ばれます。

### 重い処理を直接呼ばない理由

監視ループ内で次のように直接呼び出すと、受信と保存が終わるまで監視が停止します。

```python
self._receive_and_save(config)
```

その間、他のモータの要求を確認できません。

そこで監視ループは要求確認とタスク登録だけを担当し、実際の受信処理はワーカースレッドに任せます。

---

## 14. 監視処理側の例外処理

```python
except (
    ConnectionError,
    OSError,
    TimeoutError,
    RuntimeError,
) as error:
    print(f"[{current_time()}] PLC通信エラー: {error}")
```

PLC通信関連の例外をまとめて捕捉します。

```text
ConnectionError
    通信接続に関するエラー

OSError
    OSやソケットに関するエラー

TimeoutError
    通信タイムアウト

RuntimeError
    PLC応答異常など、プログラム側で検出したエラー
```

エラーを表示しても監視ループは終了せず、次の周期で再び監視します。

### データエラー

```python
except ValueError as error:
    print(f"[{current_time()}] PLCデータエラー: {error}")
```

値の形式や受信点数などの異常を、通信エラーと分けて表示します。

---

## 15. 監視周期

```python
time.sleep(POLL_INTERVAL_SECONDS)
```

例えば、

```python
POLL_INTERVAL_SECONDS = 0.1
```

なら、約100ミリ秒周期で監視します。

`sleep()` がないと、CPUが可能な限り高速に無限ループを回し続け、CPU使用率が高くなります。

---

## 16. 終了処理

```python
self.executor.shutdown(
    wait=True,
    cancel_futures=True,
)
```

`shutdown()` はスレッドプールを安全に終了します。

### `wait=True`

すでに実行中の処理が完了するまで待ちます。

CSV保存途中などで乱暴に終了することを防ぎます。

### `cancel_futures=True`

まだ実行開始されていない待機中のタスクをキャンセルします。

すでに実行中のタスクはキャンセルされません。

---

## 17. `_check_request()` メソッド

```python
def _check_request(self, config: MotorConfig) -> None:
```

モータ1台分の要求信号を確認し、必要であれば受信タスクを登録します。

引数 `config` には、対象モータの `MotorConfig` が渡されます。

---

## 18. 要求デバイスの読込み

```python
request_is_on = read_bit_device(
    self.plc_ip_address,
    config.request_device,
)
```

対象モータの要求デバイスをPLCから読み込みます。

戻り値は `bool` です。

```text
OFF → False
ON  → True
```

---

## 19. `with self.state_lock`

```python
with self.state_lock:
```

この範囲に入るとロックを取得し、抜けると自動で解放します。

手動で書く場合は概ね次と同じです。

```python
self.state_lock.acquire()
try:
    ...
finally:
    self.state_lock.release()
```

`with` を使えば、例外発生時も解放忘れがありません。

---

## 20. 要求信号がOFFの場合

```python
if not request_is_on:
    self.request_latched[config.name] = False
    return
```

要求信号がOFFなら、ラッチを解除します。

```python
self.request_latched[config.name] = False
```

その後、`return` でこのモータの確認処理を終了します。

次にONになれば、新しい要求として受付可能です。

---

## 21. すでに受付済みの場合

```python
if self.request_latched[config.name]:
    return
```

要求信号がONでも、すでにそのONを受付済みなら何もしません。

これが同じON信号の連続受付防止です。

---

## 22. 実行中タスクの確認

```python
future = self.futures[config.name]
```

対象モータの `Future` を取得します。

```python
if future is not None and not future.done():
    return
```

この条件は次の意味です。

```text
Futureが存在する
かつ
その処理がまだ完了していない
```

つまり、同じモータの受信処理が実行中なら、新しい処理を開始しません。

---

## 23. 要求を受付済みにする

```python
self.request_latched[config.name] = True
```

ここまでの判定を通過した要求を受付済みにします。

PLC要求信号がOFFへ戻るまで `True` のままです。

---

## 24. `executor.submit()`

```python
self.futures[config.name] = self.executor.submit(
    self._receive_and_save,
    config,
)
```

ここがマルチスレッド処理の中心です。

`submit()` は、指定した関数をスレッドプールへ登録します。

### 第1引数

```python
self._receive_and_save
```

実行したい関数そのものです。

ここでは括弧を付けません。

```python
self._receive_and_save
```

は関数そのものを表します。

一方、

```python
self._receive_and_save(config)
```

と書くと、その場ですぐ実行されます。

### 第2引数

```python
config
```

`_receive_and_save()` に渡す引数です。

概念的には、

```python
self._receive_and_save(config)
```

を別スレッドで実行してください、という意味です。

### 戻り値

`submit()` は `Future` を返します。

それを、

```python
self.futures[config.name]
```

へ保存して、後から完了状態を確認できるようにしています。

---

## 25. `_receive_and_save()` メソッド

```python
def _receive_and_save(self, config: MotorConfig) -> None:
```

実際の受信・保存・完了通知を担当します。

このメソッドはメインスレッドではなく、`ThreadPoolExecutor` のワーカースレッドで動きます。

```text
PLCから電流値を受信
    ↓
CSVへ保存
    ↓
PLC完了デバイスをON
```

---

## 26. PLCから電流値を受信

```python
values = kv_com.read_devices_d(
    self.plc_ip_address,
    config.data_start_device,
    DATA_POINT_COUNT,
)
```

独自通信モジュール `kv_com.py` の `read_devices_d()` を使います。

引数は次のとおりです。

```text
self.plc_ip_address
    PLCのIPアドレス

config.data_start_device
    モータごとのデータ開始デバイス

DATA_POINT_COUNT
    受信する点数
```

モータ1なら、例えば次の条件になります。

```text
開始デバイス  EM30000
受信点数      1000点
```

### 2Wordで1点

```python
# 2Wordで1点のため、32ビットデータとして1000点読み込む。
```

PLCの1Wordは通常16ビットです。

2Wordを組み合わせて、1点あたり32ビットの値として読み込みます。

受信結果は `values` に入ります。

```python
values = [123, 125, 128, ...]
```

---

## 27. CSV保存

```python
csv_path = save_csv(config, values)
```

受信した値をCSVへ保存します。

`save_csv()` は保存したファイルの `Path` を返します。

```text
C:\...\motor1\motor1_20260806_190000.csv
```

その保存先を `csv_path` に保持します。

---

## 28. PLCへの完了通知

```python
write_bit_device(
    self.plc_ip_address,
    config.completion_device,
    True,
)
```

データ受信とCSV保存が正常に完了した後、対象モータの完了デバイスをONにします。

例えばモータ1なら、

```text
B20.0 = ON
```

です。

PLC側はこれを見て、PC側の受信・保存が完了したと判断できます。

### エラー時は完了通知しない

完了通知は受信と保存の後に書かれています。

そのため、受信や保存で例外が発生すると、完了デバイスはONになりません。

誤った完了通知を出さないための重要な設計です。

---

## 29. 受信処理側の例外処理

```python
except (
    ConnectionError,
    OSError,
    TimeoutError,
    RuntimeError,
    ValueError,
) as error:
    print(f"[{current_time()}] {config.name}: 受信処理エラー: {error}")
```

受信、CSV保存、完了通知の途中で発生した例外を、このワーカースレッド内で捕捉します。

モータ名も表示するため、どのモータでエラーが起きたか分かります。

```text
[2026-08-06 19:00:01] motor2: 受信処理エラー: 通信タイムアウト
```

`ThreadPoolExecutor` 内の例外を適切に表示するために重要です。

---

## 30. `@staticmethod`

```python
@staticmethod
def _create_output_directories() -> None:
```

`@staticmethod` は、インスタンス自身の情報を必要としないメソッドに付けます。

このメソッドでは `self` を使いません。

使用するのは `MOTOR_CONFIGS` だけです。

そのため静的メソッドとして定義されています。

---

## 31. 出力ディレクトリ作成

```python
for config in MOTOR_CONFIGS:
    config.output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
```

すべてのモータ設定について、保存先フォルダを作成します。

### `parents=True`

親フォルダが存在しなくても、まとめて作成します。

### `exist_ok=True`

対象フォルダがすでに存在していてもエラーにしません。

アプリを2回目以降に起動するときも安全です。

---

## 32. `_print_startup_message()`

```python
def _print_startup_message(self) -> None:
```

起動時に、現在の設定内容をコンソールへ表示します。

このメソッドは `self.plc_ip_address` を使うため、通常のインスタンスメソッドです。

表示内容には次が含まれます。

- PLC IPアドレス
- 監視周期
- 受信点数
- 最大並列数
- 停止方法
- 各モータの要求デバイス
- 各モータのデータ開始デバイス
- 各モータの完了デバイス

設定ミスを起動時に発見しやすくなります。

---

## 33. メインスレッドとワーカースレッド

### メインスレッド

要求信号の監視を続けます。

```text
motor1確認
motor2確認
motor3確認
0.1秒待機
繰り返し
```

### ワーカースレッド

時間のかかる処理を担当します。

```text
1000点受信
CSV保存
完了信号ON
```

この分離により、モータ1の受信中でも、モータ2・モータ3の要求を検出できます。

---

## 34. 全体の処理フロー

```text
1. MotorReceiverを生成
        ↓
2. PLC IPアドレスを保存
        ↓
3. ThreadPoolExecutorを作成
        ↓
4. request_latchedを初期化
        ↓
5. futuresを初期化
        ↓
6. Lockを作成
        ↓
7. run()を開始
        ↓
8. 保存フォルダを作成
        ↓
9. 起動メッセージを表示
        ↓
10. motor1～motor3を0.1秒周期で監視
        ↓
11. 要求信号ONを検出
        ↓
12. 同じONを受付済みか確認
        ↓
13. 同じモータの処理が実行中か確認
        ↓
14. ThreadPoolExecutorへタスク登録
        ↓
15. 別スレッドでPLCからデータ受信
        ↓
16. CSV保存
        ↓
17. PLC完了デバイスON
        ↓
18. 次の要求を待つ
```

---

## 35. このクラスの重要な設計

### 設定と処理を分離している

モータごとの設定は `MotorConfig`、動作は `MotorReceiver` が担当します。

### 監視処理と重い処理を分離している

要求監視はメインスレッド、受信・保存はワーカースレッドです。

### スレッド数を制限している

`max_workers` によって、無制限にスレッドが増えることを防ぎます。

### 同じ要求の重複受付を防いでいる

`request_latched` により、ON中の繰り返し受付を防ぎます。

### 同じモータの二重実行を防いでいる

`Future.done()` により、処理中のモータへ新しいタスクを登録しません。

### 共有状態をロックで保護している

`threading.Lock()` により、状態確認と更新を安全に行います。

### 終了処理が安全

`finally` と `executor.shutdown()` により、実行中の処理を考慮して終了します。

### エラー原因が分かりやすい

監視側と受信側の両方で、時刻・モータ名・エラー内容を表示します。

---

## 36. 学習上の重要キーワード

```text
class
__init__
self
インスタンス属性
型ヒント
辞書内包表記
ThreadPoolExecutor
max_workers
thread_name_prefix
submit
Future
Future.done
threading.Lock
with文
try
except
finally
while True
for文
return
staticmethod
Path.mkdir
```

---

## 37. まとめ

`MotorReceiver` は、PLC要求信号を常時監視し、要求が発生したモータの電流値を別スレッドで受信・保存する管理クラスです。

中心となる考え方は次のとおりです。

```text
メインスレッド
    PLC要求信号を常時監視する

ThreadPoolExecutor
    モータごとの受信処理を別スレッドで実行する

request_latched
    同じON信号を何度も受け付けない

futures
    同じモータの受信処理を二重実行しない

state_lock
    共有状態を安全に扱う

finally + shutdown
    プログラム終了時にスレッドを安全に停止する
```

このクラスには、PLC通信アプリだけでなく、今後さまざまなマルチスレッドアプリを作るうえで重要な設計が詰まっています。

特に次の考え方は、実務的なPythonアプリで広く役立ちます。

- 監視処理と時間のかかる処理を分離する
- スレッド数を制限する
- `Future` でタスク状態を管理する
- `Lock` で共有状態を保護する
- `finally` で必ず終了処理を行う
- `ThreadPoolExecutor` を正しく `shutdown()` する
