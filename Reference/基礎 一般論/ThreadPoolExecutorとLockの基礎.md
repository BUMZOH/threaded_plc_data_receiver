# ThreadPoolExecutorとLockの基礎
## Pythonで安全にマルチスレッド処理を行うための学習ノート

---

## 1. はじめに

この資料では、Pythonの `ThreadPoolExecutor` を使ったマルチスレッド処理と、`threading.Lock` を使った排他制御について学びます。

今回のPLC受信アプリでは、次のような目的で使われています。

- PLCの要求信号監視を止めずに、データ受信処理を実行する
- モータ1～モータ3の受信処理を並行して実行する
- 同時に実行するスレッド数を制限する
- 実行中の処理を `Future` で管理する
- 複数スレッドから共有状態を安全に読み書きする
- プログラム終了時にスレッドを安全に停止する

マルチスレッドは便利ですが、処理の重複や共有データの競合が起きやすくなります。

そのため、次の2つをセットで理解することが重要です。

```text
ThreadPoolExecutor
    複数の処理を別スレッドで実行・管理する

Lock
    複数スレッドが同じデータを同時に変更しないようにする
```

---

# 2. スレッドとは

スレッドは、1つのプログラム内で処理を進める実行単位です。

通常のPythonプログラムは、まず1本のスレッドで動きます。

これをメインスレッドと呼びます。

```text
メインスレッド
    処理A
      ↓
    処理B
      ↓
    処理C
```

処理Aが終わるまで、処理Bは始まりません。

---

## 2.1 シングルスレッドの問題

例えば、PLCからのデータ受信に2秒かかるとします。

シングルスレッドで次のように書くと、

```python
check_request()
receive_plc_data()
save_csv()
```

`receive_plc_data()` と `save_csv()` が終わるまで、要求信号の監視が止まります。

```text
要求監視
    ↓
モータ1のデータ受信（2秒）
    ↓
CSV保存
    ↓
要求監視を再開
```

この間にモータ2の要求が来ても、すぐに確認できません。

---

## 2.2 マルチスレッドの考え方

マルチスレッドでは、時間のかかる処理を別スレッドへ任せます。

```text
メインスレッド
    PLC要求信号を監視し続ける

ワーカースレッド1
    モータ1のデータ受信と保存

ワーカースレッド2
    モータ2のデータ受信と保存

ワーカースレッド3
    モータ3のデータ受信と保存
```

メインスレッドは監視を継続しながら、ワーカースレッドが別の処理を進められます。

---

# 3. 並行処理と並列処理

マルチスレッドを学ぶときは、「並行」と「並列」の違いを知っておくと理解しやすくなります。

## 並行処理

複数の処理を、重なり合う時間帯で進める考え方です。

```text
処理A  ──────
処理B    ──────
処理C      ──────
```

必ずしも同じ瞬間にCPUで実行されるとは限りません。

## 並列処理

複数の処理を、実際に同じ瞬間に実行することです。

複数のCPUコアなどを使います。

---

## 3.1 ThreadPoolExecutorは何に向いているか

Pythonのスレッドは、特にI/O待ちが多い処理に向いています。

I/Oとは、例えば次の処理です。

- PLC通信
- ネットワーク通信
- ファイル読込み
- ファイル書込み
- データベース通信
- 待機処理

PLCから応答を待っている間、CPUはずっと計算しているわけではありません。

その待ち時間に別スレッドを動かせるため、今回のPLC受信アプリと相性が良い方式です。

一方、大量の数値計算など、CPUを長時間使い続ける処理では、スレッドより `ProcessPoolExecutor` や別プロセスが適する場合があります。

---

# 4. ThreadPoolExecutorとは

`ThreadPoolExecutor` は、複数のスレッドをまとめて管理するためのクラスです。

次のモジュールから読み込みます。

```python
from concurrent.futures import ThreadPoolExecutor
```

基本形は次のとおりです。

```python
executor = ThreadPoolExecutor(max_workers=3)
```

これは、

> 最大3本のワーカースレッドを使えるスレッドプールを作る

という意味です。

---

# 5. スレッドプールとは

スレッドプールは、処理に使うスレッドを一定数だけ用意し、登録された仕事を順番に実行する仕組みです。

```text
スレッドプール
├─ ワーカースレッド1
├─ ワーカースレッド2
└─ ワーカースレッド3
```

処理を登録すると、空いているワーカースレッドが実行します。

---

## 5.1 毎回Threadを作る方法との違い

`threading.Thread` を直接使う場合、処理ごとにスレッドを作成します。

```python
thread = threading.Thread(target=some_function)
thread.start()
```

処理が増えると、次の管理が必要になります。

- スレッド作成
- スレッド開始
- スレッド終了待ち
- 同時実行数の制御
- 実行状態の管理

`ThreadPoolExecutor` を使うと、これらをまとめて管理できます。

---

## 5.2 ThreadPoolExecutorのメリット

- スレッド生成を自分で細かく管理しなくてよい
- 最大同時実行数を制限できる
- `submit()` で簡単に処理を登録できる
- `Future` で実行状態を確認できる
- `shutdown()` で安全に終了できる
- 例外や戻り値を管理しやすい

---

# 6. max_workers

```python
executor = ThreadPoolExecutor(max_workers=3)
```

`max_workers` は、同時に処理を実行できる最大ワーカースレッド数です。

今回のコードでは次のように書かれています。

```python
self.executor = ThreadPoolExecutor(
    max_workers=len(MOTOR_CONFIGS),
    thread_name_prefix="motor-receiver",
)
```

`MOTOR_CONFIGS` にモータ1～モータ3の3件が入っているため、

```python
len(MOTOR_CONFIGS)
```

の結果は `3` です。

したがって、実質的には次と同じです。

```python
max_workers=3
```

---

## 6.1 max_workersを超えたタスク

例えば `max_workers=3` のときに、4つのタスクを登録したとします。

```text
タスク1 → ワーカースレッド1で実行
タスク2 → ワーカースレッド2で実行
タスク3 → ワーカースレッド3で実行
タスク4 → 空きが出るまで待機
```

4つ目のタスクは失われません。

実行中のタスクが終わるまで待機キューに入ります。

---

## 6.2 max_workersを大きくしすぎない

スレッド数を増やせば、必ず速くなるわけではありません。

多すぎると、次の問題が起きます。

- メモリ使用量が増える
- スレッド切替の負荷が増える
- PLCへ同時に大量アクセスしてしまう
- ファイルや共有データの競合が増える
- 処理の順番が分かりにくくなる

今回のように対象モータが3台なら、最大3スレッドは分かりやすく妥当な設定です。

---

# 7. thread_name_prefix

```python
thread_name_prefix="motor-receiver"
```

これは、作成されるワーカースレッド名の先頭文字列です。

概ね次のような名前になります。

```text
motor-receiver_0
motor-receiver_1
motor-receiver_2
```

デバッグ時にスレッド名を表示すると、どのワーカースレッドで処理されているか確認できます。

```python
import threading

print(threading.current_thread().name)
```

---

# 8. submit()の基本

処理をスレッドプールへ登録するときは `submit()` を使います。

```python
future = executor.submit(function, argument)
```

例えば次の関数があるとします。

```python
def receive_data(motor_name: str) -> None:
    print(f"{motor_name}の受信開始")
```

これを別スレッドで実行する場合は、次のように書きます。

```python
future = executor.submit(
    receive_data,
    "motor1",
)
```

これは概念的には、

```python
receive_data("motor1")
```

を別スレッドで実行する、という意味です。

---

# 9. 関数名に括弧を付けない理由

`submit()` の第1引数には、関数の実行結果ではなく、関数そのものを渡します。

正しい例です。

```python
executor.submit(
    receive_data,
    "motor1",
)
```

誤った例です。

```python
executor.submit(
    receive_data("motor1"),
)
```

後者は `submit()` に渡す前に、メインスレッド上で `receive_data("motor1")` を実行してしまいます。

---

## 9.1 今回のコード

```python
self.futures[config.name] = self.executor.submit(
    self._receive_and_save,
    config,
)
```

第1引数は、実行するメソッドそのものです。

```python
self._receive_and_save
```

第2引数は、そのメソッドへ渡す引数です。

```python
config
```

つまり、

```python
self._receive_and_save(config)
```

をワーカースレッドで実行します。

---

# 10. Futureとは

`submit()` の戻り値は `Future` オブジェクトです。

```python
future = executor.submit(...)
```

`Future` は、登録した処理の状態、戻り値、例外を管理します。

Futureは「将来完了する処理を表す引換券」のようなものです。

---

# 11. Futureの主なメソッド

## 11.1 `done()`

```python
future.done()
```

処理が完了したかを確認します。

```text
False
    まだ実行中、または実行待ち

True
    正常終了または例外終了している
```

注意点として、`done()` が `True` でも正常終了とは限りません。

例外で終了した場合も `True` になります。

---

## 11.2 `running()`

```python
future.running()
```

現在実行中かを確認します。

```text
True
    ワーカースレッドで実行中

False
    実行前、完了済み、またはキャンセル済み
```

---

## 11.3 `cancelled()`

```python
future.cancelled()
```

タスクがキャンセルされたか確認します。

---

## 11.4 `cancel()`

```python
future.cancel()
```

まだ開始されていないタスクをキャンセルしようとします。

すでに実行中のタスクは、通常キャンセルできません。

戻り値は `bool` です。

```text
True
    キャンセル成功

False
    すでに実行中などの理由でキャンセルできなかった
```

---

## 11.5 `result()`

```python
result = future.result()
```

処理の戻り値を取得します。

まだ完了していなければ、完了するまで待機します。

例えば、

```python
def add(a: int, b: int) -> int:
    return a + b

future = executor.submit(add, 10, 20)
result = future.result()

print(result)
```

結果は次のとおりです。

```text
30
```

---

## 11.6 result()と例外

ワーカースレッド内で例外が発生していた場合、`future.result()` を呼んだ場所で、その例外が再送出されます。

```python
def fail() -> None:
    raise ValueError("処理に失敗しました")

future = executor.submit(fail)
future.result()
```

この場合、`future.result()` で `ValueError` が発生します。

---

# 12. Futureの型ヒント

今回のコードには次の型ヒントがあります。

```python
self.futures: dict[str, Future[None] | None]
```

分解すると次の意味です。

```text
dict[
    str,
    Future[None] または None
]
```

キーはモータ名です。

```text
motor1
motor2
motor3
```

値は、そのモータに対応する `Future`、またはまだタスクが登録されていないことを表す `None` です。

---

## 12.1 Future[None]の意味

```python
Future[None]
```

は、実行する関数の戻り値が `None` であることを表します。

今回の `_receive_and_save()` は次の定義です。

```python
def _receive_and_save(self, config: MotorConfig) -> None:
```

戻り値を返さないため、対応するFutureは `Future[None]` です。

---

# 13. Futureによる二重実行防止

今回のコードでは次のように確認しています。

```python
future = self.futures[config.name]

if future is not None and not future.done():
    return
```

意味は次のとおりです。

```text
Futureが登録済み
かつ
その処理がまだ完了していない
```

この場合、新しい受信処理を開始しません。

つまり、

> 同じモータの受信処理が実行中なら、二重に起動しない

という制御です。

---

# 14. Executorの終了処理

スレッドプールは、プログラム終了時に正しく閉じる必要があります。

```python
executor.shutdown()
```

今回のコードでは次のように書かれています。

```python
self.executor.shutdown(
    wait=True,
    cancel_futures=True,
)
```

---

## 14.1 wait=True

```python
wait=True
```

すでに実行中のタスクが終わるまで待機します。

例えば、CSV保存中に終了操作が行われても、処理を途中で切らず、完了を待ちます。

---

## 14.2 cancel_futures=True

```python
cancel_futures=True
```

まだ実行開始されていない待機中のタスクをキャンセルします。

すでに実行中のタスクはキャンセルされません。

---

## 14.3 shutdown後のsubmit

`shutdown()` を実行した後は、新しいタスクを登録できません。

```python
executor.submit(...)
```

を呼ぶと、`RuntimeError` になります。

---

# 15. with文でExecutorを使う方法

小さな処理では、`with` 文を使う方法もあります。

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=3) as executor:
    future1 = executor.submit(task1)
    future2 = executor.submit(task2)
```

`with` ブロックを抜けると、自動的に `shutdown(wait=True)` 相当の処理が行われます。

ただし、今回のPLC受信アプリは長時間動作する常駐アプリです。

そのため、`__init__()` でExecutorを作成し、終了時に明示的に `shutdown()` する構成が分かりやすくなっています。

---

# 16. try-finallyとshutdown

今回のコードでは、次のように `finally` 内で終了処理を行っています。

```python
try:
    while True:
        ...
finally:
    self.executor.shutdown(
        wait=True,
        cancel_futures=True,
    )
```

`finally` は、正常終了でも例外終了でも実行されます。

これにより、次の場合でもスレッドプールを閉じられます。

- `Ctrl + C` が押された
- 監視処理で例外が発生した
- プログラム終了処理へ進んだ

マルチスレッドアプリでは、終了処理を `finally` に置くことが重要です。

---

# 17. ワーカースレッド内の例外処理

今回の `_receive_and_save()` は、内部で例外を捕捉しています。

```python
def _receive_and_save(self, config: MotorConfig) -> None:
    try:
        ...
    except (
        ConnectionError,
        OSError,
        TimeoutError,
        RuntimeError,
        ValueError,
    ) as error:
        print(...)
```

ワーカースレッド内で発生した例外を、その場でログ表示します。

---

## 17.1 例外を捕捉しない場合

ワーカースレッド内の例外は、Futureに保存されます。

メインスレッドで `future.result()` を呼べば確認できますが、呼ばなければ見落としやすくなる場合があります。

そのため、常駐アプリでは次のいずれかの方式が必要です。

- ワーカー関数内で例外を捕捉して記録する
- メイン側で `Future.result()` を確認する
- `add_done_callback()` で完了時に確認する

今回のコードでは、ワーカー関数内で捕捉する方式を採用しています。

---

# 18. add_done_callback()

Futureには、処理完了時に関数を呼び出す機能があります。

```python
future.add_done_callback(callback)
```

例です。

```python
def on_finished(future: Future) -> None:
    try:
        result = future.result()
        print(f"完了: {result}")
    except Exception as error:
        print(f"エラー: {error}")

future = executor.submit(task)
future.add_done_callback(on_finished)
```

今回のコードでは使用していませんが、Futureの例外や完了状態を一元管理したい場合に便利です。

---

# 19. as_completed()

複数のFutureを、完了した順に処理できます。

```python
from concurrent.futures import as_completed

futures = [
    executor.submit(task, value)
    for value in values
]

for future in as_completed(futures):
    result = future.result()
    print(result)
```

登録順ではなく、完了した順に結果を受け取ります。

今回のPLCアプリは結果をまとめて待つ処理ではなく、長時間監視を続けるため、`as_completed()` は使用していません。

---

# 20. map()

複数の引数に同じ関数を適用する場合は `map()` も使えます。

```python
results = executor.map(process, values)
```

ただし、今回のようにモータごとのタスクを個別に管理し、Futureを辞書へ保存したい場合は `submit()` のほうが適しています。

---

# 21. Lockとは

```python
lock = threading.Lock()
```

`Lock` は、複数スレッドが共有データへ同時にアクセスすることを防ぐ仕組みです。

日本語では、排他制御や相互排他と呼ばれます。

---

# 22. 共有データとは

複数のスレッドから参照・変更されるデータを共有データと呼びます。

今回のコードでは次の属性が共有状態です。

```python
self.request_latched
self.futures
```

これらは、モータごとの受付状態や実行状態を保持しています。

---

# 23. 競合状態とは

複数スレッドが同じデータをほぼ同時に読み書きすると、処理順序によって結果が変わることがあります。

これを競合状態、英語では race condition と呼びます。

例えば、次の共有変数があるとします。

```python
counter = 0
```

2つのスレッドが同時に次の処理を行います。

```python
counter += 1
```

見た目は1行ですが、内部では概ね次の処理です。

```text
現在値を読む
    ↓
1を足す
    ↓
新しい値を書き込む
```

2つのスレッドが同じ値を読んでしまうと、本来2増えるはずが1しか増えないことがあります。

---

# 24. Lockの基本的な使い方

```python
lock = threading.Lock()

with lock:
    shared_dataを確認・変更する
```

`with lock:` の範囲には、同時に1つのスレッドしか入れません。

---

## 24.1 動作イメージ

```text
スレッドA
    Lock取得
        ↓
    共有データを処理
        ↓
    Lock解放

スレッドB
    Lockが空くまで待機
        ↓
    Lock取得
        ↓
    共有データを処理
        ↓
    Lock解放
```

---

# 25. acquire()とrelease()

`with` を使わずに、手動でLockを操作することもできます。

```python
lock.acquire()

try:
    shared_dataを処理する
finally:
    lock.release()
```

ただし、`release()` を忘れると、他のスレッドが永久に待ち続ける危険があります。

そのため、通常は次の書き方が推奨されます。

```python
with lock:
    ...
```

`with` ブロックを抜けると、自動的にLockが解放されます。

例外が発生した場合でも解放されるため安全です。

---

# 26. 今回のLock処理

今回のコードでは次のように定義しています。

```python
self.state_lock = threading.Lock()
```

そして `_check_request()` 内で使用しています。

```python
with self.state_lock:
    if not request_is_on:
        self.request_latched[config.name] = False
        return

    if self.request_latched[config.name]:
        return

    future = self.futures[config.name]
    if future is not None and not future.done():
        return

    self.request_latched[config.name] = True

    self.futures[config.name] = self.executor.submit(
        self._receive_and_save,
        config,
    )
```

この範囲では、次の処理を1つのまとまりとして扱っています。

```text
要求受付状態を確認
    ↓
実行中タスクを確認
    ↓
要求受付済みに変更
    ↓
新しいFutureを登録
```

---

# 27. 判定と更新をまとめてLockする理由

次のように、確認だけLockして更新を外で行うと危険です。

```python
with lock:
    can_start = not running

if can_start:
    running = True
```

Lockを解放してから `running = True` にするまでの間に、別スレッドも同じ判定を通過する可能性があります。

その結果、同じ処理が二重に開始されるかもしれません。

安全な形は次です。

```python
with lock:
    if running:
        return

    running = True
```

確認と更新を同じLock範囲に入れます。

---

# 28. Lockする範囲は短くする

Lock中は、他のスレッドがそのLockを取得できません。

そのため、Lockの範囲で時間のかかる処理を行うと、待ち時間が増えます。

避けたい例です。

```python
with lock:
    values = read_large_data_from_plc()
    save_large_csv(values)
```

PLC通信やCSV保存には時間がかかる可能性があります。

その間、他のスレッドがLockを取得できません。

---

## 28.1 今回の考え方

今回のコードでは、Lock範囲内で行う主な処理は次のとおりです。

- 辞書の値を確認
- 辞書の値を更新
- タスクを登録

実際のPLCデータ受信とCSV保存は、別の `_receive_and_save()` で実行されます。

そのため、長時間Lockを保持しにくい設計になっています。

---

# 29. デッドロックとは

デッドロックは、複数のスレッドがお互いのLock解放を待ち続け、処理が進まなくなる状態です。

例です。

```text
スレッドA
    Lock1を取得
    Lock2が空くのを待つ

スレッドB
    Lock2を取得
    Lock1が空くのを待つ
```

両方とも相手のLock解放を待つため、永久に進みません。

---

## 29.1 デッドロックを避ける基本

- Lockの数を必要最小限にする
- 複数Lockを取る場合は、常に同じ順番で取得する
- Lock中に時間のかかる処理をしない
- Lock中に外部通信を行わない
- `with lock:` を使って解放忘れを防ぐ
- Lock中に別のLock取得が必要な関数をむやみに呼ばない

今回のコードは1つの `state_lock` で状態を管理しているため、比較的理解しやすい構成です。

---

# 30. LockとGILの違い

PythonにはGILという仕組みがあります。

GILは、CPythonでPythonコードを実行するスレッドを内部的に制御する仕組みです。

しかし、GILがあるから共有データのLockが不要になるわけではありません。

次のような複数操作を組み合わせた処理は、途中で別スレッドへ切り替わる可能性があります。

```python
if not running:
    running = True
```

これは、

```text
runningを読む
条件を判定する
runningへ書き込む
```

という複数処理です。

したがって、共有状態の整合性を守るためには、明示的なLockが必要です。

---

# 31. Lockが必要な場面

次のような場合は、Lockの利用を検討します。

- 複数スレッドが同じ辞書を書き換える
- 複数スレッドが同じリストへ追加・削除する
- 共有フラグを確認して変更する
- カウンタを更新する
- 同じファイルへ同時に書き込む
- 同じ機器へ同時アクセスさせたくない
- 判定と更新を一体として扱いたい

---

# 32. Lockが不要な場合

次のような場合は、Lockが不要なこともあります。

- スレッドごとに完全に別のデータを扱う
- 読み取り専用データだけを共有する
- 不変オブジェクトだけを参照する
- 共有状態をメインスレッドだけが変更する
- Queueなど、スレッドセーフな仕組みを使う

ただし、Lockが必要か分からない場合は、

> 複数スレッドが同じオブジェクトを変更する可能性があるか

を確認します。

---

# 33. request_latchedとFuture

今回のPLCアプリでは、次の2つで重複処理を防止しています。

## request_latched

```python
self.request_latched
```

PLC要求信号がONのまま継続している間、同じ要求を再受付しないための状態です。

## futures

```python
self.futures
```

同じモータの受信処理がまだ実行中か確認するための状態です。

---

## 33.1 役割の違い

```text
request_latched
    PLC信号の状態を管理する

futures
    PC側タスクの状態を管理する
```

例えばPLC信号が一度OFFへ戻っても、前回のPC受信処理がまだ終了していない可能性があります。

その場合、

```python
future is not None and not future.done()
```

によって、新しい処理を開始しません。

---

# 34. 処理全体のタイムチャート

```text
PLC要求信号      OFF ── ON ───────── OFF ────────
request_latched  False  True          False
受信タスク              実行中 ───── 完了
Future           None   running       done
```

最初のONを検出すると、`request_latched` が `True` になります。

受信タスクが登録され、Futureが実行中になります。

要求信号がOFFへ戻ると、`request_latched` は `False` に戻ります。

Futureが完了していれば、次のONで新しい受信処理を開始できます。

---

# 35. ThreadPoolExecutorを使うときの注意点

## 35.1 同じ関数が同時に実行される可能性がある

同じ関数を複数回 `submit()` すると、複数スレッドで同時に動く可能性があります。

関数内で共有データを扱う場合は注意が必要です。

## 35.2 実行順序は保証されない

タスクを登録した順番と、完了する順番は同じとは限りません。

```text
登録順
    motor1
    motor2
    motor3

完了順
    motor2
    motor1
    motor3
```

通信時間や保存時間によって変わります。

## 35.3 printの順番が混ざることがある

複数スレッドが同時に `print()` すると、ログの順番が前後することがあります。

本格的な運用では、Python標準の `logging` モジュールを使う方法もあります。

## 35.4 ワーカー内例外を見落とさない

ワーカー関数内で例外を処理するか、Futureから確認する仕組みが必要です。

## 35.5 shutdownを忘れない

常駐アプリでは、終了時に `shutdown()` を実行します。

## 35.6 PLC通信ライブラリのスレッド安全性を確認する

独自モジュールや通信ライブラリが、複数スレッドから同時に呼び出されても安全か確認する必要があります。

各呼び出しが独立したソケットを作る設計なら問題が起きにくいですが、1つの共有接続を内部で使っている場合は、通信部分にもLockが必要になる可能性があります。

---

# 36. PLC通信自体にLockが必要な場合

今回の `state_lock` は、受付状態やFuture辞書を守るためのLockです。

PLC通信そのものを保護するLockではありません。

もし `kv_com.py` が1つの共有ソケットや共有バッファを使っていて、同時通信に対応していない場合は、別の通信Lockが必要です。

例です。

```python
self.communication_lock = threading.Lock()
```

通信時に次のように使います。

```python
with self.communication_lock:
    values = kv_com.read_devices_d(...)
```

ただし、これを使うとPLC通信は1つずつ順番に実行されます。

つまり、プログラム上はマルチスレッドでも、通信部分は直列になります。

必要かどうかは、`kv_com.py` の実装とPLC側の同時通信対応によって決まります。

---

# 37. ThreadPoolExecutorが向いている処理

- PLC通信
- HTTP通信
- ファイルコピー
- CSV保存
- 複数機器の状態確認
- データベースからの読込み
- 待機時間の長い処理
- GUIを止めたくないバックグラウンド処理

---

# 38. ThreadPoolExecutorが向いていないことがある処理

- 大量の画像処理
- 長時間の数値計算
- 暗号計算
- 大規模なデータ変換
- CPUを使い続ける解析処理

このようなCPU負荷の高い処理では、`ProcessPoolExecutor` などを検討します。

---

# 39. 最小サンプル

```python
import time
from concurrent.futures import ThreadPoolExecutor


def work(name: str) -> None:
    print(f"{name}: 開始")
    time.sleep(2)
    print(f"{name}: 完了")


def main() -> None:
    with ThreadPoolExecutor(max_workers=3) as executor:
        executor.submit(work, "motor1")
        executor.submit(work, "motor2")
        executor.submit(work, "motor3")


if __name__ == "__main__":
    main()
```

3つの処理が別スレッドで進みます。

---

# 40. Futureを保存するサンプル

```python
from concurrent.futures import Future, ThreadPoolExecutor


def work(name: str) -> None:
    print(f"{name}: 実行")


executor = ThreadPoolExecutor(max_workers=3)

futures: dict[str, Future[None]] = {}

futures["motor1"] = executor.submit(work, "motor1")

if futures["motor1"].done():
    print("motor1は完了しています")
else:
    print("motor1はまだ実行中です")

executor.shutdown(wait=True)
```

---

# 41. Lockを使ったサンプル

```python
import threading
from concurrent.futures import ThreadPoolExecutor


counter = 0
counter_lock = threading.Lock()


def increment() -> None:
    global counter

    with counter_lock:
        counter += 1


def main() -> None:
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(increment)
            for _ in range(1000)
        ]

        for future in futures:
            future.result()

    print(counter)


if __name__ == "__main__":
    main()
```

`with counter_lock:` によって、`counter` の更新を1スレッドずつ行います。

---

# 42. PLC受信アプリへの対応表

```text
ThreadPoolExecutor
    モータごとの受信処理を実行する

max_workers
    同時に受信できる最大モータ数

submit
    受信処理をワーカースレッドへ登録する

Future
    各モータの受信タスクを管理する

Future.done
    受信処理が完了したか確認する

request_latched
    同じPLC要求信号の再受付を防止する

Lock
    request_latchedとfuturesの判定・更新を保護する

shutdown
    終了時にスレッドプールを安全に閉じる

finally
    終了理由にかかわらずshutdownを実行する
```

---

# 43. 学習時に覚えるべき基本形

## Executorの作成

```python
executor = ThreadPoolExecutor(max_workers=3)
```

## タスクの登録

```python
future = executor.submit(function, argument)
```

## 完了確認

```python
future.done()
```

## 結果取得

```python
result = future.result()
```

## Lockの作成

```python
lock = threading.Lock()
```

## Lockの利用

```python
with lock:
    shared_stateを確認・更新する
```

## 終了処理

```python
executor.shutdown(
    wait=True,
    cancel_futures=True,
)
```

---

# 44. まとめ

`ThreadPoolExecutor` は、複数のスレッドを安全かつ簡潔に管理するための仕組みです。

重要な役割は次のとおりです。

```text
ThreadPoolExecutor
    ワーカースレッドをまとめて管理する

max_workers
    最大同時実行数を制限する

submit
    関数を別スレッドで実行する

Future
    タスクの状態、結果、例外を管理する

shutdown
    スレッドプールを安全に終了する
```

一方、`Lock` は、複数スレッドが同じ共有状態を同時に変更することを防ぎます。

```text
Lock
    同時に1スレッドだけを重要処理へ入れる

with lock
    Lockの取得と解放を安全に行う

排他制御
    共有状態の競合や二重実行を防ぐ
```

今回のPLC受信アプリでは、

```text
メインスレッド
    PLC要求信号の監視を継続する

ワーカースレッド
    PLCデータ受信、CSV保存、完了通知を行う

Future
    モータごとの受信処理が実行中か管理する

Lock
    要求受付状態とFuture登録を安全に行う
```

という役割分担になっています。

`ThreadPoolExecutor` だけでなく、`Future`、`Lock`、`finally`、`shutdown()` を組み合わせることで、安全で読みやすいマルチスレッドアプリを構築できます。
