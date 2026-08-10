# ThreadPoolExecutor方式へ変更した場合のメリット

## 1. はじめに

現在のモータ電流値受信アプリでは、PLCから受信要求が入ったタイミングで `threading.Thread` を生成し、モータごとのデータ受信・CSV保存・PLCへの完了通知をサブスレッドで実行している。

現在のイメージは次のとおり。

```python
thread = threading.Thread(
    target=self._receive_and_save,
    args=(config,),
    name=f"{config.name}-receiver",
    daemon=False,
)
thread.start()
```

この方式はシンプルで分かりやすく、モータが3台程度であれば十分実用的である。

一方、この処理は `ThreadPoolExecutor` を使用して書き換えることもできる。

例えば、初期化時に次のような固定サイズのスレッドプールを作成する。

```python
from concurrent.futures import ThreadPoolExecutor

self.executor = ThreadPoolExecutor(
    max_workers=len(MOTOR_CONFIGS),
    thread_name_prefix="motor-receiver",
)
```

受信要求が発生したときは、

```python
self.executor.submit(
    self._receive_and_save,
    config,
)
```

とする。

本資料では、現在の `threading.Thread` 方式を `ThreadPoolExecutor` 方式へ変更した場合に、どのようなメリットがあるのかを整理する。

---

# 2. 結論

今回のアプリは、`ThreadPoolExecutor` と相性がよい。

ただし、

> 現在の `threading.Thread` 方式が間違っているから変更する

という意味ではない。

現在の方式でも十分に動作する。

`ThreadPoolExecutor` へ変更する主な理由は、性能向上ではなく、

> スレッドの生成・再利用・最大並列数・終了処理などの管理を `ThreadPoolExecutor` に任せ、アプリ全体のスレッド管理を整理するため

である。

特に今回のような、

- 複数のモータを監視する
- 要求が来たときだけ処理する
- PLC通信のようなI/O待ちが多い
- 複数台を並行処理したい
- 同時実行数には上限を設けたい
- 受信・保存処理を途中で終了させたくない

というアプリでは、`ThreadPoolExecutor` は非常に自然な選択肢である。

---

# 3. 現在の threading.Thread 方式

現在は要求を検出すると、その場で新しいスレッドを生成している。

```python
thread = threading.Thread(
    target=self._receive_and_save,
    args=(config,),
    name=f"{config.name}-receiver",
    daemon=False,
)
thread.start()
```

処理イメージは、

```text
メインスレッド
    │
    ├── モータ1要求検出
    │       ↓
    │   Thread生成
    │       ↓
    │   _receive_and_save(motor1)
    │
    ├── モータ2要求検出
    │       ↓
    │   Thread生成
    │       ↓
    │   _receive_and_save(motor2)
    │
    └── モータ3要求検出
            ↓
        Thread生成
            ↓
        _receive_and_save(motor3)
```

となる。

この方式の最大のメリットは、

> 動作が非常に分かりやすい

ことである。

```python
thread = threading.Thread(...)
thread.start()
```

を見れば、

「ここで新しいスレッドを1本作って開始している」

と直感的に理解できる。

学習面でも非常に分かりやすい。

---

# 4. ThreadPoolExecutor方式

`ThreadPoolExecutor` を使用する場合は、あらかじめ複数のworkerスレッドを管理する「スレッドプール」を用意する。

例えばモータが3台なら、

```python
self.executor = ThreadPoolExecutor(
    max_workers=3,
    thread_name_prefix="motor-receiver",
)
```

とする。

そして処理したい仕事を、

```python
self.executor.submit(
    self._receive_and_save,
    config,
)
```

とExecutorへ渡す。

イメージは次のようになる。

```text
                  ┌────────────────────────┐
要求 ───────────→ │   ThreadPoolExecutor   │
                  │                        │
                  │  worker 1              │
                  │  worker 2              │
                  │  worker 3              │
                  └────────────────────────┘
                           │
                           ↓
                  _receive_and_save()
```

プログラム側は、

> 新しいThreadを作る

のではなく、

> Executorへ「この仕事を実行してください」と依頼する

形になる。

---

# 5. メリット1：スレッド管理をExecutorへ任せられる

`threading.Thread` 方式では、自分で、

```python
thread = threading.Thread(...)
thread.start()
```

とスレッドを作成・開始する。

必要に応じて、

```python
thread.join()
```

などによる終了待ちも自分で管理する必要がある。

一方、`ThreadPoolExecutor` では、

```python
self.executor.submit(...)
```

と仕事を渡せば、どのworkerスレッドで実行するかなどをExecutorが管理してくれる。

つまり、

```text
threading.Thread
    ↓
スレッドそのものを自分で管理する

ThreadPoolExecutor
    ↓
「実行したい仕事」をExecutorへ渡す
    ↓
スレッド管理はExecutorに任せる
```

という違いがある。

アプリが大きくなるほど、後者の方が管理しやすくなる。

---

# 6. メリット2：最大同時実行数を明確に制限できる

`ThreadPoolExecutor` の大きなメリットの一つが、

```python
max_workers=3
```

のように、同時に実行できる処理数を明示できることである。

例えば、

```python
self.executor = ThreadPoolExecutor(
    max_workers=3,
)
```

なら、

```text
処理1 → worker 1
処理2 → worker 2
処理3 → worker 3
処理4 → 待機
処理5 → 待機
```

となる。

workerの処理が終われば、

```text
worker 2 処理終了
        ↓
待機していた処理4を開始
```

という形でExecutorが自動的に処理する。

今回のようなPLC通信アプリでは、

> 通信を無制限に並列化しない

ことは重要である。

現在はモータ3台なので大きな問題にはなりにくいが、将来、

- モータ台数が増える
- PLC台数が増える
- 別の受信処理が追加される

といった場合には、`max_workers` による上限管理が非常に役立つ。

---

# 7. メリット3：スレッドを再利用できる

`threading.Thread` では、基本的に処理ごとに、

```text
Thread生成
    ↓
処理開始
    ↓
処理終了
    ↓
Thread終了
```

となる。

次の要求が来れば、また新しいThreadを作る。

一方、`ThreadPoolExecutor` はworkerスレッドを管理し、処理が終わったworkerを次の仕事に再利用する。

イメージとしては、

```text
worker 1
    ↓
motor1受信
    ↓
処理終了
    ↓
待機
    ↓
次の受信処理
```

となる。

今回のアプリでは要求頻度が極端に高いわけではないため、スレッド生成コストによる性能差を重視する必要はない。

したがって、

> ThreadPoolExecutorにすると劇的に高速になる

という理解は適切ではない。

メリットは主に管理面にある。

---

# 8. メリット4：終了処理を整理しやすい

今回のアプリでは、サブスレッドが、

```text
PLCから1000点受信
    ↓
CSV保存
    ↓
PLCへ受信完了通知
```

という重要な処理を担当している。

そのため、アプリ終了時にこの処理を途中で強制終了するのは避けたい。

`threading.Thread` 方式なら、非daemonスレッドにしたうえで、必要に応じて各Threadを保持し、

```python
thread.join()
```

で終了を待つ設計が考えられる。

`ThreadPoolExecutor` では、

```python
self.executor.shutdown(wait=True)
```

という形でExecutor全体を終了できる。

`wait=True` にすると、実行中の処理が終了するまで待つ。

理想的な終了イメージは、

```text
Ctrl + C
    ↓
メイン監視ループ終了
    ↓
新しい受信要求の受付終了
    ↓
executor.shutdown(wait=True)
    ↓
現在実行中の受信処理を待つ
    ↓
PLCデータ受信完了
    ↓
CSV保存完了
    ↓
PLC完了通知
    ↓
worker終了
    ↓
アプリ終了
```

となる。

今回のような、

> 途中で切りたくない処理

を扱うアプリでは、この終了管理は大きなメリットである。

---

# 9. daemon=Falseとの関係

現在の `threading.Thread` 方式では、

```python
daemon=False
```

とするのが今回の用途には適している。

理由は、受信スレッドが動作中なら、その処理が完了する前にPythonプロセスを終了させたくないからである。

```text
daemon=True
    ↓
メインスレッドなどの非daemonスレッドがなくなれば
処理途中でもプロセス終了可能

daemon=False
    ↓
そのスレッドが終了するまで
Pythonプロセスは終了しない
```

今回の `_receive_and_save()` は、

- PLCデータ受信
- CSV保存
- PLCへの完了通知

を行うため、途中終了させたくない。

そのため `daemon=False` が自然である。

`ThreadPoolExecutor` を使用すると、この考え方をExecutor単位で管理しやすくなる。

特に、

```python
executor.shutdown(wait=True)
```

によって、

> 実行中の仕事を完了させてから終了する

という意図を明確にできる。

---

# 10. メリット5：要求処理部分がシンプルになる

現在は、

```python
thread = threading.Thread(
    target=self._receive_and_save,
    args=(config,),
    name=f"{config.name}-receiver",
    daemon=False,
)
thread.start()
```

としている。

`ThreadPoolExecutor` なら、

```python
self.executor.submit(
    self._receive_and_save,
    config,
)
```

と書ける。

つまり、

```text
Threadオブジェクトを作る
    ↓
引数をargsタプルで渡す
    ↓
start()する
```

という操作が、

```text
Executorへ処理をsubmitする
```

という一つの考え方にまとまる。

---

# 11. メリット6：Futureを利用できる

`submit()` は `Future` オブジェクトを返す。

```python
future = self.executor.submit(
    self._receive_and_save,
    config,
)
```

`Future` は、

> 将来完了する処理

を表すオブジェクトである。

例えば、

```python
future.done()
```

で処理が完了したか確認できる。

```python
future.result()
```

で処理結果を取得できる。

また、処理内で例外が発生した場合、その例外を `Future` 経由で扱うこともできる。

今回のコードでは `_receive_and_save()` 自身が例外処理を行っているため、すぐにFuture管理が必須になるわけではない。

しかし将来、

- 完了状態を管理する
- 処理結果を取得する
- エラーを一元管理する
- 完了した処理から順に扱う

といった機能を追加するときに、Futureが利用できるのは大きな拡張性になる。

---

# 12. ThreadPoolExecutorに変更してもLockは必要

ここは非常に重要である。

`ThreadPoolExecutor` に変更すると、

> Lockが不要になる

わけではない。

今回のコードでは、

```python
self.request_latched
self.is_receiving
```

という共有状態がある。

これらを複数のスレッドから安全に扱うため、

```python
self.state_lock = threading.Lock()
```

を使用している。

`ThreadPoolExecutor` の役割は、

> workerスレッドを管理すること

である。

一方、`Lock` の役割は、

> 複数スレッドから共有データへ同時アクセスすることを防ぐこと

である。

つまり、

```text
ThreadPoolExecutor
    ↓
スレッド管理

Lock
    ↓
共有データ保護
```

であり、役割が異なる。

したがって `ThreadPoolExecutor` へ変更しても、

```python
self.state_lock
```

は基本的に残す。

---

# 13. request_latchedとis_receivingも基本的に残す

現在のアプリでは、

```python
self.request_latched
```

によって、PLC要求信号がONのまま連続しているときに同じ要求を再受付しないようにしている。

また、

```python
self.is_receiving
```

によって、そのモータの受信処理がすでに実行中なら二重起動しないようにしている。

`ThreadPoolExecutor` は仕事を渡されれば実行するだけなので、

> 同じモータの処理を重複してsubmitしない

というアプリ固有の判断まではしてくれない。

したがって、

```python
request_latched
is_receiving
state_lock
```

という現在の制御は、ThreadPoolExecutor方式でも重要である。

---

# 14. 今回のアプリとThreadPoolExecutorの相性

今回のアプリには、次の特徴がある。

```text
メインスレッド
    ↓
PLC要求信号を常時監視

要求なし
    ↓
何もしない

要求あり
    ↓
モータごとの受信処理を開始

受信処理
    ↓
PLC通信
    ↓
CSV保存
    ↓
PLC完了通知
```

PLC通信やファイル保存は、CPUで大量計算する処理というよりI/O待ちを含む処理である。

このような処理はスレッドによる並行処理と相性がよい。

さらにモータごとの処理単位も明確である。

```python
_receive_and_save(config)
```

という一つの仕事を、

```python
executor.submit(...)
```

へ渡せるため、ThreadPoolExecutorの考え方と非常によく合っている。

---

# 15. max_workersはいくつがよいか

今回の構成では、

```python
max_workers=len(MOTOR_CONFIGS)
```

が分かりやすい。

モータが3台なら、

```python
max_workers=3
```

になる。

```python
self.executor = ThreadPoolExecutor(
    max_workers=len(MOTOR_CONFIGS),
    thread_name_prefix="motor-receiver",
)
```

とすれば、

> 最大でモータ台数分の受信処理を同時実行する

という設計意図がコードから読み取れる。

例えば、

```text
motor1受信中
motor2受信中
motor3受信中
```

という3台同時受信も可能になる。

ただし、実際の最大並列数はPLC通信ライブラリのスレッド安全性や、PLC・ネットワーク側の通信能力も考慮して決める必要がある。

---

# 16. 性能目的で変更するわけではない

今回、ThreadPoolExecutorへ変更する理由を、

> ThreadPoolExecutorの方が高速だから

と考えない方がよい。

3台程度のモータで、要求時だけThreadを作る現在の方式なら、Thread生成コストは通常大きな問題にはなりにくい。

したがって、

```text
threading.Thread
        vs
ThreadPoolExecutor
```

の主な違いは、

```text
速度
```

ではなく、

```text
管理方法
```

である。

ThreadPoolExecutorの価値は、

- 最大並列数
- worker管理
- スレッド再利用
- shutdown
- Future
- 将来の拡張性

などにある。

---

# 17. threading.Thread方式のメリットもある

ThreadPoolExecutorが常に優れているわけではない。

現在の方式には、

> とにかくシンプルで動作が見えやすい

という大きなメリットがある。

```python
thread = threading.Thread(...)
thread.start()
```

は、Pythonのスレッドを理解するうえでも非常に分かりやすい。

そのため、

- モータは3台固定
- 今後機能追加しない
- スレッド数も少ない
- シンプルさを最優先する

のであれば、現在の方式をそのまま使っても問題ない。

---

# 18. ThreadPoolExecutorへ変更する価値が高くなる条件

次のような条件なら、ThreadPoolExecutor方式へ変更する価値が高い。

### モータ数・処理数が増える

スレッドを個別管理するよりExecutorでまとめた方が分かりやすくなる。

### 最大同時実行数を制限したい

```python
max_workers
```

で明示できる。

### 終了処理を整理したい

```python
shutdown(wait=True)
```

による管理ができる。

### Futureを使いたい

処理状態・結果・例外などを管理しやすくなる。

### 今後も機能追加する予定がある

ThreadPoolExecutor方式の方が拡張しやすい。

---

# 19. 今回のアプリで推奨する構成

今回のアプリを継続運用する前提なら、次のような構成は非常に自然である。

```text
MotorReceiver
│
├── メインスレッド
│       │
│       └── PLC要求信号監視
│
├── ThreadPoolExecutor
│       │
│       ├── worker 1
│       ├── worker 2
│       └── worker 3
│
├── request_latched
│
├── is_receiving
│
└── state_lock
```

要求が来たら、

```text
PLC要求ON
    ↓
request_latched確認
    ↓
is_receiving確認
    ↓
Executorへsubmit
    ↓
workerが_receive_and_save()を実行
```

となる。

終了時は、

```text
Ctrl + C
    ↓
監視終了
    ↓
Executorへ新しい仕事を入れない
    ↓
shutdown(wait=True)
    ↓
受信中処理完了
    ↓
アプリ終了
```

という流れにできる。

---

# 20. threading.Thread方式とThreadPoolExecutor方式の比較

| 項目 | threading.Thread | ThreadPoolExecutor |
|---|---|---|
| 分かりやすさ | 非常に高い | 少し抽象度が高い |
| Thread生成 | 自分で行う | Executorが管理 |
| Thread開始 | `start()` | `submit()` |
| 最大並列数 | 自分で管理 | `max_workers` |
| スレッド再利用 | 基本なし | あり |
| 終了管理 | `join()`等 | `shutdown()` |
| Future | なし | あり |
| 小規模処理 | 非常に向く | 向く |
| 処理数が増える場合 | 管理が複雑化 | 管理しやすい |
| 拡張性 | 普通 | 高い |

---

# 21. 今回の判断

今回のアプリでは、

```text
現在のthreading.Thread方式
```

でも十分に正しい。

特に現在のコードは、

- 受信要求の立上り検出
- 二重起動防止
- Lockによる共有状態保護
- モータ別スレッド
- 例外処理
- CSV保存
- PLC完了通知

まで整理されている。

そのため、

> ThreadPoolExecutorにしないと危険

という状況ではない。

一方で、このアプリを今後も発展させるなら、

> ThreadPoolExecutor方式へ変更する価値は十分にある。

特に大きいのは、

1. スレッド管理の一元化
2. 最大同時実行数の明示
3. 終了処理の整理
4. Futureによる拡張性

である。

---

# 22. 最終的な考え方

今回の選択を一言で表すと、

```text
threading.Thread
    ↓
「スレッド」を自分で作って管理する

ThreadPoolExecutor
    ↓
「仕事」をExecutorへ渡し、
スレッド管理はExecutorに任せる
```

という違いである。

今回のPLC受信アプリは、

```python
_receive_and_save(config)
```

という独立した「仕事」が明確に定義されている。

そのため、

```python
executor.submit(
    self._receive_and_save,
    config,
)
```

というThreadPoolExecutorの考え方と非常に相性がよい。

---

# 23. まとめ

今回のアプリをThreadPoolExecutor方式へ変更する主なメリットは、

- スレッド管理をExecutorへ任せられる
- `max_workers` で最大並列数を制限できる
- workerスレッドを再利用できる
- `shutdown(wait=True)` で終了処理を整理しやすい
- `Future` を利用できる
- 将来モータや処理が増えても拡張しやすい

ことである。

ただし、

> ThreadPoolExecutorにすれば高速になるから変更する

という話ではない。

今回の最大の目的は、

> **スレッド管理をより整理された形にすること**

である。

また、ThreadPoolExecutorに変更しても、

```python
self.state_lock
self.request_latched
self.is_receiving
```

は基本的に必要である。

それぞれ、

```text
ThreadPoolExecutor
    → スレッド管理

Lock
    → 共有データ保護

request_latched
    → 要求信号の二重受付防止

is_receiving
    → 同じモータの受信処理の二重起動防止
```

という異なる役割を持つ。

今回のようなPLC通信＋データ保存アプリを長期的に運用・拡張することを考えると、

> **固定サイズのThreadPoolExecutorを1つ持ち、各モータの受信処理をsubmitする方式**

は、シンプルさと拡張性のバランスがよい設計である。
