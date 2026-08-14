# pywebview PUSH実装の技術標準
## `window` を `js_api` の公開オブジェクトツリーに含めない

## 1. 目的

本書は、pywebviewアプリにおいて **Python側からJavaScript側へデータをPushする場合の標準的な設計方針**を定める。

特に重要な原則を次の1文に集約する。

> **PUSH実装の原則：`window` を `js_api` の公開オブジェクトツリーに含めない。**

この原則は、Python → JavaScript のPushそのものの制約ではない。

`js_api`としてJavaScript側へ公開するPythonオブジェクトと、pywebview内部の`window`オブジェクトの責務を分離し、不要なシリアライズや再帰的なオブジェクト探索を防ぐための設計原則である。

---

# 2. 結論

pywebviewでPythonからJavaScriptへPushする基本処理は非常に単純である。

```python
window.run_js(
    "window.receiveData(...);"
)
```

JavaScript側には、受信用関数を用意する。

```javascript
window.receiveData = function (data) {
    // 画面更新など
};
```

Push自体に、

- クラス分割
- `_serializable = False`
- 特別なスレッド構成

が必須というわけではない。

重要なのは、JavaScriptからPythonを呼ぶために`js_api`へ公開するオブジェクトの中へ、`webview.Window`などのPython内部オブジェクトを不用意に含めないことである。

標準的な考え方は次の通り。

```text
JavaScriptへ公開する領域
        │
        ↓
      AppApi
        │
        ├─ start_xxx()
        ├─ stop_xxx()
        └─ get_xxx()

--------------------------------
        境界
--------------------------------

Python内部の領域

window
Thread
Event
Lock
Executor
PLC通信オブジェクト
DB接続オブジェクト
その他の内部状態
```

---

# 3. まず理解するべき2方向の通信

pywebviewアプリでは、PythonとJavaScriptの通信を2方向に分けて考える。

## 3.1 JavaScript → Python

JavaScriptからPythonを呼び出す場合は、

```javascript
await pywebview.api.start_clock();
```

のように`pywebview.api`を使用する。

Python側では、

```python
class AppApi:
    def start_clock(self):
        ...
```

のようなAPIを用意する。

さらに、

```python
api = AppApi()

window = webview.create_window(
    "Sample",
    "index.html",
    js_api=api,
)
```

として`js_api=api`を指定する。

概念的には、

```text
JavaScript
    │
    │ pywebview.api.start_clock()
    ↓
js_api
    ↓
AppApi
    ↓
Python処理
```

となる。

---

## 3.2 Python → JavaScript

PythonからJavaScriptへPushする場合は、

```python
window.run_js(...)
```

を使用する。

例えば、

```python
window.run_js(
    'window.receiveTime("12:34:56");'
)
```

とすると、JavaScript側の、

```javascript
window.receiveTime = function (currentTime) {
    console.log(currentTime);
};
```

が実行される。

概念的には、

```text
Python
    │
    │ window.run_js(...)
    ↓
pywebview Window
    ↓
JavaScript
    │
    │ window.receiveTime(...)
    ↓
画面更新
```

となる。

この2方向は別の仕組みである。

```text
JavaScript → Python
        pywebview.api.xxx()

Python → JavaScript
        window.run_js()
```

まずこの区別を明確にする。

---

# 4. Pushと`js_api`は別の役割

ここは非常に重要である。

PythonからJavaScriptへPushするとき、

```python
window.run_js(...)
```

を使用する。

一方、

```python
js_api=api
```

は、

> JavaScriptからPythonのメソッドを呼べるようにする

ための仕組みである。

つまり、

```text
js_api
```

と、

```text
window.run_js()
```

は別方向の通信を担当している。

```text
              JavaScript
                  │
       ┌──────────┴──────────┐
       │                     │
       ↓                     ↑
 pywebview.api.xxx()    window.run_js()
       │                     │
       ↓                     │
              Python
```

したがって、

> Pushするために`window`を`AppApi`のメンバにする必要はない。

これが本書の設計原則につながる。

---

# 5. `window`とは何か

pywebviewでは、

```python
window = webview.create_window(
    "Sample",
    "index.html",
)
```

によってWindowオブジェクトを取得する。

この`window`には、

- JavaScript実行
- ウィンドウ操作
- ネイティブGUIとの連携
- pywebview内部状態

など、多くの情報が含まれている。

PythonからJavaScriptへPushする場合は、

```python
window.run_js(...)
```

を使うため、この`window`への参照が必要になる。

しかし、

> `window`を使う必要があることと、`window`を`js_api`へ公開する必要があることは別問題

である。

---

# 6. 避けるべき構造

次のような構造は避ける。

```python
class AppApi:
    def __init__(self):
        self.window = None

    def set_window(self, window):
        self.window = window
```

そして、

```python
api = AppApi()

window = webview.create_window(
    "Sample",
    "index.html",
    js_api=api,
)

api.set_window(window)
```

とする。

見た目には自然である。

しかしオブジェクトの関係を見ると、

```text
js_api
  ↓
AppApi
  ↓
self.window
  ↓
webview.Window
```

となる。

つまり、JavaScript APIとして公開しているオブジェクトから`window`へ到達できる。

これを本書では、

> **`window`が`js_api`の公開オブジェクトツリーに含まれている**

と表現する。

---

# 7. 「公開オブジェクトツリー」とは

例えば、

```python
class AppApi:
    def __init__(self, receiver):
        self.receiver = receiver
```

さらに、

```python
class Receiver:
    def __init__(self, window):
        self.window = window
```

だったとする。

オブジェクト関係は、

```text
AppApi
  │
  └─ receiver
       │
       └─ window
```

となる。

`AppApi`自身が直接`window`を持っていなくても、

```text
AppApi
 ↓
receiver
 ↓
window
```

と辿ることができる。

したがって、

> 「AppApiが直接windowを持たなければよい」

だけでは不十分である。

重要なのは、

> **`js_api`から辿れる公開オブジェクトの範囲に`window`を含めないこと**

である。

---

# 8. 今回実際に発生した不具合

学習用の時計アプリでは、当初`AppApi`が直接、

```python
self.window
self.stop_event
self.clock_thread
```

を保持する構造にしていた。

そして`AppApi`を、

```python
js_api=api
```

としてJavaScriptへ公開した。

起動時には、次のようなエラーが発生した。

```text
[pywebview] Error while processing
window.native.AccessibilityObject.Bounds.Empty.Empty.Empty...
maximum recursion depth exceeded
```

特に特徴的だったのは、

```text
window.native.AccessibilityObject
```

以降を延々と辿っていたことである。

概念的には、

```text
js_api
  ↓
AppApi
  ↓
window
  ↓
native
  ↓
AccessibilityObject
  ↓
Bounds
  ↓
Empty
  ↓
Empty
  ↓
Empty
  ↓
...
```

のような状態になった。

最終的にPythonの再帰深度上限へ到達し、

```text
maximum recursion depth exceeded
```

となった。

---

# 9. 不具合の本質

今回の不具合を、

> 「PythonからJavaScriptへPushしたから発生した」

と理解してはいけない。

Push処理そのものは、

```python
window.run_js(...)
```

であり、問題ではなかった。

問題だったのは、

```text
js_api
  ↓
公開Pythonオブジェクト
  ↓
window
```

というオブジェクト構造である。

したがって、不具合の本質は、

> **Pushではなく、JavaScript公開用APIのオブジェクトツリーに`window`を含めてしまったこと**

と整理する。

---

# 10. 正しい設計原則

今後の標準方針を次のように定める。

> ## PUSH実装の原則
>
> **`window`を`js_api`の公開オブジェクトツリーに含めない。**

もう少し具体的に書くと、

> `js_api`として公開するクラスには、JavaScriptから呼び出す必要のあるAPIだけを持たせる。  
> `webview.Window`などのPython内部オブジェクトは、JavaScript公開APIの外側で管理する。

---

# 11. 最も単純な回避方法：`window`を外側で管理する

小規模なアプリや学習用サンプルでは、`window`をモジュールレベルで管理する方法が非常に分かりやすい。

```python
window = None
```

そしてPush時には、

```python
window.run_js(...)
```

を使用する。

`AppApi`には`window`を持たせない。

```python
class AppApi:
    def start_clock(self):
        ...

    def stop_clock(self):
        ...
```

オブジェクト関係は、

```text
js_api
  ↓
AppApi

----------------

window
  ↓
Python内部
```

となる。

`AppApi`から`window`へ辿れないため、今回問題になった経路そのものが存在しない。

---

# 12. グローバル`window`方式の評価

グローバル変数は一般論として無条件に推奨されるものではない。

しかし、

```python
window
```

がアプリ全体で1個しか存在せず、

```python
window.run_js(...)
```

のために共有したいだけであれば、小規模アプリでは非常に単純で理解しやすい。

メリット：

- 構造が単純
- `_serializable = False`を意識しなくてよい
- Pushの仕組みが理解しやすい
- `js_api`と`window`の責務が明確に分離される

デメリット：

- アプリが大規模になるとグローバル状態が増えやすい
- 複数Windowを扱う場合は管理しにくくなる
- テストや再利用性ではクラス管理の方が有利な場合がある

したがって、

> **グローバル変数だから悪い**

と機械的に判断するのではなく、アプリ規模と責務を見て判断する。

---

# 13. クラスで管理する場合

大規模なアプリでは、

- PLC通信
- Thread
- Event
- Executor
- SQLite
- 各種状態

などをクラスへまとめたい場合がある。

例えば、

```text
AppApi
  ↓
DataReceiver
```

という構造にする。

`DataReceiver`が`window`を保持する場合、

```text
js_api
  ↓
AppApi
  ↓
DataReceiver
  ↓
window
```

となるため、そのままでは公開オブジェクトツリーに`window`が入る。

そこで、

```python
class DataReceiver:
    _serializable = False
```

として、Python内部クラスをシリアライズ対象から除外する。

概念的には、

```text
js_api
  ↓
AppApi
  ↓
DataReceiver
  ↓
_serializable = False
  ↓
ここから先は公開対象外

    ├─ window
    ├─ Event
    ├─ Executor
    └─ PLC通信状態
```

となる。

---

# 14. `_serializable = False`の位置づけ

ここで重要なのは、

> `_serializable = False`はPushするために必要な機能ではない

ということである。

Pushに必要なのは、

```python
window.run_js(...)
```

である。

`_serializable = False`は、

> クラス設計上、JavaScript公開APIからPython内部オブジェクトへ参照がつながる場合に、その内部を公開・解析対象から外すための手段

と理解する。

したがって、

```text
PUSH
  =
_serializable = False
```

ではない。

また、

```text
PUSH
  =
クラスを分ける
```

でもない。

正しくは、

```text
PUSH
  =
window.run_js()
```

である。

そして設計原則として、

```text
js_api
  ↓
windowを含めない
```

を守る。

---

# 15. 「クラスを分ける」は手段の一つ

今回、再帰エラーを回避するために、

```text
AppApi
  ↓
Clock
```

とクラスを分け、

```python
class Clock:
    _serializable = False
```

とする方法でも正常動作した。

これは有効な方法である。

しかし、

> Pushする場合は必ずクラスを2つに分ける

というルールではない。

クラス分割は、

> `window`やThread、Eventなどの内部状態をJavaScript公開APIから隔離するための設計手段の一つ

である。

---

# 16. 標準設計の優先順位

今後は次の順序で考える。

## 第1段階：Pushの必要性を確認する

Python側のタイミングでJavaScriptを更新したい場合、

```python
window.run_js(...)
```

を使用する。

---

## 第2段階：`window`をどこで管理するか決める

小規模なら、

```python
window = ...
```

をモジュールレベルで管理してもよい。

大規模なら内部処理クラスで管理してもよい。

---

## 第3段階：`js_api`から`window`へ辿れないか確認する

必ず次の視点で確認する。

```text
js_api
  ↓
AppApi
  ↓
？？？
  ↓
window
```

この経路が存在しないか確認する。

---

## 第4段階：必要なら内部クラスを非シリアライズ化する

設計上、

```text
AppApi
  ↓
内部処理クラス
  ↓
window
```

となる場合は、

```python
_serializable = False
```

の利用を検討する。

---

# 17. 推奨パターンA：小規模アプリ

学習用アプリや小規模ツールでは次の形が分かりやすい。

```text
グローバル / モジュールレベル
    │
    ├─ window
    ├─ Event
    └─ Thread

AppApi
    │
    ├─ start()
    └─ stop()
```

重要なのは、

```text
AppApi → window
```

というメンバ参照を作らないことである。

---

# 18. 推奨パターンB：中～大規模アプリ

PLC通信アプリなどでは、

```text
AppApi
  │
  └─ receiver
       ↓
    DataReceiver
    _serializable = False
       │
       ├─ window
       ├─ Event
       ├─ ThreadPoolExecutor
       ├─ PLC通信
       └─ 内部状態
```

のようにする。

この場合、

- `AppApi`：JavaScriptとの窓口
- `DataReceiver`：Python内部処理

と責務を分離できる。

---

# 19. `AppApi`に持たせてよいもの

基本的には、

> JavaScript APIとして公開するために必要なものだけ

と考える。

例えば、

```python
class AppApi:
    def start_monitoring(self):
        ...

    def stop_monitoring(self):
        ...

    def get_status(self):
        ...
```

のようなメソッドである。

単純な文字列、数値、辞書など、API処理に必要な軽量データを持つことはあり得る。

ただし、複雑なPython内部オブジェクトを不用意にぶら下げない。

---

# 20. `AppApi`から隔離したいもの

特に次のようなものは注意する。

```text
webview.Window
threading.Thread
threading.Event
threading.Lock
ThreadPoolExecutor
Future
Socket
PLC通信オブジェクト
DB Connection
ファイルハンドル
GUIネイティブオブジェクト
```

これらはJavaScript側へ公開するためのデータではなく、

> Python内部で処理を実現するためのオブジェクト

である。

---

# 21. データは公開しても、処理オブジェクトは公開しない

設計を考えるときは、

```text
データ
```

と、

```text
処理を行う内部オブジェクト
```

を分けると分かりやすい。

JavaScriptへ渡したいもの：

```text
"motor1"
"2026-08-14 10:30:00"
[100, 200, 300]
{"status": "running"}
```

JavaScriptへ公開する必要がないもの：

```text
Window
Thread
Event
Lock
Executor
Socket
```

つまり、

> **JavaScriptには必要なデータとAPIだけを見せ、Pythonの実装詳細は見せない。**

これはpywebviewに限らず、API設計全般で重要な考え方である。

---

# 22. PushするデータはJSON化する

例えばPLCデータをPushする場合、

```python
payload = json.dumps(
    {
        "data_name": "motor1",
        "measured_at": "2026-08-14 10:30:00",
        "values": [100, 200, 300],
    },
    ensure_ascii=False,
)
```

として、

```python
window.run_js(
    f"window.receiveData({payload});"
)
```

とする。

JavaScript側：

```javascript
window.receiveData = function (payload) {
    console.log(payload.data_name);
    console.log(payload.measured_at);
    console.log(payload.values);
};
```

このときJavaScriptへ渡しているのはデータであり、Pythonの`window`オブジェクトそのものではない。

---

# 23. PLCアプリでの標準イメージ

実際のPLCデータ受信アプリでは、

```text
PLC
 ↓
Python
 ↓
DataReceiver
 ↓
データ取得
 ↓
JSON化
 ↓
window.run_js()
 ↓
JavaScript
 ↓
Chart.js
```

となる。

一方、操作方向は、

```text
JavaScript
 ↓
pywebview.api.start_monitoring()
 ↓
AppApi
 ↓
Python内部処理
```

となる。

全体では、

```text
                  pywebview

       JavaScript / HTML / Chart.js
              │             ↑
              │             │
 pywebview.api.xxx()     run_js()
              │             │
              ↓             │
             AppApi         │
              │             │
              ↓             │
       Python内部処理 ───────┘
              │
              ↓
             PLC
```

となる。

---

# 24. コードレビュー時の確認項目

pywebviewアプリでPush処理を実装・レビューするときは、次を確認する。

- Python → JavaScriptは`window.run_js()`で実装しているか
- JavaScript → Pythonは`pywebview.api.xxx()`で実装しているか
- `js_api`へ渡しているオブジェクトは何か
- そのオブジェクトが`window`を直接持っていないか
- メンバを1段、2段と辿ると`window`へ到達しないか
- Thread、Event、Lock、Executorなどが公開対象になっていないか
- 内部処理クラスを持たせる場合、必要なら`_serializable = False`を指定しているか
- Pushする値はJSONなどのデータとして明示的に渡しているか
- JavaScript側に受信用関数が存在するか
- 受信用関数名と`run_js()`内の関数名が一致しているか

---

# 25. 不具合発生時の確認方法

次のようなエラーが出た場合、

```text
maximum recursion depth exceeded
```

さらにログに、

```text
window.native...
AccessibilityObject...
Empty.Empty.Empty...
```

などが大量に並んでいる場合は、

> `js_api`の公開オブジェクトから`window`などの複雑な内部オブジェクトへ到達していないか

を最初に確認する。

確認イメージ：

```text
js_api=api
    ↓
apiは何を持っている？
    ↓
そのメンバは何を持っている？
    ↓
さらにその先は？
    ↓
windowへ到達していないか？
```

---

# 26. よくある誤解

## 誤解1
### Pushするには`window`を`AppApi`へ持たせる必要がある

必要ない。

Pushするコードが`window`へアクセスできればよい。

```python
window.run_js(...)
```

を実行できる場所で管理すればよい。

---

## 誤解2
### Pushするならクラスを分ける必要がある

必要ない。

クラス分割は内部状態を整理・隔離する設計手段である。

---

## 誤解3
### `_serializable = False`はPushに必要

必要ない。

`_serializable = False`は、JavaScript公開オブジェクトの配下にPython内部クラスが存在するとき、その内部を公開・解析対象から除外するための手段である。

---

## 誤解4
### グローバル`window`は絶対に禁止

必ずしもそうではない。

小規模アプリで`window`が1個だけなら、単純さを優先してモジュールレベルで管理する設計も合理的である。

ただし、アプリ規模が大きくなった場合は管理方法を再検討する。

---

# 27. 本技術標準の最重要ルール

今後のpywebviewアプリでは、次を最重要ルールとする。

> ## `js_api`にはJavaScriptから利用するAPIだけを公開する。
>
> ## `window`を`js_api`の公開オブジェクトツリーに含めない。

Pushについては、

```text
Python → JavaScript
```

を、

```python
window.run_js(...)
```

で実装する。

`window`の管理方法はアプリ規模に応じて選択する。

```text
小規模
  ↓
モジュールレベルで管理してもよい

中～大規模
  ↓
Python内部クラスで管理
  ↓
必要なら _serializable = False
```

---

# 28. 最終整理

今回の検証から、次のように整理できる。

```text
【Pushの仕組み】

Python
  ↓
window.run_js()
  ↓
JavaScript
```

Pushそのものはこれだけである。

一方、

```text
【JavaScript → Python】

JavaScript
  ↓
pywebview.api.xxx()
  ↓
js_api
  ↓
AppApi
```

となる。

ここで守るべき境界は、

```text
           JavaScript公開領域

                 AppApi
                   │
                   │
───────────────────┼──────────────────
              ここが境界
───────────────────┼──────────────────
                   │
             Python内部領域

       window / Thread / Event / Lock
       Executor / PLC通信 / DB接続
```

である。

この境界を意識することで、

- pywebviewのシリアライズ問題を避ける
- APIの責務を明確にする
- Python内部実装をJavaScriptから隔離する
- Push処理をシンプルに保つ
- 将来の保守性を高める

ことができる。

---

# 29. 技術標準としての一文

最後に、本書の内容を一文で表す。

> **pywebviewでPythonからJavaScriptへPushする場合は`window.run_js()`を使用し、`window`は`js_api`の公開オブジェクトツリーに含めない。JavaScriptへは必要なAPIとデータだけを公開し、Window・Thread・Event・ExecutorなどのPython内部オブジェクトは公開領域から隔離する。**

この原則を、今後のpywebviewアプリにおけるPython → JavaScript Push実装の標準方針とする。
