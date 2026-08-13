# ThreadPoolExecutorでワーカースレッドの例外が見えなかったトラブル事例

## 1. はじめに

設備データ受信アプリの開発中、`ThreadPoolExecutor` で実行しているデータ受信処理が途中で停止しているように見えるトラブルが発生した。

PLCの要求デバイス監視自体は正常に動作していたため、アプリ全体が停止したわけではなかった。

しかし、PLCから実データを読み出す処理だけが進まず、さらにコンソールにも例外が表示されなかったため、

> 「データ受信スレッドの中で何が起きているのか分からない」

という状態になった。

原因を調べたところ、外部モジュール `kv_com` が古いままで、アプリ側から呼び出していた `read_devices_l()` が存在していなかった。

このトラブルは、Pythonの `ThreadPoolExecutor` と `Future` における例外処理を理解するうえで非常に重要な事例である。

---

## 2. 発生した状況

アプリでは、PLC通信ライブラリとして次の外部モジュールを使用している。

```python
from common_lib_mw import kv_com
```

アプリ側では、32ビット符号付き整数データを読み出すために次の関数を使用するよう変更していた。

```python
values = kv_com.read_devices_l(
    self.plc_ip_address,
    config.data_start_device,
    DATA_POINT_COUNT,
)
```

ところが、実行環境に配置されていた `kv_com.py` が古いバージョンのままであり、`read_devices_l()` がまだ実装されていなかった。

そのため、実際には次のような例外が発生する状況だったと考えられる。

```text
AttributeError:
module 'kv_com' has no attribute 'read_devices_l'
```

---

## 3. 表面上の症状

今回のトラブルでは、次のような状態になった。

- PLC要求デバイスの監視は正常に継続していた
- PLCからデータを受信する処理だけが完了しなかった
- アプリ全体は終了しなかった
- コンソールにも目立った例外が表示されなかった
- ユーザーから見ると「データ受信処理が止まっている」ように見えた

このため、最初はPLC通信そのものが停止しているのか、スレッドがデッドロックしているのか、データ読み出し関数が待ち続けているのか判断しにくい状態だった。

しかし実際には、

> ワーカースレッド内で例外が発生し、その例外が `Future` に保持されたまま誰にも確認されていなかった

ことが問題の中心だった。

---

## 4. 現在のThreadPoolExecutorの使い方

現在のアプリでは、データ受信要求を検出すると次のように処理をスレッドプールへ投入している。

```python
self.executor.submit(
    self._receive_and_save,
    config,
)
```

`executor.submit()` は、指定された関数をワーカースレッドで実行するよう依頼する。

重要なのは、`submit()` が処理結果そのものを返すのではなく、

```python
Future
```

オブジェクトを返すことである。

本来は次のように受け取ることができる。

```python
future = self.executor.submit(
    self._receive_and_save,
    config,
)
```

この `future` が、ワーカースレッドで実行されている処理の状態や結果を管理する。

---

## 5. Futureとは何か

`Future` は、

> 「別スレッドで実行している処理が、将来どのような結果になるか」

を表すオブジェクトである。

概念的には次のようになる。

```text
executor.submit()
        │
        ▼
   Futureを返す
        │
        ├── 実行待ち
        │
        ├── 実行中
        │
        ├── 正常終了
        │      └── 戻り値を保持
        │
        └── 異常終了
               └── 例外を保持
```

ワーカースレッドで例外が発生した場合、`ThreadPoolExecutor` はその例外を捨てるわけではない。

例外は `Future` の中に保存される。

---

## 6. 今回の処理の流れ

今回の状況を順番に整理すると、次のようになる。

```text
PLC要求デバイス ON
        │
        ▼
_check_request()
        │
        ▼
executor.submit()
        │
        ├─────────────── PLC監視スレッド
        │                     │
        │                     └── 監視処理を継続
        │
        ▼
ワーカースレッド
_receive_and_save()
        │
        ▼
kv_com.read_devices_l()
        │
        ▼
関数が存在しない
        │
        ▼
AttributeError 発生
        │
        ▼
_receive_and_save() の except では捕捉されない
        │
        ▼
Future が例外を保持
        │
        ▼
しかし Future を保存していない
        │
        ▼
誰も Future の例外を確認しない
        │
        ▼
コンソールに原因が見えない
```

これが今回の「停止しているように見えた」直接的な理由である。

---

## 7. なぜ_receive_and_save()のexceptで捕まらなかったのか

現在の `_receive_and_save()` では、次の例外を捕捉している。

```python
except (
    ConnectionError,
    OSError,
    RuntimeError,
    ValueError,
) as error:
    print(
        f"[{current_time()}] "
        f"{config.name}: 受信処理エラー: {error}"
    )
```

しかし、存在しない属性や関数を参照した場合に発生するのは、

```python
AttributeError
```

である。

現在の `except` の対象には `AttributeError` が含まれていない。

そのため今回の例外は `_receive_and_save()` の外へ伝播した。

通常の関数呼び出しなら、そのまま呼び出し元へ例外が伝わる。

しかし今回は `ThreadPoolExecutor` のワーカースレッド上で実行されているため、例外は `Future` に格納された。

---

## 8. ThreadPoolExecutorでは例外が消えたわけではない

ここは特に重要である。

今回、

> 「スレッド内の例外が無視された」

と考えるのは正確ではない。

正しくは、

> 「例外はFutureに保存されていたが、そのFutureを確認していなかった」

という状態である。

つまり例外そのものは存在している。

ただし、

```python
self.executor.submit(...)
```

の戻り値を受け取らずに捨ててしまうと、その `Future` に保存されている例外をアプリ側から確認する機会も失ってしまう。

---

## 9. future.result()の役割

`Future` の結果を取得する代表的な方法が、

```python
future.result()
```

である。

正常終了した場合は、ワーカースレッドで実行した関数の戻り値を取得できる。

例えば、

```python
def worker():
    return 100
```

を実行した場合、

```python
future = executor.submit(worker)

result = future.result()

print(result)
```

とすると、

```text
100
```

が取得できる。

一方、ワーカースレッド内で例外が発生していた場合は、`future.result()` を呼び出した場所で、その例外が再送出される。

例えば、

```python
def worker():
    raise ValueError("テストエラー")
```

の場合、

```python
future = executor.submit(worker)

future.result()
```

を実行すると、`result()` を呼び出した側で `ValueError` が発生する。

つまり、

```text
ワーカースレッド
    │
    ▼
例外発生
    │
    ▼
Futureが例外を保持
    │
    ▼
future.result()
    │
    ▼
呼び出し側で例外を再送出
```

という仕組みになっている。

---

## 10. 単純にfuture.result()を直後に呼ぶのはよくない

今回の問題を見て、

```python
future = self.executor.submit(
    self._receive_and_save,
    config,
)

future.result()
```

とすれば解決できるように見える。

しかし、現在のアプリではこの方法は適切ではない。

`future.result()` は、処理がまだ完了していない場合、

> 処理が完了するまでその場所で待機する

からである。

現在はPLC監視処理からデータ受信処理をスレッドプールへ投入している。

その直後に `future.result()` すると、

```text
PLC監視
   │
   ▼
submit()
   │
   ▼
future.result()
   │
   └── データ受信完了まで待機
```

となってしまう。

これでは、せっかくデータ受信処理を別スレッドへ分離しているメリットが小さくなる。

複数データ項目を並行処理する現在の設計とも相性が悪い。

---

## 11. 推奨方法：add_done_callback()で完了時に例外確認する

今回のアプリでは、

```python
Future.add_done_callback()
```

を利用する方法が適している。

例えば次のようにする。

```python
future = self.executor.submit(
    self._receive_and_save,
    config,
)

future.add_done_callback(
    self._handle_future
)
```

そして、完了時の処理を用意する。

```python
def _handle_future(self, future) -> None:
    try:
        future.result()

    except Exception as error:
        print(
            f"[{current_time()}] "
            f"受信スレッドで予期しないエラー: {error}"
        )
```

これにより、監視スレッドは待機せず、そのまま次の処理を継続できる。

```text
executor.submit()
        │
        ├──────────── PLC監視処理
        │                 │
        │                 └── そのまま継続
        │
        ▼
ワーカースレッド
        │
        ▼
_receive_and_save()
        │
        ├── 正常終了
        │      │
        │      ▼
        │  callback実行
        │      │
        │      ▼
        │  future.result()
        │      │
        │      └── 正常
        │
        └── 例外発生
               │
               ▼
           Futureが保持
               │
               ▼
           callback実行
               │
               ▼
           future.result()
               │
               ▼
           例外を再送出
               │
               ▼
           エラー表示
```

これなら、

- 並行処理を維持できる
- 監視スレッドを停止させない
- ワーカースレッドの予期しない例外を検知できる

という利点がある。

---

## 12. なぜexcept Exceptionだけにしないのか

今回のトラブルだけを見ると、`_receive_and_save()` を次のようにすれば簡単に見える。

```python
except Exception as error:
    print(error)
```

確かにこれでも `AttributeError` を捕捉できる。

しかし、アプリ設計としては注意が必要である。

例えば今回の

```python
AttributeError
```

は、

> PLC通信で通常発生する可能性があるエラー

ではなく、

> 必要な関数が存在しないというプログラム構成上の問題

である。

このようなプログラム上のバグまで通常の通信エラーと同じ扱いで捕捉してしまうと、重大な実装ミスに気付きにくくなる可能性がある。

そのため、

### 想定内の例外

例えば、

```python
ConnectionError
OSError
TimeoutError
RuntimeError
ValueError
```

などは、処理関数の中で個別に捕捉する。

### 想定外の例外

例えば、

```python
AttributeError
TypeError
NameError
```

など、通常はプログラムの不具合を疑うべき例外については、Future側まで伝播させて検知する。

という二段構えにすると、エラーの性質を区別しやすい。

---

## 13. 推奨する例外処理構成

今回のアプリでは、概念的には次の構成が分かりやすい。

```text
_receive_and_save()
        │
        ├── 想定内エラー
        │
        │     例:
        │     ConnectionError
        │     OSError
        │     RuntimeError
        │     ValueError
        │
        │        ↓
        │
        │   関数内部で処理
        │   ログ出力
        │
        └── 想定外エラー
              例:
              AttributeError
              TypeError
              NameError
                   │
                   ▼
              Futureまで伝播
                   │
                   ▼
              callback
                   │
                   ▼
              future.result()
                   │
                   ▼
              予期しないエラーとして通知
```

これにより、

> 通信時に起こり得る通常のエラー

と、

> プログラムそのものに問題がある可能性が高いエラー

を分けて扱える。

---

## 14. Futureで利用できる主な確認方法

Futureには `result()` 以外にも状態を確認するための機能がある。

### done()

```python
future.done()
```

処理が完了していれば `True` を返す。

正常終了でも異常終了でも、「処理が完了した」という意味では `True` になる。

つまり、

```python
future.done()
```

だけでは、

> 正常に終了したか

までは分からない。

---

### exception()

```python
future.exception()
```

処理中に発生した例外を取得できる。

正常終了の場合は `None` になる。

例えば、

```python
if future.done():
    error = future.exception()

    if error is not None:
        print(error)
```

のように確認できる。

---

### result()

```python
future.result()
```

正常終了なら戻り値を返す。

異常終了なら、ワーカースレッドで発生した例外を再送出する。

例外処理と組み合わせやすいため、

```python
try:
    future.result()
except Exception as error:
    ...
```

という形が分かりやすい。

---

## 15. as_completed()との違い

複数のFutureをまとめて管理している場合には、

```python
concurrent.futures.as_completed()
```

を使用する方法もある。

例えば、

```python
for future in as_completed(futures):
    try:
        future.result()
    except Exception as error:
        print(error)
```

とすると、完了したFutureから順番に処理できる。

ただし、現在のアプリは、

- PLC要求を常時監視する
- 要求が発生したタイミングで処理を投入する
- 処理の投入数が時間とともに変化する

という構成である。

このような常駐型アプリでは、Futureごとに完了時処理を登録する

```python
add_done_callback()
```

の方が自然で扱いやすい。

---

## 16. 今回の根本原因

今回のトラブルを整理すると、原因は一つではなく、次の複数の条件が重なっていた。

### 原因1：外部モジュールが古かった

アプリ側では、

```python
kv_com.read_devices_l()
```

を使用していたが、実行環境の `kv_com.py` にその関数が存在していなかった。

これが最初の原因である。

---

### 原因2：発生した例外がAttributeErrorだった

存在しない関数を呼び出したため、

```python
AttributeError
```

が発生した。

---

### 原因3：_receive_and_save()のexcept対象外だった

現在の例外処理では `AttributeError` を捕捉していなかった。

そのため、例外は関数の外まで伝播した。

---

### 原因4：処理がThreadPoolExecutor上で実行されていた

通常の同期関数呼び出しではなく、

```python
executor.submit()
```

で実行していたため、関数の外へ出た例外は `Future` に保存された。

---

### 原因5：submit()の戻り値Futureを保存していなかった

現在は、

```python
self.executor.submit(...)
```

だけを実行しており、戻り値の `Future` を受け取っていない。

---

### 原因6：Futureの結果・例外を確認していなかった

`future.result()` や `future.exception()` を呼んでいなかったため、Future内に保存された例外をアプリ側から確認できなかった。

---

## 17. 今回の推奨対策

今回のアプリでは、次の対策が有効である。

### 対策1：submit()が返すFutureを受け取る

現在の、

```python
self.executor.submit(
    self._receive_and_save,
    config,
)
```

を、

```python
future = self.executor.submit(
    self._receive_and_save,
    config,
)
```

のようにする。

---

### 対策2：add_done_callback()を登録する

```python
future.add_done_callback(
    self._handle_future
)
```

を登録する。

---

### 対策3：callback内でfuture.result()を呼び出す

```python
def _handle_future(self, future) -> None:
    try:
        future.result()

    except Exception as error:
        print(
            f"[{current_time()}] "
            f"受信スレッドで予期しないエラー: {error}"
        )
```

とする。

これによって、ワーカースレッド内の想定外エラーを確実に把握できる。

---

## 18. さらに改善するならtracebackも表示する

単純に、

```python
print(error)
```

だけでは、

> どのファイルの何行目で発生したのか

が分かりにくいことがある。

開発中は、Python標準ライブラリの `traceback` を利用する方法も有効である。

例えば、

```python
import traceback
```

として、

```python
def _handle_future(self, future) -> None:
    try:
        future.result()

    except Exception:
        traceback.print_exc()
```

とすれば、通常の例外と同様にスタックトレースを確認できる。

今回のような、

```text
AttributeError
```

であれば、`kv_com.read_devices_l()` の呼び出し箇所まで確認できるため、原因究明が非常に速くなる。

将来的に `logging` モジュールを採用する場合は、

```python
logger.exception(...)
```

を使用することで、エラーメッセージとスタックトレースをまとめてログへ記録できる。

---

## 19. 外部モジュールを使用するアプリで特に注意すること

今回のトラブルは、

```python
from common_lib_mw import kv_com
```

のように、別ディレクトリや共通ライブラリとして管理しているモジュールを使用する場合に特に起こりやすい。

アプリ側だけを更新して、

```python
read_devices_l()
```

のような新しいAPIを使い始めても、

実行環境側の共通モジュールが古いままであれば不整合が発生する。

そのため、次の観点も重要になる。

```text
アプリ本体
    │
    ├── app.py         最新
    │
    └── common_lib_mw
            │
            └── kv_com.py   古い
```

このような状態では、

> ソースコード上は正しく見えても、実行時には関数が存在しない

という問題が発生する。

外部・共通モジュールを変更した場合には、

- 実行環境のファイルも更新されているか
- importしているファイルが想定した場所のものか
- 必要な関数が実際に存在するか

を確認することが重要である。

必要であれば開発時に、

```python
print(kv_com.__file__)
```

で、実際に読み込まれている `kv_com.py` の場所を確認することもできる。

---

## 20. 今回の重要な教訓

### 教訓1

`ThreadPoolExecutor` のワーカースレッドで発生した例外は、

> 自動的にメインスレッドへ表示されるとは限らない。

---

### 教訓2

`executor.submit()` は `Future` を返す。

```python
future = executor.submit(...)
```

このFutureは、単なる戻り値ではなく、

> 非同期処理の状態・結果・例外を管理する重要なオブジェクト

である。

---

### 教訓3

Futureを受け取らずに捨てると、

> ワーカースレッド内で発生した想定外エラーに気付きにくくなる

可能性がある。

---

### 教訓4

ワーカースレッドの例外を確認する代表的方法は、

```python
future.result()
```

である。

異常終了していた場合は、その例外が `result()` を呼び出した場所で再送出される。

---

### 教訓5

非同期処理を維持したい場合、

```python
submit()
↓
直後にresult()
```

とするのではなく、

```python
submit()
↓
add_done_callback()
↓
処理完了後にresult()
```

という構成が有効である。

---

### 教訓6

想定内の通信エラーと、プログラム上の想定外エラーは分けて考える。

```text
想定内
ConnectionError
OSError
RuntimeError
ValueError
など

        ↓

処理関数内部で対応


想定外
AttributeError
TypeError
NameError
など

        ↓

Future側で検知
        ↓
重大なプログラムエラーとして確認
```

---

## 21. 今回のトラブルを一言で表すと

今回の問題は、

> **古い `kv_com` に存在しない `read_devices_l()` をワーカースレッドから呼び出したことで `AttributeError` が発生したが、その例外は `ThreadPoolExecutor` の `Future` に保存され、アプリ側がFutureを確認していなかったため表面化しなかった**

というトラブルである。

PLC監視処理そのものは別に動き続けていたため、アプリ全体が停止せず、

> 「PLC監視は動いているのに、データ受信だけが止まっている」

という非常に分かりにくい症状になった。

---

## 22. 今後の設計方針

今後の設備データ受信アプリでは、`ThreadPoolExecutor` へ処理を投入するとき、

```python
executor.submit(...)
```

だけで終わらせず、

> **Futureの例外をどこで確認するか**

までをセットで設計する。

現在のアプリでは、

```python
future = self.executor.submit(...)
future.add_done_callback(...)
```

とし、callback内で、

```python
future.result()
```

を実行して想定外例外を検知する方法が適している。

これにより、

- PLC監視処理を止めない
- 複数データの並行受信を維持する
- ワーカースレッドの想定外エラーを見逃さない
- 外部モジュールのバージョン不整合にも早く気付ける

という、より堅牢な構成にできる。

---

## 23. まとめ

今回のトラブルで最も重要なポイントは、

```text
ThreadPoolExecutor
        ↓
executor.submit()
        ↓
Future
        ↓
正常終了なら結果を保持
異常終了なら例外を保持
```

という関係である。

そして、

```python
future.result()
```

は単に計算結果を受け取るためだけのものではない。

> **ワーカースレッド内で発生した例外を呼び出し側へ再送出し、異常を認識する**

という非常に重要な役割を持っている。

今回のような常駐監視型アプリでは、直後に `result()` して待機するのではなく、

```python
add_done_callback()
```

と組み合わせて、処理完了時に `result()` を確認する構成が適している。

この事例は、

> **「ThreadPoolExecutorを使うなら、処理をsubmitするだけでなくFutureの例外管理まで考える」**

という設計上の重要な教訓として残しておく。
