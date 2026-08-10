# Python `threading.Thread` の `daemon` 完全ガイド

## 1. はじめに

Python の `threading.Thread` では、スレッドを作成するときに `daemon` を指定できます。

```python
thread = threading.Thread(
    target=self._receive_and_save,
    args=(config,),
    daemon=True,
)
```

`daemon` は単なる補助オプションではありません。

これは、

> **そのスレッドが動作中でも、Python プログラム全体を終了してよいか**

を決める重要な設定です。

特に、

- PLC 通信
- SQLite へのデータ保存
- ファイル書き込み
- ログ保存
- バックグラウンド監視
- 定期処理

などをスレッドで実行する場合、`daemon=True` と `daemon=False` の違いを理解せずに使うと、プログラム終了時に処理が途中で打ち切られる可能性があります。

この資料では、`daemon` の意味を基礎から丁寧に整理します。

---

# 2. まず結論

最初に最も重要な違いをまとめます。

```text
daemon=False
    ↓
このスレッドが動作している限り、
Python プロセスは終了しない


daemon=True
    ↓
このスレッドしか残っていなければ、
Python プロセスは終了できる
```

つまり、

```text
最後まで確実に終わらせたい処理
    ↓
daemon=False


アプリ終了時に途中で終わっても構わない補助処理
    ↓
daemon=True
```

という考え方が基本です。

---

# 3. `daemon` とは何か

`threading.Thread` のコンストラクタでは、次のように指定できます。

```python
thread = threading.Thread(
    target=worker,
    daemon=True,
)
```

または、

```python
thread = threading.Thread(
    target=worker,
    daemon=False,
)
```

`daemon` は、そのスレッドを

- デーモンスレッド
- 非デーモンスレッド

のどちらとして扱うかを指定します。

---

# 4. デーモンスレッドと非デーモンスレッド

## 4.1 非デーモンスレッド

```python
daemon=False
```

のスレッドです。

このスレッドが動作している間、Python は通常プロセスを終了しません。

例えば、

```python
import threading
import time


def worker():
    print("処理開始")
    time.sleep(5)
    print("処理終了")


thread = threading.Thread(
    target=worker,
    daemon=False,
)

thread.start()

print("メイン処理終了")
```

実行イメージは、

```text
workerスレッド開始
        │
        ├── 処理開始
        │
メインスレッド
        │
        └── メイン処理終了
                │
                ↓
        workerはまだ動作中
                │
                ↓
        Pythonは終了しない
                │
        5秒経過
                │
        worker処理終了
                │
                ↓
        Pythonプロセス終了
```

となります。

---

## 4.2 デーモンスレッド

```python
daemon=True
```

のスレッドです。

```python
thread = threading.Thread(
    target=worker,
    daemon=True,
)
```

この場合、

> デーモンスレッドしか残っていなければ、Python はプロセスを終了できます。

先ほどと同じ処理でも、

```python
import threading
import time


def worker():
    print("処理開始")
    time.sleep(5)
    print("処理終了")


thread = threading.Thread(
    target=worker,
    daemon=True,
)

thread.start()

print("メイン処理終了")
```

では、

```text
workerスレッド開始
        │
        ├── 処理開始
        │
メインスレッド
        │
        └── メイン処理終了
                │
                ↓
        非デーモンスレッドが残っていない
                │
                ↓
        Pythonプロセス終了
                │
                ×
        workerの処理は途中でも終了する可能性
```

となります。

この違いが `daemon` の本質です。

---

# 5. 「メインスレッドが終了したら即終了」ではない

ここは誤解しやすいポイントです。

よく、

> `daemon=True` にすると、メインスレッド終了時にデーモンスレッドも終了する

と説明されます。

概念的には近いですが、より正確には、

> **非デーモンスレッドがすべて終了し、デーモンスレッドしか残っていなければ、Python インタプリタは終了できる**

という動作です。

例えば、

```text
MainThread              非デーモン
Worker-A                非デーモン
Worker-B                デーモン
```

という状態なら、`MainThread` が終了しても `Worker-A` が動いているため、Python はまだ終了しません。

```text
MainThread   終了
Worker-A     動作中
Worker-B     動作中
```

この場合、

```text
Worker-A が非デーモン
        ↓
Pythonは終了しない
```

です。

その後 `Worker-A` が終了し、

```text
Worker-B（daemon=True）
```

だけになった時点で Python は終了できます。

---

# 6. `daemon=True` は「安全に終了してくれる」という意味ではない

これが最も重要な注意点です。

```python
daemon=True
```

を、

> アプリ終了時にスレッドもきれいに終了させてくれる機能

と考えてはいけません。

むしろ、

> **そのスレッドの完了を待たずに Python を終了してよい**

という意味です。

したがって、処理の途中で終了する可能性があります。

---

# 7. 保存処理で `daemon=True` が危険な理由

例えば、

```python
def receive_and_save():
    data = receive_from_plc()
    save_to_database(data)
```

という処理を考えます。

これを、

```python
thread = threading.Thread(
    target=receive_and_save,
    daemon=True,
)
```

で動かしているとします。

処理途中でアプリが終了すると、

```text
PLCからデータ受信
        │
        ↓
データ変換
        │
        ↓
SQLite書き込み開始
        │
        ↓
    ← このタイミングでメイン終了
        │
        ×
Pythonプロセス終了
```

となる可能性があります。

つまり、

- DBへの書き込み途中
- ファイルへの保存途中
- ログ出力途中
- 通信処理途中
- 後処理未実行

などの状態で終了する可能性があります。

---

# 8. 今回の `_receive_and_save` で考える

例えば次のコードです。

```python
thread = threading.Thread(
    target=self._receive_and_save,
    args=(config,),
    name=f"{config.name}-receiver",
    daemon=True,
)

thread.start()
```

名前から考えると、

```text
_receive_and_save
        │
        ├── PLCからデータ受信
        │
        ├── データ処理
        │
        └── SQLite等へ保存
```

という重要処理である可能性があります。

この場合、

```python
daemon=True
```

を使うかどうかは、

> **アプリ終了時に、この処理が途中で打ち切られてもよいか**

で判断します。

---

# 9. `daemon=False` が向いている処理

次のような処理は、基本的に最後まで終わらせたい処理です。

```text
PLCから受信したデータの保存
SQLiteへの登録
ファイル保存
CSV出力
重要なログ保存
バックアップ
データ変換結果の確定
装置への重要コマンド送信
```

このような場合は、

```python
daemon=False
```

が自然です。

例えば、

```python
thread = threading.Thread(
    target=self._receive_and_save,
    args=(config,),
    name=f"{config.name}-receiver",
    daemon=False,
)
```

とします。

これなら `_receive_and_save()` が実行中である間は Python プロセスが終了しません。

---

# 10. `daemon=True` が向いている処理

一方で、

> アプリケーション終了時に一緒に終了して構わない

という補助的な処理には `daemon=True` が便利です。

例えば、

```text
定期的な状態表示
簡易監視
UI補助処理
一定間隔の情報更新
キャッシュ更新
終了しても失われるデータがない監視ループ
```

などです。

例：

```python
def monitor():
    while True:
        print("監視中...")
        time.sleep(1)


thread = threading.Thread(
    target=monitor,
    daemon=True,
)

thread.start()
```

この監視処理は、

> アプリケーション本体が終了したら監視も不要

という性質なので `daemon=True` が自然です。

---

# 11. `daemon=True` と無限ループ

`daemon=True` は無限ループ型の補助スレッドでよく使われます。

```python
def monitor():
    while True:
        check_status()
        time.sleep(1)
```

もしこれを、

```python
daemon=False
```

にすると、メイン処理が終了してもこの無限ループが残ります。

```text
メイン処理終了
      │
      ↓
monitorは無限ループ
      │
      ↓
Pythonが終了できない
```

となります。

このような場合、

```python
daemon=True
```

なら、

```text
メイン処理終了
      │
      ↓
デーモンスレッドしか残っていない
      │
      ↓
Python終了
```

となるため便利です。

ただし、重要な後処理があるなら、単純なデーモンスレッドよりも終了通知を使った設計の方が安全です。

---

# 12. より安全なのは「終了要求を出して正常終了させる」設計

重要なアプリでは、

```python
daemon=True
```

に頼って強制的に終了させるより、

> スレッドへ終了要求を送り、自分で正常終了させる

設計が安全です。

その代表が、

```python
threading.Event
```

です。

---

# 13. `threading.Event` を使った安全な終了

例：

```python
import threading
import time


stop_event = threading.Event()


def worker():
    while not stop_event.is_set():
        print("処理中...")
        time.sleep(1)

    print("終了処理を実行")
```

スレッドを開始します。

```python
thread = threading.Thread(
    target=worker,
    daemon=False,
)

thread.start()
```

終了したいときに、

```python
stop_event.set()
```

とします。

すると、

```text
メインスレッド
      │
      │ stop_event.set()
      ↓
終了要求
      │
      ↓
worker
      │
      ├── ループ終了
      ├── 後処理
      └── スレッド終了
```

という正常終了ができます。

---

# 14. `join()` と組み合わせる

さらに、

```python
thread.join()
```

を使うことで、スレッドの終了を明示的に待てます。

```python
stop_event.set()
thread.join()
```

流れは、

```text
終了要求
   │
   ↓
stop_event.set()
   │
   ↓
workerが終了処理
   │
   ↓
thread終了
   │
   ↓
join()から戻る
   │
   ↓
メイン処理終了
```

となります。

これは非常に安全な終了方法です。

---

# 15. `daemon=False + Event + join()` の考え方

重要なバックグラウンド処理では、

```text
daemon=False
+
threading.Event
+
join()
```

という組み合わせが分かりやすく安全です。

例えば、

```python
import threading


class Receiver:

    def __init__(self):
        self.stop_event = threading.Event()

    def receive_loop(self):
        while not self.stop_event.is_set():
            self.receive_data()

        self.cleanup()

    def stop(self):
        self.stop_event.set()
```

開始：

```python
thread = threading.Thread(
    target=receiver.receive_loop,
    daemon=False,
)

thread.start()
```

終了：

```python
receiver.stop()
thread.join()
```

これなら、

```text
突然打ち切る
```

のではなく、

```text
終了要求
    ↓
現在処理を整理
    ↓
後処理
    ↓
正常終了
```

という設計にできます。

---

# 16. `daemon` のデフォルト値

`daemon` を省略した場合、

```python
thread = threading.Thread(
    target=worker,
)
```

生成されたスレッドは、

> **作成したスレッドの daemon 状態を引き継ぎます。**

通常のメインスレッドは、

```python
daemon=False
```

です。

そのため、普通にメインスレッドから作成すると、

```python
thread = threading.Thread(
    target=worker,
)
```

は通常、

```python
daemon=False
```

になります。

実用上は、

> daemon を指定しなければ通常は非デーモンスレッド

と覚えてよいですが、厳密には「親スレッドから引き継ぐ」です。

---

# 17. daemon 状態を確認する

スレッドの `daemon` は確認できます。

```python
print(thread.daemon)
```

例えば、

```python
thread = threading.Thread(
    target=worker,
    daemon=True,
)

print(thread.daemon)
```

なら、

```text
True
```

です。

現在実行中のスレッドについても確認できます。

```python
current = threading.current_thread()

print(current.name)
print(current.daemon)
```

---

# 18. `daemon` は `start()` 前に決める

`daemon` の設定はスレッド開始前に行う必要があります。

通常はコンストラクタで指定するのが分かりやすいです。

```python
thread = threading.Thread(
    target=worker,
    daemon=True,
)
```

また、

```python
thread = threading.Thread(
    target=worker,
)

thread.daemon = True
thread.start()
```

という指定もできます。

ただし、開始後に変更しようとするのは不適切です。

```python
thread.start()

thread.daemon = True
```

のような使い方はできません。

そのため、

> daemon はスレッドの基本的な性質なので、start() 前に決める

と覚えておくと分かりやすいです。

---

# 19. `daemon=True` はスレッドを停止する命令ではない

これも大切です。

```python
daemon=True
```

は、

```text
スレッドを停止する
```

という意味ではありません。

通常動作中は、デーモンスレッドも普通のスレッドと同じように動きます。

```python
thread = threading.Thread(
    target=worker,
    daemon=True,
)

thread.start()
```

なら `worker()` は普通に実行されます。

違いが現れるのは、

> Python プロセスを終了できるかどうか

という場面です。

したがって、

```text
daemon=True
    ≠
スレッド停止機能
```

です。

---

# 20. `daemon=True` は「低優先度」でもない

OS の処理優先度とは関係ありません。

```python
daemon=True
```

だから、

```text
CPU使用率が低くなる
優先順位が下がる
処理速度が遅くなる
```

ということはありません。

`daemon` が決めるのは、

> Python の終了を妨げるスレッドかどうか

です。

---

# 21. `daemon=True` と `join()` は両立できる

デーモンスレッドでも、

```python
thread.join()
```

は使用できます。

例えば、

```python
thread = threading.Thread(
    target=worker,
    daemon=True,
)

thread.start()
thread.join()
```

とすると、メインスレッド側が `worker` の終了を待ちます。

そのため、この場合は結果として `worker` が終了するまでメインスレッドも終了しません。

つまり、

```text
daemon=True
```

は、

> 必ず途中で終了する

という意味ではありません。

あくまで、

> 他に非デーモンスレッドがなくなった場合、Python はこのスレッドの終了を待つ義務がない

という意味です。

---

# 22. 判断のための実践フローチャート

スレッドを作るときは次のように判断すると分かりやすいです。

```text
この処理はアプリ終了時に
途中で終わってもよい？
        │
        ├── YES
        │     ↓
        │  daemon=True を検討
        │
        └── NO
              ↓
           daemon=False
              │
              ↓
        必要なら Event + join()
```

もう少し具体的には、

```text
データ保存？
重要通信？
ファイル更新？
バックアップ？
DB書き込み？
      │
      └── YES
            ↓
         daemon=False


単なる監視？
定期表示？
補助的な更新？
失われても問題ない？
      │
      └── YES
            ↓
         daemon=True を検討
```

---

# 23. PLCアプリでのおすすめ

PLCアプリでは、処理を次のように分けて考えると安全です。

## PLC監視ループ

例えば、

```python
while True:
    request = read_plc_request()
```

のような監視処理です。

この処理そのものは、アプリ終了時に停止して構わない場合があります。

そのため、

```python
daemon=True
```

が候補になります。

ただし、接続終了処理などを確実に行いたいなら `Event` を使った正常終了の方が適しています。

---

## PLCからのデータ受信

受信途中で終了すると、

```text
データ欠損
```

につながる可能性があります。

したがって、

```python
daemon=False
```

を優先して検討します。

---

## SQLiteへのデータ保存

保存途中で終了してほしくない処理です。

そのため、

```python
daemon=False
```

が自然です。

---

# 24. `_receive_and_save` ならどう考えるか

今回の例：

```python
thread = threading.Thread(
    target=self._receive_and_save,
    args=(config,),
    name=f"{config.name}-receiver",
    daemon=True,
)

thread.start()
```

`_receive_and_save` が、

```text
PLCからデータ受信
      ↓
データ確認
      ↓
SQLiteへ保存
```

という処理なら、

```python
daemon=False
```

を検討する価値があります。

理由は、

> 一度受信処理を開始したなら、アプリ終了操作が発生しても、そのデータだけは最後まで保存したい

という設計の方が安全だからです。

例えば、

```python
thread = threading.Thread(
    target=self._receive_and_save,
    args=(config,),
    name=f"{config.name}-receiver",
    daemon=False,
)
```

とすれば、この受信・保存スレッドが終了するまでは Python プロセスが終了しません。

---

# 25. ただし `daemon=False` だけでも完全ではない

`daemon=False` にしたからといって、

> すべての終了問題が自動的に解決する

わけではありません。

例えば worker が、

```python
while True:
    ...
```

という無限ループなら、永遠に Python が終了しなくなる可能性があります。

そのため重要なのは、

```text
daemon=False
       +
終了条件
       +
必要なら Event
       +
join()
```

です。

---

# 26. 「止まらないアプリ」と「途中で切れるアプリ」の中間を目指す

設計上ありがちな両極端は、

## daemon=False だけ

```text
終了しようとしてもスレッドが終わらず、
アプリが閉じない
```

## daemon=True だけ

```text
アプリはすぐ閉じるが、
重要処理が途中で切れる可能性
```

です。

理想は、

```text
終了要求
   ↓
新しい仕事を受け付けない
   ↓
現在処理中の仕事を完了
   ↓
後処理
   ↓
スレッド終了
   ↓
アプリ終了
```

という流れです。

これを実現するために、

```text
Event
join()
shutdown()
```

などを使います。

---

# 27. ThreadPoolExecutor との関係

`ThreadPoolExecutor` を使う場合は、通常 `shutdown()` によってスレッドの終了を管理します。

```python
executor.shutdown(wait=True)
```

とすると、実行中のタスクが完了するのを待って終了できます。

考え方としては、

```text
threading.Thread
    ↓
Event / join() で終了管理


ThreadPoolExecutor
    ↓
shutdown() で終了管理
```

と考えると分かりやすいです。

重要な処理ほど、

> daemon に任せて打ち切る

のではなく、

> 明示的に終了を管理する

方が安全です。

---

# 28. 覚えておきたい誤解

## 誤解1

```text
daemon=True
= バックグラウンドで実行
```

厳密には違います。

通常の非デーモンスレッドもバックグラウンドで並行実行できます。

---

## 誤解2

```text
daemon=True
= 安全に自動終了
```

違います。

処理途中でも Python プロセスが終了できる、という意味です。

---

## 誤解3

```text
daemon=True
= CPU優先度が低い
```

違います。

処理優先度とは関係ありません。

---

## 誤解4

```text
daemon=False
= join() と同じ
```

違います。

`daemon=False` は、

```text
そのスレッドが残っていればPython全体を終了しない
```

という性質です。

`join()` は、

```text
この位置で明示的にスレッド終了を待つ
```

という命令です。

---

# 29. 早見表

| 項目 | `daemon=False` | `daemon=True` |
|---|---|---|
| Python終了時 | スレッド終了を待つ | 終了を待たなくてよい |
| 処理途中で終了する可能性 | 通常は低い | ある |
| 重要データ保存 | 向いている | 注意が必要 |
| SQLite書き込み | 向いている | 注意が必要 |
| PLC受信処理 | 向いていることが多い | 要件次第 |
| 単純な監視 | 使用可能 | 向いている |
| 無限監視ループ | 終了管理が必要 | 簡易用途では便利 |
| Eventとの併用 | 非常に有効 | 使用可能 |
| join() | 使用可能 | 使用可能 |

---

# 30. 実践上のおすすめルール

まず次のルールで考えると安全です。

### ルール1

重要なデータを扱うスレッドは、

```python
daemon=False
```

を基本にする。

### ルール2

終了時に失われても問題ない補助処理なら、

```python
daemon=True
```

を検討する。

### ルール3

`daemon=True` を、

```text
スレッドを安全に停止する機能
```

とは考えない。

### ルール4

本格的なアプリでは、

```text
threading.Event
join()
```

などを使って明示的に終了させる。

### ルール5

`daemon` を決めるときは、

> **「アプリ終了時に、この処理が途中で打ち切られても本当に問題ないか？」**

と考える。

---

# 31. 最重要ポイント

`daemon` の意味を一言で覚えるなら、

```text
daemon=False
    ↓
「この仕事が終わるまでPythonを終了させない」


daemon=True
    ↓
「この仕事が残っていてもPythonを終了してよい」
```

です。

特に、

```python
daemon=True
```

は、

> 便利な終了機能

ではなく、

> **そのスレッドを待たずにプロセス終了してよいという許可**

だと理解することが重要です。

PLC通信やSQLite保存のようにデータを確実に残したい処理では、安易に `daemon=True` を使用せず、

```text
daemon=False
+
正常な終了条件
+
threading.Event
+
join()
```

という設計を優先して検討するのが安全です。

---

# 32. 今回のコードに対する判断

元のコード：

```python
thread = threading.Thread(
    target=self._receive_and_save,
    args=(config,),
    name=f"{config.name}-receiver",
    daemon=True,
)

thread.start()
```

ここで `_receive_and_save()` が重要なデータを受信して保存する処理なら、

```python
daemon=True
```

を採用する前に、

```text
アプリを閉じた瞬間、
受信・保存途中の処理を打ち切ってもよいか？
```

を確認する必要があります。

もし答えが、

```text
NO
```

なら、

```python
daemon=False
```

を基本にし、必要に応じて `Event` や `join()` を使って正常終了を設計する方が適切です。

これが `daemon` を使ううえで最も重要な判断基準です。
