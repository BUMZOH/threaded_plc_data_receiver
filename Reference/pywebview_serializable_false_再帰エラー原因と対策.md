# pywebviewで `_serializable = False` が必要になった理由
## Chart.js追加時に発生した大量エラーの原因と対策

## 1. はじめに

今回、pywebviewアプリへChart.jsによるモータ電流値グラフ表示を追加したところ、アプリ自体は正常に動作しているにもかかわらず、コンソールへ大量のエラーが出力されました。

代表的なエラーは次のようなものでした。

```text
[pywebview] Error while processing receiver.window.native...
maximum recursion depth exceeded
```

また、

```text
CoreWebView2Controller members can only be accessed from the UI thread
```

というエラーも出ていました。

一見すると、

```text
Chart.jsが悪い？
JavaScriptが悪い？
run_js()が悪い？
WebView2が壊れている？
```

と考えたくなります。

しかし、実際の原因は別のところにありました。

結論から言うと、

> **pywebviewが `js_api` オブジェクトの内部をJavaScript公開用として調べていく途中で、`MotorReceiver` が保持していた `webview.Window` の内部まで深く辿ってしまった**

ことが原因でした。

そして、

```python
_serializable = False
```

を `MotorReceiver` に追加することで、

> **MotorReceiverはJavaScriptへ公開・解析しないPython内部用クラスである**

とpywebviewへ伝えられたため、エラーが解消しました。

---

## 2. Chart.js追加前の構成

Chart.js追加前のアプリでは、概ね次のような構成でした。

```text
JavaScript
    ↓
pywebview.api.start_monitoring()
    ↓
AppApi
    ↓
MotorReceiver
    ↓
PLC通信
```

Python側では、

```python
api = AppApi(receiver)
```

として、

```python
window = webview.create_window(
    ...,
    js_api=api,
)
```

としています。

ここで重要なのが、

```python
js_api=api
```

です。

これは、

> `AppApi` オブジェクトをJavaScriptから呼び出せるAPIとしてpywebviewへ渡す

という意味です。

---

## 3. `AppApi` は `MotorReceiver` を持っている

`AppApi` の中では、

```python
class AppApi:
    def __init__(self, receiver: MotorReceiver) -> None:
        self.receiver = receiver
```

となっています。

つまりオブジェクトの参照関係は、

```text
AppApi
  │
  └── receiver
        │
        └── MotorReceiver
```

です。

この時点では `MotorReceiver` の中に、

```text
PLC IPアドレス
ThreadPoolExecutor
Event
Lock
状態辞書
```

などが入っています。

Chart.js追加前は、この構成でも大きな問題は表面化していませんでした。

---

## 4. Chart.js対応で何を追加したか

Chart.jsで、

```text
Pythonで1000点受信
        ↓
すぐJavaScriptへPush
        ↓
Chart.js更新
```

を実現するため、Python側からJavaScriptを呼ぶ必要がありました。

そのため `MotorReceiver` に、

```python
self.window: webview.Window | None = None
```

を追加しました。

さらに、

```python
def set_window(self, window: webview.Window) -> None:
    self.window = window
```

として、`main()` で作成したpywebview Windowを渡しました。

```python
receiver.set_window(window)
```

これによって、参照関係が次のようになりました。

```text
AppApi
  │
  └── receiver
        │
        └── MotorReceiver
              │
              └── window
                    │
                    └── webview.Window
```

この変更が今回の重要ポイントです。

---

## 5. なぜ `window` を持たせたら問題になったのか

`webview.Window` は単純なデータではありません。

内部には概念的に、

```text
ネイティブウィンドウ
WebView2
アクセシビリティ情報
ブラウザコントローラ
イベント
OS側オブジェクト
```

など、多数の複雑なオブジェクトへの参照があります。

イメージすると、

```text
webview.Window
   │
   ├── native
   │     │
   │     ├── browser
   │     ├── AccessibilityObject
   │     ├── Bounds
   │     ├── Parent
   │     └── ...
   │
   ├── events
   ├── gui
   └── ...
```

のような巨大なオブジェクトです。

しかも、その内部には循環参照や、さらに別の巨大なオブジェクトへの参照が含まれる場合があります。

---

## 6. pywebview側では何が起きたのか

今回の `AppApi` は、

```python
js_api=api
```

としてpywebviewへ渡されています。

つまりpywebview側から見ると、

```text
AppApi
```

は、

> JavaScriptへ公開するために調べる対象

です。

そして `AppApi` の内部には、

```python
self.receiver
```

があります。

そのため、概念的にはpywebviewが、

```text
AppApi
 ↓
receiver
 ↓
MotorReceiver
 ↓
window
 ↓
webview.Window
 ↓
native
 ↓
さらに内部……
```

と辿っていきました。

実際のエラーログにも、

```text
receiver.window.native.AccessibilityObject.Bounds.Empty.Empty.Empty...
```

のような非常に長いパスが出ていました。

これは、

> pywebviewが `receiver` の中へ入り、その中の `window`、さらに `native` の内部まで解析しようとしていた

ことを示しています。

---

## 7. `maximum recursion depth exceeded` の意味

Pythonには、再帰的な処理を深く繰り返しすぎないため、再帰の深さに上限があります。

今回ログに出た、

```text
maximum recursion depth exceeded
```

は、

> **オブジェクトの内部を辿る処理が深くなりすぎた**

という意味です。

今回のイメージでは、

```text
AppApi
 ↓
receiver
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
……
```

のように、延々と深く探索してしまいました。

その結果、

```text
これ以上深く辿れない
```

となり、

```text
maximum recursion depth exceeded
```

が発生しました。

---

## 8. なぜ同じ名前が延々と続いていたのか

エラーログでは、

```text
Bounds.Empty.Empty.Empty.Empty.Empty...
```

や、

```text
Alert.Alert.Alert.Alert...
```

のような不自然な繰り返しが見えていました。

これは通常のアプリ処理ではありません。

pywebviewが内部オブジェクトをJavaScript公開用として調べる過程で、

```text
あるオブジェクト
 ↓
その属性
 ↓
さらにその属性
 ↓
……
```

と深く辿り続けていたことを示す重要な手掛かりです。

このログを見たときは、

> **自分のコードが無限ループしているのではなく、オブジェクト解析・シリアライズ側が再帰している可能性**

も疑う必要があります。

---

## 9. WebView2のUI Threadエラーも同じ流れ

ログには、

```text
CoreWebView2Controller members can only be accessed from the UI thread
```

というエラーもありました。

これは、

> WebView2の一部機能はUIスレッドからしかアクセスしてはいけない

という意味です。

今回、pywebviewが `window.native` の内部まで調べに行った結果、本来こちらから触る必要のないWebView2内部プロパティまでアクセスしてしまいました。

そのため、

```text
UIスレッド以外から触らないでください
```

というエラーも副次的に発生したと考えられます。

つまり、

```text
maximum recursion depth exceeded
```

と、

```text
CoreWebView2Controller members can only be accessed from the UI thread
```

は別々の根本原因ではなく、

```text
pywebviewがwebview.Windowの内部まで解析してしまった
```

ことから派生した症状と考えると理解しやすくなります。

---

## 10. なぜアプリ自体は正常に動いていたのか

今回ややこしかったのは、

> **大量のエラーが出ていたのに、Chart.js表示やPLC通信自体は正常に動いていた**

ことです。

本来やりたい処理である、

```text
PLCから1000点受信
 ↓
Python
 ↓
run_js()
 ↓
JavaScript
 ↓
Chart.js
```

は正常に動いていました。

一方で、

```text
js_api公開用の解析
```

という別の場所で、余計な `receiver.window` の内部探索が走っていました。

したがって、

```text
本体処理       → 正常
余計なAPI解析   → エラー
```

という状態になっていました。

これが、

> エラーは大量に出るがアプリは正常に動く

という不思議な現象の理由です。

---

## 11. `_serializable = False` とは何か

今回の解決策が、

```python
_serializable = False
```

です。

`MotorReceiver` に、

```python
class MotorReceiver:
    """PLC要求監視とモータ電流データ受信を管理する。"""

    _serializable = False
```

と追加しました。

この設定によってpywebviewへ、

> **このオブジェクトはJavaScript APIとして公開・シリアライズする対象ではありません**

という意図を伝えます。

すると、

```text
AppApi
  │
  └── receiver
        │
        × ここから先は解析しない
```

となります。

そのため、

```text
MotorReceiver
 ↓
window
 ↓
native
 ↓
WebView2
```

へ進まなくなります。

結果として、大量の再帰エラーもWebView2内部アクセスエラーも消えました。

---

## 12. 修正前と修正後

### 修正前

```text
js_api=AppApi
      │
      ↓
   AppApi
      │
      └── receiver
             │
             ↓
        MotorReceiver
             │
             └── window
                    │
                    ↓
              webview.Window
                    │
                    ↓
                 native
                    │
                    ↓
                  ...
                深く解析
                    │
                    ↓
               エラー発生
```

### 修正後

```text
js_api=AppApi
      │
      ↓
   AppApi
      │
      ├── start_monitoring()
      ├── stop_monitoring()
      ├── get_status()
      │
      └── receiver
             │
             ×
      _serializable = False
      ここから先は解析しない
```

---

## 13. JavaScriptへ公開したいものと公開したくないもの

今回のアプリでは、JavaScriptへ公開したいのは `AppApi` です。

```text
JavaScript
    ↓
AppApi.start_monitoring()
AppApi.stop_monitoring()
AppApi.get_status()
```

一方、

```text
MotorReceiver
ThreadPoolExecutor
threading.Event
threading.Lock
webview.Window
PLC通信処理
```

はJavaScriptから直接触る必要がありません。

したがって役割として、

```text
AppApi
    → JavaScriptへ公開する境界

MotorReceiver
    → Python内部の業務処理
```

と分けるのが自然です。

---

## 14. 今回の設計上の重要ポイント

今回の問題は、Chart.jsそのものが原因ではありません。

より正確には、

```text
Chart.jsを追加
    ↓
PythonからJSへPushしたくなった
    ↓
MotorReceiverにwebview.Windowを保持させた
    ↓
AppApi.receiver経由でpywebviewがWindow内部まで解析
    ↓
大量エラー
```

という流れです。

つまり、

```text
Chart.js
```

は直接の原因ではなく、

```text
Chart.js対応のために追加した
Python → JavaScript Push用のWindow参照
```

が問題を表面化させました。

---

## 15. 今後同じ問題を避けるための考え方

pywebviewで、

```python
window = webview.create_window(
    ...,
    js_api=api,
)
```

とした場合、

> `api` はJavaScriptとの境界になるオブジェクト

と意識します。

そして `api` の内部に別オブジェクトを保持する場合、

```text
そのオブジェクトもJavaScriptへ公開する必要があるか？
```

を考えます。

必要がなければ、

```python
_serializable = False
```

を検討します。

特に次のような複雑なオブジェクトを持つクラスには注意します。

```text
GUI Window
WebView
Socket
Thread
Lock
Executor
DB接続
OSオブジェクト
外部ライブラリの巨大オブジェクト
```

これらはJavaScriptへシリアライズする目的のデータではありません。

---

## 16. `self.window` を持たせること自体が悪いのか

いいえ。

今回、

```python
self.window = window
```

としてPythonから、

```python
self.window.run_js(...)
```

を使うこと自体は問題ありません。

実際、この仕組みによって、

```text
PLCデータ受信
 ↓
Python
 ↓
JavaScriptへPush
 ↓
Chart.js即時描画
```

を実現できています。

問題だったのは、

```text
MotorReceiverがwindowを持っている
```

ことではなく、

```text
そのMotorReceiverをpywebviewが
JavaScript API公開対象として解析しようとした
```

ことです。

したがって、

```python
_serializable = False
```

によって役割を明確にすれば、`window` を保持したままで問題ありません。

---

## 17. 今回のコメント例

```python
# Python内部用クラスのため、pywebviewのJavaScript API公開対象から除外する。
# window内部まで解析されて再帰エラーになることを防ぐ。
_serializable = False
```

この2行には今回の原因と対策がほぼ凝縮されています。

---

## 18. エラー発生時の調査ポイント

今回のようなログが出た場合は、次を確認するとよいです。

```text
1. エラー文字列に自分のオブジェクト名があるか
   例: receiver.window.native...

2. 同じ属性名が異常に繰り返されていないか
   例: Empty.Empty.Empty...
       Alert.Alert.Alert...

3. maximum recursion depth exceeded があるか

4. js_apiへ渡しているオブジェクトが
   複雑なオブジェクトを内部に保持していないか

5. JavaScriptへ公開する必要がないクラスを
   pywebviewが解析していないか
```

このパターンなら `_serializable = False` が有力な確認ポイントになります。

---

## 19. 今回の問題を一言で表すと

今回の問題は、

> **Python内部だけで使いたい `MotorReceiver` を、pywebviewがJavaScript公開用オブジェクトとして深く解析してしまった**

ことです。

さらに `MotorReceiver` が `webview.Window` を持つようになったため、

```text
Window
 ↓
native
 ↓
WebView2
 ↓
OS内部オブジェクト
```

まで探索範囲が広がり、再帰エラーが表面化しました。

---

## 20. 最終的な正しい構成

```text
                JavaScript
                    │
                    │ pywebview.api
                    ↓
                AppApi
          JavaScript公開用API
                    │
                    ↓
              MotorReceiver
          _serializable = False
             Python内部用
                    │
        ┌───────────┴───────────┐
        ↓                       ↓
     PLC通信                webview.Window
                                │
                                │ run_js()
                                ↓
                            JavaScript
                                ↓
                             Chart.js
```

この構成なら、

```text
JS → Python
```

は `AppApi` を通し、

```text
Python → JS
```

は `window.run_js()` を使います。

`MotorReceiver` はJavaScriptへ直接公開せず、Python内部の処理クラスとして扱います。

---

## 21. 忘備録用まとめ

```text
【症状】

Chart.js追加後、
アプリは正常に動作するが
pywebviewから大量エラー。

maximum recursion depth exceeded
CoreWebView2Controller members can only be accessed from the UI thread


【直接の原因】

Chart.jsそのものではない。


【問題が起きた流れ】

Chart.js表示のためPython→JS Pushが必要
        ↓
MotorReceiverにwebview.Windowを保持
        ↓
AppApiはMotorReceiverを保持
        ↓
AppApiはjs_apiとしてpywebviewへ公開
        ↓
pywebviewがreceiver内部も解析
        ↓
receiver.window.native...
まで深く探索
        ↓
再帰エラー


【対策】

MotorReceiverへ追加

_serializable = False


【意味】

MotorReceiverはPython内部用。

JavaScript APIとして
内部まで解析・公開しない。


【結果】

receiver.window内部を探索しなくなり
大量エラーが解消。


【覚えておくこと】

pywebviewのjs_apiオブジェクトが
複雑な内部オブジェクトを持つ場合は、

「本当にJSへ公開する必要があるか？」

を考える。

不要なら
_serializable = False
を検討する。
```

---

## 22. まとめ

今回のエラーは、Chart.jsの描画処理そのものではありませんでした。

Chart.js追加をきっかけにPythonからJavaScriptへPushするため、

```python
self.window = window
```

という参照を `MotorReceiver` に持たせました。

一方、`MotorReceiver` は、

```python
AppApi.receiver
```

として、`js_api` に渡されている `AppApi` の内部に存在していました。

そのためpywebviewが、

```text
AppApi
 ↓
receiver
 ↓
MotorReceiver
 ↓
window
 ↓
native
 ↓
WebView2内部
```

までJavaScript公開用として解析しようとし、深すぎる再帰やUIスレッド制約のエラーを発生させました。

そこで、

```python
_serializable = False
```

を `MotorReceiver` に追加し、

> **このクラスはPython内部用であり、JavaScriptへ公開・解析する対象ではない**

と明示しました。

これによってpywebviewが `receiver` の内部を深く探索しなくなり、エラーが解消しました。

今後は、

> **`js_api` へ渡すオブジェクトと、Python内部だけで使うオブジェクトの境界を明確にする**

ことが重要です。

今回の `_serializable = False` は、単なるエラー回避ではなく、

```text
AppApi
    → JavaScript公開用

MotorReceiver
    → Python内部用
```

という設計上の役割を明確にする設定として覚えておくと理解しやすくなります。
