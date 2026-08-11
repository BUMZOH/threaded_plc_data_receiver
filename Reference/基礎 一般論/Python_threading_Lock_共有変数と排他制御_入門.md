# Python `threading.Lock` 入門
## 共有変数の読み取り・書き込みと安全な排他制御

## 1. はじめに

マルチスレッドでは、複数のスレッドが同じデータや状態を参照・変更することがあります。このようなデータを**共有状態（shared state）**と考えます。

今回のPLC監視アプリでは、たとえば次があります。

```python
self.monitor_thread
```

これは監視スレッドの状態を管理し、開始処理・停止処理から参照や変更が行われます。このような共有状態を安全に扱う代表的な仕組みが `threading.Lock` です。

今回の最重要ポイントは次の2つです。

> **Lockは特定の変数そのものをロックする仕組みではない。**

> **共有変数は書き換えるときだけでなく、読み取って判断するときにもLockが必要になる場合がある。**

---

## 2. Lockの基本

```python
import threading

self.lock = threading.Lock()
```

使用時は、

```python
with self.lock:
    # 同時に実行させたくない処理
    ...
```

とします。

```text
with self.lock:
        ↓
Lock取得
        ↓
処理を実行
        ↓
withを抜ける
        ↓
Lock解放
```

---

## 3. Lockは「変数をロックする」のではない

たとえば、

```python
with self.lock:
    self.monitor_thread = None
```

と書いても、Pythonが `self.monitor_thread` という変数そのものに鍵を掛けているわけではありません。

Pythonから見れば、

```text
self.lockを取得
    ↓
withブロックを実行
    ↓
self.lockを解放
```

だけです。

**何を守るためにそのLockを使うかはプログラマが決めます。**

---

## 4. 同じLockを使うというルール

`self.monitor_thread` を共有状態として守るなら、それを扱う複数の処理で同じ `self.lock` を使います。

```text
Thread A                     Thread B

with self.lock:              with self.lock:
    共有状態を操作               共有状態を操作
```

Thread AがLockを取得している間、Thread Bは同じLockを取得できず待機します。

一方、別スレッドがLockを使わず、

```python
self.monitor_thread = None
```

と書けば普通に変更できます。

したがってLockとは、

> **「この共有状態へアクセスするときは、みんな同じ鍵を使う」**

というプログラム上の約束です。

---

## 5. 今回の `stop_monitoring()`

```python
def stop_monitoring(self) -> dict[str, str]:
    """PLC監視を停止する。"""
    with self.lock:
        monitor_thread = self.monitor_thread
        self.receiver.stop()

    if monitor_thread is not None:
        monitor_thread.join()

    with self.lock:
        if self.monitor_thread is monitor_thread:
            self.monitor_thread = None

    return {
        "status": "stopped",
        "message": "停止中",
    }
```

全体の意味は、

```text
現在の監視Threadを覚える
    ↓
停止要求を出す
    ↓
Threadが終了するまで待つ
    ↓
監視Threadの登録をNoneへ戻す
```

です。

---

## 6. `monitor_thread` と `self.monitor_thread`

```python
monitor_thread = self.monitor_thread
```

左側と右側は性質が違います。

```text
monitor_thread
    ↓
このメソッド内のローカル変数


self.monitor_thread
    ↓
オブジェクトが持つインスタンス変数
    ↓
複数スレッドから扱われる可能性がある共有状態
```

したがって、Lockで重要なのはローカル変数 `monitor_thread` を保護することではありません。

右辺の `self.monitor_thread` を含む**共有状態の扱い**を保護しています。

---

## 7. 「設定時だけLock」ではない

最初は、

```text
共有変数を書き換える
    ↓
Lockする
```

と考えがちです。

しかし、より正確には、

> **共有状態を読み取り、その結果を使って判断・処理するときにもLockが必要になる場合がある**

と考えます。

たとえば、

```python
if self.monitor_thread is not None:
    if self.monitor_thread.is_alive():
        ...
```

は、

```text
① monitor_threadは存在する？
② そのThreadは生きている？
③ それなら監視中と判断する
```

という一連の操作です。

途中で別スレッドが `self.monitor_thread` を変更すると、「最初に確認した状態」と「現在の状態」が食い違う可能性があります。

そこで、

```python
with self.lock:
    if (
        self.monitor_thread is not None
        and self.monitor_thread.is_alive()
    ):
        ...
```

として、存在確認から判断までを一つのまとまりとして扱います。

---

## 8. Lockの本質は「一連の操作を守る」

Lockを単なる「書き込み保護」と考えるのではなく、

> **共有状態に対する一連の操作の途中へ、同じLockを使う別スレッドを割り込ませないための仕組み**

と考えます。

```python
with self.lock:
    # 共有状態を読む
    # 確認する
    # 判断する
    # 必要なら変更する
```

読み取りも、その後の判断とセットなら保護対象になる場合があります。

---

## 9. 最初のLockは何をしているか

```python
with self.lock:
    monitor_thread = self.monitor_thread
    self.receiver.stop()
```

まず `self.monitor_thread` から今回停止対象とするThreadをローカル変数へ保持します。

次に `self.receiver.stop()` で停止要求を出します。

今回の `stop()` は概念的には、

```python
self.stop_event.set()
```

です。

`Event.set()` 自体を安全に呼ぶためだけに `self.lock` が必要なわけではありません。`threading.Event` はスレッド間通知のための仕組みです。

このLock区間は、

```text
停止対象Threadを取得
    ↓
監視処理へ停止要求を出す
```

という**停止開始の一連の操作**を、開始・停止などの別処理と競合しにくくするためにまとめている、と理解すると分かりやすいです。

---

## 10. `stop()` と `join()` の違い

```text
stop()
    ↓
「停止してください」と要求する

join()
    ↓
「実際に終了するまで待つ」
```

`stop()` はスレッドを強制終了する命令ではありません。

`stop_event` をセットし、

```python
while not self.stop_event.is_set():
```

という監視ループが自主的に終了するようにしています。

---

## 11. なぜ `join()` はLockの外なのか

`join()` はスレッドが終了するまで待つので、時間が掛かる可能性があります。

もしLock内で `join()` すると、その待ち時間中ずっと同じLockを必要とする別処理を待たせる可能性があります。

したがって、

```text
Lockが必要な短い処理
    ↓
Lock解放
    ↓
join()で待機
```

という構造にしています。

**Lockは必要最小限の時間だけ保持する**のが基本です。

---

## 12. ローカル変数へ退避する意味

```python
monitor_thread = self.monitor_thread
```

としておけば、Lockを解放したあとも、

```python
monitor_thread.join()
```

と、**今回停止対象として取得したThread**を待てます。

ローカル変数 `monitor_thread` 自体を他スレッドが書き換えるわけではないので、`join()` のためにLockを保持する必要はありません。

---

## 13. 最後にもう一度Lockする理由

```python
with self.lock:
    if self.monitor_thread is monitor_thread:
        self.monitor_thread = None
```

ここでは、

> 現在登録されているThreadが、今回自分が停止させたThreadと同じか？

を確認しています。

`is` は同じオブジェクトかどうかを確認します。

`join()` 中はLockを保持していないため、理屈上はその間に共有状態が変更される可能性があります。

```text
self.monitor_thread → Thread A
    ↓
Thread Aをローカル変数へ保存
    ↓
停止要求
    ↓
Lock解放
    ↓
Thread A.join()

    この間に状態が変わる

self.monitor_thread → Thread B
```

ここで無条件に `self.monitor_thread = None` とすると、Thread Bの登録まで消してしまう可能性があります。

そこで、

```python
if self.monitor_thread is monitor_thread:
```

と確認します。

---

## 14. シンプルな停止処理との比較

本質だけなら、

```python
self.receiver.stop()
monitor_thread.join()
self.monitor_thread = None
```

でも、

```text
停止要求
    ↓
終了待ち
    ↓
後片付け
```

という基本的な流れは表現できます。

元コードは、その周囲に、

```text
Lock
ローカル変数への退避
同一Threadの確認
```

を追加し、複数スレッドから操作された場合にも壊れにくいよう安全側に設計しています。

---

## 15. Lockが必要か考えるチェックポイント

```text
① このデータは複数スレッドから触る可能性がある？
        ↓
      YES

② 読み取り・変更の途中で
   別スレッドに状態を変えられると困る？
        ↓
      YES

③ 一連の処理をまとめて守る
        ↓
      Lock
```

特に、

```text
確認
 ↓
判断
 ↓
変更
```

のような複数ステップは注意します。

---

## 16. `with self.lock:` を使う理由

Lockは次のようにも書けます。

```python
self.lock.acquire()

try:
    ...
finally:
    self.lock.release()
```

しかし通常は、

```python
with self.lock:
    ...
```

の方が分かりやすく安全です。

`with` を抜けるとLockが解放されるので、`release()` の書き忘れを防げます。

---

## 17. よくある誤解

### 誤解1：Lockは変数に掛かる

```text
× self.monitor_threadという変数をロックする

○ self.lockというLockを取得し、
  その間に何を守るかをプログラマが決める
```

### 誤解2：書き込み時だけLockすればよい

必ずしもそうではありません。

```text
共有状態を読む
    ↓
確認する
    ↓
その結果で判断する
```

という一連の操作中に状態が変わると困るなら、読み取り側にもLockが必要です。

### 誤解3：Lockを長く持つほど安全

必要以上に長く保持すると、他のスレッドを待たせます。

```text
必要な共有状態の操作
    → Lock内

時間の掛かる処理
    → 可能ならLock外
```

と考えます。

---

## 18. 今回の最重要ポイント

### 1. Lockは変数をロックするものではない

```text
Lockオブジェクトを取得し、
どの処理区間を守るかは
プログラマが決める。
```

### 2. 読み取りでもLockが必要な場合がある

```text
共有状態を読む
    ↓
その結果で判断する
    ↓
次の処理をする
```

という一連の操作を途中で変更されたくない場合は、読み取り側もLockします。

### 3. Lockの本質は「一連の操作への割り込みを防ぐ」

```text
共有状態に対する

読む
確認する
判断する
変更する

という一連の操作を、
同じLockを使う他スレッドと同時実行させない。
```

---

## 19. 忘備録用チートシート

```text
【Lockとは？】

特定の変数に鍵を掛けるものではない。

self.lockという「鍵」を取得して、
どの処理区間を守るかはプログラマが決める。


【何を守る？】

共有状態に対する一連の操作。

・読む
・確認する
・判断する
・変更する


【書き込み時だけ？】

NO。

読み取った値を使って判断・処理するとき、
途中で共有状態が変わると困るなら
読み取り側にもLockが必要。


【ローカル変数は？】

monitor_thread = self.monitor_thread

左：
monitor_thread
→ ローカル変数

右：
self.monitor_thread
→ 共有状態

守りたいのは主に右側を含む共有状態の扱い。


【Lockは長く持つ？】

必要最小限にする。

時間の掛かるjoin()などは、
可能ならLockの外で実行する。


【今回のstop_monitoring】

Lock
 ↓
停止対象Threadを取得
 ↓
停止要求
 ↓
Lock解放
 ↓
join()で終了待ち
 ↓
Lock
 ↓
同じThreadか確認
 ↓
Noneへ戻す
 ↓
Lock解放
```

---

## 20. まとめ

`threading.Lock` を理解するときは、

> **「どの変数をロックしているのか？」**

ではなく、

> **「このLockを使って、どの共有状態に対する、どの一連の操作を守っているのか？」**

と考えることが重要です。

今回の `stop_monitoring()` では、`self.monitor_thread` という共有状態を安全に扱うために、読み取り・停止開始・確認・変更の重要な区間を `self.lock` で排他制御しています。

そして `join()` のように時間が掛かる可能性がある処理はLockの外へ出し、その間に状態が変化する可能性を考慮して、最後にもう一度Lockを取得して同じThreadか確認しています。

今後Lockを見たときは、

```text
何をロックしている？
```

ではなく、

```text
何の共有状態を守るために、
どの処理をひとまとまりにしている？
```

と読むと理解しやすくなります。
