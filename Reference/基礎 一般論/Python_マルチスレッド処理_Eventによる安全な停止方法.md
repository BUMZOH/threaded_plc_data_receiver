# Python マルチスレッド処理 ― `threading.Event` による安全な停止方法

## 1. はじめに

Pythonでマルチスレッド処理を行っていると、次のような場面があります。

- 長時間動作するスレッドを途中で終了したい
- 定周期で動いている監視処理を停止したい
- キーボード入力や終了ボタンをきっかけにバックグラウンド処理を終了したい
- `threading.Thread` と `ThreadPoolExecutor` では停止方法が違うのか知りたい

このような場合に重要になるのが、Python標準ライブラリの `threading.Event` です。

結論から言うと、**`threading.Thread` でも `ThreadPoolExecutor` でも、すでに実行を開始した処理を安全に終了させる基本的な考え方は同じ**です。

`threading.Event` を使って「停止要求」をワーカーへ伝え、ワーカー自身がその要求を確認して処理を終了します。

---

## 2. 「スレッドを止める」という表現について

日常的には「スレッドを止める」と表現して問題ありません。

ただし、技術的には次のように理解しておくと正確です。

> 外部からスレッドを強制終了するのではなく、停止要求を通知し、スレッド側がそれを検知して自分で処理を終了する。

この方式は一般に**協調的キャンセル（cooperative cancellation）**と呼ばれる考え方です。

Pythonでは、実行中のスレッドを外部から安全に強制終了する一般的な仕組みは用意されていません。

そこで、次のような流れにします。

```text
メイン側                         ワーカー側
   │                                │
   │                                │ 処理
   │                                │ 処理
   │ stop_event.set()               │
   ├──────── 停止要求 ──────────────>│
   │                                │
   │                                │ stop_event.is_set()
   │                                │     ↓ True
   │                                │ ループ終了
   │                                │
   │                            処理終了
```

重要なのは、`Event` 自体がスレッドを直接停止するわけではないことです。

`Event` は、

> 「止まってください」

という信号をスレッド間で共有するための仕組みです。

---

# 3. `threading.Event` とは

`Event` は `threading` モジュールに用意されている、スレッド間で状態や合図を共有するための同期機構です。

作成方法は次のとおりです。

```python
import threading

stop_event = threading.Event()
```

作成直後の Event は「OFF」の状態です。

```python
stop_event.is_set()
```

は `False` を返します。

その後、

```python
stop_event.set()
```

を実行すると「ON」の状態になり、

```python
stop_event.is_set()
```

は `True` を返すようになります。

この状態変化を停止要求として利用できます。

---

# 4. `threading.Thread` の場合

## 4.1 基本例

```python
import threading
import time


def worker(stop_event):
    while not stop_event.is_set():
        print("処理中...")
        time.sleep(1)

    print("終了します")


stop_event = threading.Event()

thread = threading.Thread(
    target=worker,
    args=(stop_event,),
)

thread.start()

time.sleep(5)

stop_event.set()

thread.join()

print("プログラム終了")
```

## 4.2 処理の流れ

まず停止通知用の Event を作ります。

```python
stop_event = threading.Event()
```

次に、その Event をワーカー関数へ渡します。

```python
thread = threading.Thread(
    target=worker,
    args=(stop_event,),
)
```

ワーカーでは次の条件でループします。

```python
while not stop_event.is_set():
```

Event がまだセットされていなければ、

```python
stop_event.is_set()
```

は `False` です。

したがって、

```python
not False
```

は `True` となり、ループが継続します。

停止したい側が、

```python
stop_event.set()
```

を実行すると、以降は、

```python
stop_event.is_set()
```

が `True` になります。

そのため、

```python
while not stop_event.is_set():
```

の条件が成立しなくなり、ワーカーがループから抜けます。

つまり、`set()` がワーカーを強制終了しているわけではありません。

**ワーカー自身が Event の状態を確認して、自分でループを終了しています。**

---

# 5. `ThreadPoolExecutor` の場合

`ThreadPoolExecutor` を使った場合でも、すでに動いている処理を終了させる基本的な考え方は同じです。

```python
import threading
import time
from concurrent.futures import ThreadPoolExecutor


def worker(stop_event):
    while not stop_event.is_set():
        print("処理中...")
        time.sleep(1)

    print("終了します")


stop_event = threading.Event()

with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(
        worker,
        stop_event,
    )

    time.sleep(5)

    stop_event.set()
```

ここでも、

```python
stop_event.set()
```

によって停止要求を通知します。

ワーカー側は、

```python
stop_event.is_set()
```

を確認し、自分自身で処理を終了します。

したがって、停止要求については次のように考えられます。

```text
threading.Thread
        │
        ├── Eventを共有
        │
        └── workerがEventを確認

ThreadPoolExecutor
        │
        ├── Eventを共有
        │
        └── workerがEventを確認
```

この部分の考え方は同じです。

---

# 6. `threading.Thread` と `ThreadPoolExecutor` の違い

違うのは、主に**スレッドや仕事の管理方法**です。

| 項目 | `threading.Thread` | `ThreadPoolExecutor` |
|---|---|---|
| スレッド生成 | 自分で `Thread()` を作成 | Executorがスレッドプールを管理 |
| 処理開始 | `thread.start()` | `executor.submit()` |
| 終了待ち | `thread.join()` | `future.result()` やExecutorの終了処理 |
| 実行結果 | 自分で管理 | `Future` から取得できる |
| 例外 | 自分で扱う必要がある | `Future` から取得できる |
| 実行中処理への停止要求 | `Event` が利用できる | `Event` が利用できる |
| 実行前タスクのキャンセル | 通常は自分で管理 | `Future.cancel()` が利用できる |

`ThreadPoolExecutor` では `Future` が存在することが大きな違いです。

---

# 7. `Future.cancel()` と `Event` の違い

`ThreadPoolExecutor` では、

```python
future = executor.submit(worker)
```

によって `Future` オブジェクトが返されます。

そして、

```python
future.cancel()
```

というメソッドがあります。

ここで、

> `cancel()` があるなら Event は不要なのでは？

と思うかもしれません。

しかし、`Future.cancel()` と `Event` は役割が異なります。

## 7.1 `Future.cancel()`

`Future.cancel()` は、**まだ実行が開始されていない仕事をキャンセルする**ために利用できます。

例えば、スレッドプールの全ワーカーが使用中で、ある仕事が実行待ちになっている場合、その仕事はキャンセルできる可能性があります。

```python
future.cancel()
```

が成功すれば、その仕事は実行されません。

## 7.2 すでに実行中の場合

一方、ワーカーがすでに仕事を開始している場合、基本的に、

```python
future.cancel()
```

ではその処理を停止できません。

整理すると次のようになります。

```text
まだ実行されていない仕事
        ↓
Future.cancel()
        ↓
キャンセル可能

すでに実行中の仕事
        ↓
Future.cancel()
        ↓
基本的に止められない

すでに実行中の仕事を終了させたい
        ↓
threading.Event
        ↓
worker自身が終了する
```

この違いは非常に重要です。

---

# 8. Event は `ThreadPoolExecutor` 専用ではない

`threading.Event` は `ThreadPoolExecutor` の機能ではありません。

名前のとおり、Python標準ライブラリの、

```python
threading
```

モジュールに属する機能です。

したがって、

```python
threading.Thread
```

でも、

```python
ThreadPoolExecutor
```

でも利用できます。

より本質的には、Event は、

> 複数のスレッド間で「ある状態になった」「ある出来事が発生した」という合図を共有する仕組み

です。

「停止要求」は Event の代表的な利用方法の一つです。

---

# 9. 単純な bool 変数ではなく Event を使う理由

考え方だけなら、次のような変数でも停止フラグを作れそうに見えます。

```python
stop_requested = False
```

停止するときに、

```python
stop_requested = True
```

とする方法です。

しかし、マルチスレッド間で通知を行うのであれば、用途が明確で同期機構として設計されている `threading.Event` を使う方が適切です。

Event には次のような専用メソッドがあります。

```python
set()
clear()
is_set()
wait()
```

## 主なメソッド

### `set()`

Event をON状態にします。

```python
stop_event.set()
```

停止用途では「停止要求を出す」という意味になります。

### `is_set()`

現在セットされているか確認します。

```python
if stop_event.is_set():
    ...
```

セット済みなら `True`、そうでなければ `False` を返します。

### `clear()`

Event をOFF状態へ戻します。

```python
stop_event.clear()
```

再利用する設計では使うことがあります。

ただし、停止専用の Event では、一度 `set()` したらそのまま終了する設計も多くあります。

### `wait()`

Event がセットされるまで待機できます。

```python
stop_event.wait()
```

また、タイムアウトを指定できます。

```python
stop_event.wait(timeout=1)
```

これは定周期処理で非常に便利です。

---

# 10. `time.sleep()` と `Event.wait()` の違い

例えば、1秒周期で処理するワーカーを考えます。

```python
while not stop_event.is_set():
    do_something()
    time.sleep(1)
```

この方法でも動作します。

しかし、`time.sleep(1)` の最中に、

```python
stop_event.set()
```

されても、sleep が終わるまではワーカーが停止要求を確認できません。

最大で約1秒、終了が遅れる可能性があります。

そこで、次のように書けます。

```python
while not stop_event.is_set():
    do_something()

    if stop_event.wait(timeout=1):
        break
```

`wait(timeout=1)` は、単純に1秒待つのではありません。

次のどちらかが発生するまで待ちます。

```text
1. 1秒経過する

または

2. Eventがset()される
```

そのため、待機開始から0.2秒後に、

```python
stop_event.set()
```

された場合、残り0.8秒を待たずに `wait()` が解除されます。

これは、PLC監視、定周期データ収集、画面キャプチャなどの「一定時間待ちながら、終了要求には素早く反応したい処理」と非常に相性がよい方法です。

---

# 11. Event を使っても「瞬時に止まる」とは限らない

Event を使えば、どんな処理でも即座に停止できるわけではありません。

例えば次の処理を考えます。

```python
while not stop_event.is_set():
    very_long_function()
```

`very_long_function()` に30秒かかる場合、その関数を実行している途中で Event がセットされても、通常は関数から戻るまで次の `is_set()` を確認できません。

```text
Event確認
   ↓
長い処理開始
   ↓
   ↓ ← この途中で stop_event.set()
   ↓
長い処理終了
   ↓
Event確認
   ↓
停止
```

したがって、停止への応答性を高くしたい場合は、長時間処理の途中でも適切な場所で Event を確認できる設計にすることが重要です。

---

# 12. `join()` の役割

`threading.Thread` では、停止要求を出した後によく次のようにします。

```python
stop_event.set()
thread.join()
```

ここで注意したいのは、

```python
thread.join()
```

もスレッドを停止する命令ではないということです。

`join()` の意味は、

> 対象スレッドの処理が終了するまで、呼び出した側が待つ

です。

したがって、

```python
stop_event.set()
thread.join()
```

は、

```text
stop_event.set()
        ↓
「終了してください」と通知
        ↓
workerが通知を確認
        ↓
worker終了
        ↓
thread.join() の待機解除
```

という流れです。

`set()` と `join()` は役割が異なります。

- `set()`：停止要求を通知する
- `join()`：実際に終了するまで待つ

と覚えると分かりやすいです。

---

# 13. `ThreadPoolExecutor` では Future で処理状態を管理できる

`ThreadPoolExecutor` では、

```python
future = executor.submit(worker, stop_event)
```

のように `Future` を受け取れます。

Futureを使うことで、

- 完了したか
- キャンセルされたか
- 結果は何か
- 例外が発生したか

などを管理できます。

例えば、

```python
future.done()
```

で処理が完了状態か確認できます。

また、

```python
future.result()
```

を呼び出すと、処理結果を取得すると同時に、まだ完了していなければ完了まで待機します。

ただし、これらは Event による停止要求とは別の役割です。

```text
Event
    ↓
実行中のworkerへ停止要求を伝える

Future
    ↓
投入した仕事の状態・結果・例外などを管理する
```

と分けて考えると整理しやすくなります。

---

# 14. `threading.Thread` と `ThreadPoolExecutor` の停止処理の比較

## `threading.Thread`

```python
stop_event = threading.Event()

thread = threading.Thread(
    target=worker,
    args=(stop_event,),
)

thread.start()

# 停止要求
stop_event.set()

# 終了待ち
thread.join()
```

## `ThreadPoolExecutor`

```python
stop_event = threading.Event()

with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(
        worker,
        stop_event,
    )

    # 停止要求
    stop_event.set()

    # 必要なら完了を待つ
    future.result()
```

停止要求そのものは、どちらも、

```python
stop_event.set()
```

です。

違うのは、その処理を管理する仕組みです。

---

# 15. 実用的な考え方

長時間動作するバックグラウンド処理では、次の形を基本パターンとして覚えておくと便利です。

```python
def worker(stop_event):
    while not stop_event.is_set():
        # 1回分の処理
        do_something()

        # 次の周期まで待つ。
        # 停止要求が来た場合はすぐに解除される。
        if stop_event.wait(timeout=1):
            break
```

この形なら、

1. Event がセットされていなければ処理する
2. 1回分の処理が終わったら次周期まで待つ
3. 待機中に停止要求が来ればすぐ反応する
4. ループを抜けて正常終了する

という分かりやすい構造になります。

---

# 16. よくある誤解

## 誤解1：`Event.set()` がスレッドを強制終了する

違います。

```python
stop_event.set()
```

は Event の状態をセットするだけです。

ワーカー側が Event を確認しなければ、処理はそのまま継続します。

---

## 誤解2：`thread.join()` がスレッドを終了させる

違います。

`join()` はスレッドが終了するまで待つだけです。

---

## 誤解3：`Future.cancel()` なら実行中の処理も停止できる

基本的にはできません。

`Future.cancel()` は、まだ開始していない仕事をキャンセルするときに使います。

実行開始済みの処理を協調的に終了させる場合は `Event` などの仕組みを用意します。

---

## 誤解4：`Thread` と `ThreadPoolExecutor` では Event の使い方がまったく違う

基本的な考え方は同じです。

どちらの場合も、Event をワーカーと共有し、ワーカー自身が停止要求を確認して終了します。

---

# 17. 最重要ポイント

今回の内容で最も重要なのは、次の理解です。

```text
× Eventがスレッドを強制停止する

○ Eventで「停止要求」を伝える
        ↓
  ワーカーが要求を確認する
        ↓
  ワーカー自身が break / return する
        ↓
  ワーカーの処理が終了する
```

この考え方は、

```python
threading.Thread
```

でも、

```python
ThreadPoolExecutor
```

でも同じです。

`ThreadPoolExecutor` では追加で `Future` が使えるため、実行前タスクのキャンセルや処理結果・例外・完了状態の管理がしやすくなっています。

しかし、**すでに実行中の仕事を安全に終了させる場合は、Eventなどを使った協調的な停止が基本**です。

---

# 18. まとめ

今回の内容を短く整理すると、次のようになります。

```text
threading.Event
    │
    ├─ set()      → 合図をONにする
    ├─ clear()    → 合図をOFFに戻す
    ├─ is_set()   → 合図がONか確認する
    └─ wait()     → 合図を待つ
```

スレッド停止では、

```text
メインスレッド
    │
    │ stop_event.set()
    ↓
停止要求
    ↓
ワーカースレッド
    │
    │ stop_event.is_set()
    ↓
停止要求を検知
    ↓
break / return
    ↓
正常終了
```

となります。

そして、

```text
threading.Thread
        ↓
実行中の処理を終了したい
        ↓
Eventによる協調的な停止

ThreadPoolExecutor
        ↓
実行中の処理を終了したい
        ↓
Eventによる協調的な停止

ThreadPoolExecutor
        ↓
まだ開始していない仕事を取り消したい
        ↓
Future.cancel()
```

と整理すると非常に分かりやすくなります。

**「スレッドを外部から止める」のではなく、「停止要求を送り、スレッド自身に安全に終了してもらう」**。

これが Python のマルチスレッド処理における重要な設計思想です。
