# pywebviewでPythonからJavaScriptへPushする方法
## ― 時計サンプルで学ぶ双方向通信・スレッド・Event・`_serializable` ―

## 1. はじめに

この資料では、pywebviewアプリで次の処理を実現する最小サンプルを題材に、PythonとJavaScriptの連携方法を基礎から整理する。

- 「開始」ボタンを押すとPython側の処理を開始する
- Python側で1秒ごとに現在時刻を取得する
- PythonからJavaScriptへ現在時刻をPushする
- JavaScript側で受け取った時刻を画面に表示する
- 「停止」ボタンを押すとPython側の繰り返し処理を停止する

今回のサンプルでは、単なる「PythonからJavaScriptを1回呼ぶ」処理だけでなく、

- JavaScript → Python
- Python → JavaScript
- 別スレッドでの繰り返し処理
- `threading.Event`による安全な停止
- pywebviewの`js_api`
- `window.run_js()`
- `_serializable = False`

まで含まれている。

そのため、実際のPLC監視アプリのような、Python側で処理を行い、その結果を画面へPushするアプリを理解するための基礎教材として非常に適している。

---

# 2. 完成したアプリの動作

アプリを起動した直後は、画面の時刻表示は次の状態である。

```text
---
```

「開始」ボタンを押すとPython側で時計処理用スレッドが開始される。

その後、1秒ごとにPython側で現在時刻を取得し、JavaScriptへPushする。

```text
2026-08-14 10:30:01
2026-08-14 10:30:02
2026-08-14 10:30:03
...
```

「停止」ボタンを押すと、Python側の繰り返し処理が停止する。

全体の流れは次のようになる。

```text
アプリ起動
    │
    ↓
pywebview画面表示
    │
    │ 「開始」クリック
    ↓
JavaScript
    │
    │ pywebview.api.start_clock()
    ↓
Python AppApi
    │
    │ Clock.start()
    ↓
時計用スレッド開始
    │
    ↓
1秒待機
    │
    ↓
現在時刻取得
    │
    ↓
JSON化
    │
    ↓
window.run_js()
    │
    ↓
JavaScript
    │
    │ window.receiveTime()
    ↓
HTML表示更新
    │
    ↓
1秒待機
    │
   ...
    │
    │ 「停止」クリック
    ↓
JavaScript
    │
    │ pywebview.api.stop_clock()
    ↓
Python
    │
    │ stop_event.set()
    ↓
時計スレッド終了
```

---

# 3. 使用ファイル

今回のサンプルは2ファイルで構成される。

```text
push_clock_sample/
├─ app.py
└─ index.html
```

| ファイル | 役割 |
|---|---|
| `app.py` | pywebview起動、時計処理、スレッド管理、JavaScriptへのPush |
| `index.html` | 画面表示、開始・停止ボタン、Python API呼び出し、Pushデータ受信 |

---

# 4. Python側の完成コード

```python
import json
import threading
from datetime import datetime

import webview


class Clock:
    """時計処理を管理する。"""

    # Python内部用クラスのため、pywebviewのJavaScript API公開対象から除外する。
    _serializable = False

    def __init__(self):
        self.window = None
        self.stop_event = threading.Event()
        self.clock_thread = None

    def set_window(self, window):
        """JavaScriptへPushするためのpywebviewウィンドウを保持する。"""
        self.window = window

    def start(self):
        """時計処理を開始する。"""

        # すでに時計スレッドが動作中なら何もしない
        if (
            self.clock_thread is not None
            and self.clock_thread.is_alive()
        ):
            return

        # 前回の停止要求を解除する
        self.stop_event.clear()

        # 時計処理を別スレッドで開始する
        self.clock_thread = threading.Thread(
            target=self._clock_loop,
            name="clock-thread",
            daemon=True,
        )

        self.clock_thread.start()

    def stop(self):
        """時計処理の停止を要求する。"""
        self.stop_event.set()

    def _clock_loop(self):
        """1秒ごとに現在時刻をJavaScriptへPushする。"""

        while not self.stop_event.wait(1):
            current_time = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            payload = json.dumps(
                current_time,
                ensure_ascii=False,
            )

            if self.window is None:
                continue

            self.window.run_js(
                f"window.receiveTime({payload});"
            )


class AppApi:
    """JavaScriptから呼び出すPython API。"""

    def __init__(self, clock):
        self.clock = clock

    def start_clock(self):
        """JavaScriptから時計処理を開始する。"""
        self.clock.start()

    def stop_clock(self):
        """JavaScriptから時計処理を停止する。"""
        self.clock.stop()


clock = Clock()
api = AppApi(clock)

window = webview.create_window(
    "Push Clock Sample",
    "index.html",
    js_api=api,
)

clock.set_window(window)

webview.start()
```

---

# 5. HTML / JavaScript側の完成コード

```html
<!DOCTYPE html>
<html lang="ja">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Push Clock Sample</title>
</head>

<body>

    <h1>Python Push Clock</h1>

    <p id="time">---</p>

    <button id="start-button" type="button">
        開始
    </button>

    <button id="stop-button" type="button">
        停止
    </button>

    <script>
        const timeElement =
            document.getElementById("time");

        const startButton =
            document.getElementById("start-button");

        const stopButton =
            document.getElementById("stop-button");


        window.receiveTime = function (currentTime) {
            timeElement.textContent = currentTime;
        };


        startButton.addEventListener(
            "click",
            async () => {
                await pywebview.api.start_clock();
            }
        );


        stopButton.addEventListener(
            "click",
            async () => {
                await pywebview.api.stop_clock();
            }
        );
    </script>

</body>

</html>
```

---

# 6. pywebviewの基本構造

pywebviewでは、大きく分けて2方向の通信がある。

```text
JavaScript → Python
Python     → JavaScript
```

この2つは方法が異なる。

---

# 7. JavaScript → Python

JavaScriptからPythonのメソッドを呼ぶ場合は、

```javascript
pywebview.api.メソッド名()
```

を使用する。

今回の開始処理では、

```javascript
await pywebview.api.start_clock();
```

停止処理では、

```javascript
await pywebview.api.stop_clock();
```

としている。

Python側では`AppApi`クラスに同名のメソッドを用意している。

```python
class AppApi:
    def start_clock(self):
        self.clock.start()

    def stop_clock(self):
        self.clock.stop()
```

つまり、

```text
JavaScript
pywebview.api.start_clock()
            │
            ↓
Python
AppApi.start_clock()
            │
            ↓
Clock.start()
```

という呼び出しになる。

---

# 8. `js_api=api`とは何か

Python側では次のようにウィンドウを作成している。

```python
window = webview.create_window(
    "Push Clock Sample",
    "index.html",
    js_api=api,
)
```

この、

```python
js_api=api
```

が重要である。

これは、

> `api`オブジェクトの公開可能なメソッドをJavaScript側から呼べるようにする

という指定である。

今回、

```python
api = AppApi(clock)
```

なので、JavaScript側から、

```javascript
pywebview.api.start_clock()
pywebview.api.stop_clock()
```

を呼ぶことができる。

---

# 9. Python → JavaScript

今回の中心テーマがこちらである。

Python側からJavaScriptへPushする場合、

```python
window.run_js()
```

を使用している。

今回のコードは、

```python
self.window.run_js(
    f"window.receiveTime({payload});"
)
```

である。

このコードは、Pythonが直接HTMLを書き換えているわけではない。

Python側から、

```javascript
window.receiveTime(...)
```

というJavaScriptコードを実行させている。

---

# 10. JavaScript側の受信関数

JavaScript側には、あらかじめ次の関数を用意している。

```javascript
window.receiveTime = function (currentTime) {
    timeElement.textContent = currentTime;
};
```

Python側が、

```python
self.window.run_js(
    f"window.receiveTime({payload});"
)
```

を実行すると、この関数が呼ばれる。

たとえばPython側の時刻が、

```text
2026-08-14 10:30:15
```

だった場合、JavaScript側では実質的に、

```javascript
window.receiveTime("2026-08-14 10:30:15");
```

が実行されるイメージになる。

---

# 11. Pushとは何か

今回「Push」と呼んでいる処理は、

> JavaScript側から要求されるのを待つのではなく、Python側のタイミングでJavaScriptへ通知する

方式である。

通常のJavaScript → Pythonは、

```text
ユーザー操作
    ↓
JavaScript
    ↓
Pythonへ要求
```

である。

一方、Pushは、

```text
Python側でイベント発生
    ↓
Python
    ↓
JavaScriptへ通知
```

となる。

今回なら、

```text
1秒経過
    ↓
Pythonが現在時刻取得
    ↓
PythonからJavaScriptへPush
```

となる。

PLCアプリであれば、

```text
PLC受信要求ON
    ↓
PythonがPLCデータ受信
    ↓
PythonからJavaScriptへPush
    ↓
Chart.js更新
```

という構造になる。

---

# 12. なぜJSONに変換するのか

Python側では、

```python
payload = json.dumps(
    current_time,
    ensure_ascii=False,
)
```

としている。

`json.dumps()`はPythonオブジェクトをJSON形式の文字列へ変換する関数である。

実際のアプリでは、

```python
{
    "data_name": "motor1",
    "measured_at": "2026-08-14 10:30:00",
    "values": [100, 200, 300]
}
```

のようなPythonの辞書をJavaScriptへ渡す場合に特に重要になる。

Pythonの`dict`とJavaScriptのObjectは似ているが、同じものではない。

そのため、

```text
Pythonオブジェクト
      ↓
json.dumps()
      ↓
JSON
      ↓
JavaScript
```

という形で受け渡すと安全で分かりやすい。

---

# 13. `ensure_ascii=False`

`ensure_ascii=False`を指定すると、日本語などのUnicode文字を読みやすい形のままJSON化できる。

たとえば、

```python
message = "受信完了"
```

のような文字列をJavaScriptへ渡す場合にも便利である。

---

# 14. なぜ別スレッドが必要なのか

今回、時計処理は、

```python
self.clock_thread = threading.Thread(
    target=self._clock_loop,
    name="clock-thread",
    daemon=True,
)
```

で別スレッドとして実行している。

もし開始処理の中で直接、

```python
while True:
    ...
```

と長時間続くループを実行すると、開始処理が戻ってこなくなる。

GUIアプリでは、

- 画面操作
- ボタン入力
- Python側処理
- JavaScriptとの通信

を止めないことが重要である。

そのため、継続的に動く処理は別スレッドへ分離する。

---

# 15. `threading.Thread`

時計スレッドは次のコードで作成している。

```python
self.clock_thread = threading.Thread(
    target=self._clock_loop,
    name="clock-thread",
    daemon=True,
)
```

## `target`

```python
target=self._clock_loop
```

は、このスレッドで実行する関数を指定する。

`()`は付けない。

正しい例：

```python
target=self._clock_loop
```

誤った例：

```python
target=self._clock_loop()
```

後者ではスレッド開始前に関数を実行してしまう。

---

# 16. `start()`

スレッドオブジェクトを作成しただけでは処理は始まらない。

```python
self.clock_thread.start()
```

を実行して初めて別スレッドが開始する。

```text
Thread(...)
    ↓
スレッドオブジェクト作成

start()
    ↓
別スレッド開始

_clock_loop()
    ↓
実行
```

---

# 17. `is_alive()`

開始処理には、

```python
if (
    self.clock_thread is not None
    and self.clock_thread.is_alive()
):
    return
```

がある。

これは、すでに時計処理が動いているときに、さらにもう1本時計スレッドを起動しないための処理である。

これがない場合、開始ボタンを何度も押すと複数の時計スレッドが起動する可能性がある。

---

# 18. `threading.Event`

今回の停止処理では、

```python
self.stop_event = threading.Event()
```

を使用している。

`Event`はスレッド間でON/OFF状態を共有するための仕組みと考えると分かりやすい。

| メソッド | 意味 |
|---|---|
| `set()` | EventをONにする |
| `clear()` | EventをOFFにする |
| `is_set()` | ONか確認する |
| `wait()` | ONになるまで待つ |

---

# 19. 開始時の`clear()`

時計処理開始時には、

```python
self.stop_event.clear()
```

を実行している。

停止ボタンを一度押すと、

```python
self.stop_event.set()
```

によりEventはONになる。

そのため再開時には、

```python
clear()
```

でOFFへ戻す必要がある。

---

# 20. 停止時の`set()`

停止処理は、

```python
def stop(self):
    self.stop_event.set()
```

である。

スレッドを外部から強制終了しているわけではない。

あくまで、

> 停止してください

という要求をEventで通知し、時計スレッド自身が終了する。

---

# 21. `Event.wait(1)`が重要

時計ループは、

```python
while not self.stop_event.wait(1):
```

となっている。

意味は、

> EventがONになるまで最大1秒待つ

である。

1秒経過してもEventがOFFなら`wait(1)`は`False`を返す。

停止ボタンが押されてEventがONになると、`wait()`は`True`を返す。

そのため`while`条件がFalseになり、ループが終了する。

---

# 22. `time.sleep(1)`との違い

単純に、

```python
time.sleep(1)
```

でも待機はできる。

しかしsleep中に停止要求が来ても、sleepが終わるまで待たなければならない。

一方、

```python
self.stop_event.wait(1)
```

なら、待機中にEventがONになると、その時点で待機を解除できる。

停止可能な繰り返し処理では`Event.wait()`が非常に便利である。

---

# 23. `daemon=True`

今回の時計スレッドには、

```python
daemon=True
```

を指定している。

daemonスレッドは、メインプログラム終了時に、そのスレッドだけが残っていてもPythonプロセス終了を妨げない。

学習用時計処理のような補助処理では便利である。

ただし、ファイル保存やDB書込みのように必ず最後まで完了させたい処理では、安易にdaemonへ任せない方がよい。

---

# 24. `Clock`クラスの役割

`Clock`クラスが担当しているのは、

- pywebviewの`window`保持
- 停止用Event
- 時計用Thread
- 時計開始
- 時計停止
- 1秒周期処理
- JavaScriptへのPush

である。

つまり時計処理の実体を担当するクラスである。

---

# 25. `AppApi`クラスの役割

`AppApi`は、JavaScriptからPythonへ入ってくるための窓口である。

```python
def start_clock(self):
    self.clock.start()

def stop_clock(self):
    self.clock.stop()
```

という最小限のAPIだけを持つ。

```text
JavaScript
    ↓
AppApi
    ↓
Clock
```

という役割分担になっている。

---

# 26. なぜ`AppApi`と`Clock`を分けるのか

最初は`AppApi`自身に時計処理、Thread、Event、`window`をすべて持たせた。

しかし今回、それがpywebviewのシリアライズ処理に関連する再帰エラーにつながった。

そこで、

```text
AppApi
    │ JavaScript公開用
    ↓
Clock
    │ Python内部処理用
```

と役割を分離した。

この構造は実際のアプリでも有効である。

---

# 27. `set_window()`

`Clock`には、

```python
def set_window(self, window):
    self.window = window
```

がある。

PythonからJavaScriptへPushするには、

```python
window.run_js()
```

を実行する必要があるため、`Clock`がpywebviewの`window`オブジェクトを保持する。

---

# 28. `self.window is None`の確認

Push前には、

```python
if self.window is None:
    continue
```

を入れている。

`window`が未設定のまま、

```python
self.window.run_js(...)
```

を実行するとエラーになるため、安全確認として入れている。

---

# 29. HTML側のDOM取得

HTML側では、

```javascript
const timeElement =
    document.getElementById("time");
```

として表示場所を取得する。

HTMLでは、

```html
<p id="time">---</p>
```

となっている。

JavaScriptから、

```javascript
timeElement.textContent = currentTime;
```

とすることで表示文字列を書き換える。

---

# 30. 開始ボタンと停止ボタン

開始ボタン：

```javascript
startButton.addEventListener(
    "click",
    async () => {
        await pywebview.api.start_clock();
    }
);
```

停止ボタン：

```javascript
stopButton.addEventListener(
    "click",
    async () => {
        await pywebview.api.stop_clock();
    }
);
```

JavaScript側のボタン操作からPython APIを呼び出している。

---

# 31. `async` / `await`

pywebviewのPython API呼び出しはPromiseとして扱われる。

そのため、

```javascript
async () => {
    await pywebview.api.start_clock();
}
```

としている。

これは、Python側のAPI呼び出し完了を待つ形である。

---

# 32. 今回発生した不具合 その1
## JavaScriptのIDタイプミス

途中のコードでは、

```javascript
const stopButton =
    document.getElementById("stopButton");
```

となっていた。

しかしHTML側は、

```html
id="stop-button"
```

だった。

`getElementById()`は完全一致なので、この場合は対象を取得できず`null`になる。

### 教訓

```text
HTML
id="stop-button"

JavaScript
getElementById("stop-button")
```

のように完全一致させる。

---

# 33. 今回発生した不具合 その2
## pywebviewの再帰エラー

起動時に次のようなエラーが大量に表示された。

```text
[pywebview] Error while processing
window.native.AccessibilityObject.Bounds.Empty.Empty.Empty...
maximum recursion depth exceeded
```

特徴は、`window.native.AccessibilityObject`から始まり、内部オブジェクトを延々と辿っていることである。

---

# 34. `maximum recursion depth exceeded`とは

Pythonには再帰処理の深さに上限がある。

例えば、

```python
def test():
    test()
```

のように自分自身を無限に呼び出すと、最終的に再帰深度の上限へ達する。

今回のpywebviewエラーも、オブジェクト内部を延々と辿った結果として再帰深度上限へ到達したものと考えられる。

---

# 35. 最初の問題構造

最初は`AppApi`自身が、

```python
self.window
self.stop_event
self.clock_thread
```

を持っていた。

さらに、

```python
js_api=api
```

として、その`AppApi`をJavaScript APIへ直接公開していた。

概念的には、

```text
js_api
  ↓
AppApi
  ↓
self.window
  ↓
pywebview.Window
  ↓
native
  ↓
AccessibilityObject
  ↓
Bounds
  ↓
...
```

とpywebview内部の複雑なオブジェクトまで解析対象になった。

---

# 36. 最初に試した対策

最初は、

```python
class AppApi:
    _serializable = False
```

とした。

しかし、この形では問題は解消しなかった。

今回の構造では、`js_api`として直接公開する`AppApi`自身に指定するだけでは期待した回避にならなかった。

---

# 37. 正しく動作した回避策

最終的には、

```text
AppApi
    ↓
Clock
```

とクラスを分離した。

そしてPython内部用の`Clock`に、

```python
_serializable = False
```

を指定した。

```python
class Clock:
    _serializable = False
```

構造は、

```text
js_api
  ↓
AppApi
  │
  └─ self.clock
        ↓
      Clock
      _serializable = False
        │
        ├─ self.window
        ├─ self.stop_event
        └─ self.clock_thread
```

となる。

これにより、`Clock`内部の`self.window`などをJavaScript API用の解析対象から外す境界を作ることができ、再帰エラーを回避できた。

---

# 38. `_serializable = False`の意味

今回の理解としては、

```python
_serializable = False
```

は、

> このPython内部オブジェクトを、JavaScriptへ公開するための解析対象にしない

ために使う、と覚えると分かりやすい。

特に、

- `webview.Window`
- Thread
- Event
- Lock
- Executor
- 独自通信オブジェクト

など、JavaScriptへ直接公開する必要がない内部オブジェクトを持つクラスでは重要になる場合がある。

---

# 39. JavaScriptへ公開するものを最小限にする

今回の設計上の重要な教訓は、

> `js_api`として公開するクラスには、JavaScriptから呼ぶ必要のある窓口だけを持たせる

ことである。

今回なら、

```python
class AppApi:
    def start_clock(self):
        ...

    def stop_clock(self):
        ...
```

だけで十分である。

内部処理は`Clock`へ任せる。

```text
JavaScriptに公開
       │
       ↓
   AppApi
       │
       ↓
Python内部
       │
       ↓
    Clock
```

この構造にすると責務も明確になり、保守しやすい。

---

# 40. 今回の設計をPLCアプリへ置き換える

時計サンプル：

```text
開始ボタン
    ↓
AppApi
    ↓
Clock
    ↓
Thread
    ↓
現在時刻取得
    ↓
run_js()
    ↓
JavaScript
```

PLCアプリ：

```text
監視開始ボタン
    ↓
AppApi
    ↓
DataReceiver
    ↓
Thread / ThreadPoolExecutor
    ↓
PLCデータ受信
    ↓
run_js()
    ↓
JavaScript
    ↓
Chart.js
```

つまり時計サンプルは、

> PLC通信を現在時刻取得へ置き換えた最小モデル

と考えることができる。

---

# 41. Pushの本質

PythonからJavaScriptへPushする基本形は、

Python：

```python
window.run_js(
    "window.receiveData(...);"
)
```

JavaScript：

```javascript
window.receiveData = function (data) {
    ...
};
```

である。

```text
Python
    ↓
run_js()
    ↓
JavaScript関数を実行
    ↓
JavaScriptで画面更新
```

となる。

---

# 42. 双方向通信の整理

## JavaScript → Python

```javascript
await pywebview.api.start_clock();
```

```text
JavaScript
    ↓
pywebview.api
    ↓
Python
```

## Python → JavaScript

```python
window.run_js(
    "window.receiveTime(...);"
)
```

```text
Python
    ↓
window.run_js()
    ↓
JavaScript
```

この2方向を組み合わせることで、

```text
操作はJavaScriptからPythonへ
結果はPythonからJavaScriptへPush
```

というGUIアプリを作ることができる。

---

# 43. 今回のプログラムで覚えておきたいポイント

1. `js_api=api`でPythonメソッドをJavaScriptへ公開する。
2. JavaScriptからPythonを呼ぶときは`pywebview.api.xxx()`を使う。
3. PythonからJavaScriptを呼ぶときは`window.run_js()`を使う。
4. JavaScript側にはPythonから呼ばれる受信関数を用意する。
5. Pythonオブジェクトを渡す場合は`json.dumps()`でJSON化すると扱いやすい。
6. 長時間動く繰り返し処理は別スレッドにする。
7. スレッド停止には`threading.Event`が便利。
8. `Event.wait(interval)`を使うと待機中でも素早く停止できる。
9. `is_alive()`で多重起動を防止する。
10. JavaScriptへ公開する`AppApi`には必要最小限のAPIだけを持たせる。
11. `Window`、Thread、EventなどPython内部オブジェクトはJavaScriptへ公開しない。
12. 内部処理クラスには必要に応じて`_serializable = False`を指定する。
13. HTMLの`id`と`getElementById()`の文字列は完全一致させる。
14. `maximum recursion depth exceeded`で`window.native...`が延々続く場合は、pywebviewが内部オブジェクトを解析していないか疑う。

---

# 44. まとめ

今回の時計アプリは小さなプログラムだが、pywebviewアプリの重要な基本構造が詰まっている。

```text
JavaScript
    │
    │ 操作
    ↓
AppApi
    │
    ↓
Python内部処理クラス
    │
    │ 別スレッド
    ↓
処理実行
    │
    │ run_js()
    ↓
JavaScript
    │
    ↓
画面更新
```

特に重要なのは、

```text
JavaScript → Python
```

と、

```text
Python → JavaScript
```

を別の仕組みとして理解することである。

さらに今回の不具合から、

```text
JavaScript公開用クラス
        ↓
Python内部処理クラス
```

と役割を分け、

```python
_serializable = False
```

によってPython内部オブジェクトをpywebviewの解析対象から外す設計の重要性も確認できた。

この考え方は、

- PLC監視
- データ収集
- センサー監視
- SQLite登録
- Chart.jsによるリアルタイムグラフ
- バックグラウンド処理
- 装置状態監視

などのpywebviewアプリへそのまま応用できる。

今回の時計サンプルは、これらのアプリを理解するための最小モデルとして保存しておく価値がある。
