# Pythonで高速にグラフ描画する方法

## 1. はじめに

PythonアプリでPLCやセンサーから取得した波形データを表示する場合、単に「グラフを描ければよい」だけでなく、用途によっては

- PLCからデータを受信した直後に表示したい
- 数千点程度の波形を高速に更新したい
- UIを固まらせたくない
- SQLiteへの保存も同時に行いたい
- 将来的に複数設備・複数波形へ拡張したい

といった要求が発生する。

特にpywebviewアプリでは、

- Python側でmatplotlibを使って画像を生成する方法
- JavaScript側のグラフライブラリで直接描画する方法

のどちらを採用するかによって、表示速度やアプリ構成が大きく変わる。

本書では、約2,000点程度のPLC波形データを高速表示する用途を中心に、Pythonで利用できる代表的なグラフ描画方法を比較し、今後のpywebviewアプリにおける標準的な設計方針をまとめる。

---

# 2. 結論

今後のpywebviewアプリで、PLC・センサー波形などを高速表示する場合は、原則として次の構成を推奨する。

```text
PLC
 ↓
Python
 ↓
数値データ（listなど）
 ↓
pywebview
 ↓
JavaScript
 ↓
uPlot / Chart.js
 ↓
Canvasへ直接描画
```

特に波形表示を重視する場合は、

```text
pywebview
+
HTML / CSS / JavaScript
+
uPlot
```

を第一候補とする。

2,000点程度の波形であれば、JavaScript側での描画負荷は十分小さい。

一方、従来の

```text
Python
 ↓
matplotlib
 ↓
PNG画像生成
 ↓
Base64変換
 ↓
pywebview
 ↓
<img>表示
```

という方式は、静的なグラフ表示には便利だが、PLC受信後に最短で波形を更新する用途には不向きである。

---

# 3. matplotlib → Base64方式

## 3.1 基本的な流れ

Python側でmatplotlibを使用する場合、一般的には次のような処理になる。

```text
PLCからデータ受信
 ↓
Pythonでデータ加工
 ↓
matplotlibでグラフ描画
 ↓
PNG画像へ変換
 ↓
BytesIOへ保存
 ↓
Base64エンコード
 ↓
Python → JavaScriptへ渡す
 ↓
ブラウザ側で画像としてデコード
 ↓
<img>要素へ表示
```

例えばPython側では次のような処理を行う。

```python
from io import BytesIO
import base64

buffer = BytesIO()

fig.savefig(
    buffer,
    format="png",
)

image_base64 = base64.b64encode(
    buffer.getvalue()
).decode("utf-8")
```

JavaScript側ではBase64文字列を`img`タグへ設定する。

---

## 3.2 matplotlib方式の長所

matplotlib自体が遅いライブラリというわけではない。

むしろ以下の用途には非常に優れている。

- 分析用グラフ
- レポート作成
- PNG保存
- 帳票
- 静的グラフ
- 複雑な軸設定
- 注釈付きグラフ
- Pythonのみで完結する処理

例えば、

```text
SQLite
 ↓
Python
 ↓
matplotlib
 ↓
PNG / Base64
 ↓
ダッシュボード表示
```

のように、更新頻度が低い用途では十分実用的である。

---

# 4. matplotlib → Base64方式がリアルタイム表示に不利な理由

PLC波形のように、

```text
データ受信
 ↓
即表示
```

を求める場合、matplotlib方式では途中処理が多い。

本来必要なのは、

```text
2,000個の数値
 ↓
画面上の線
```

だけである。

しかしmatplotlib方式では、

```text
数値
 ↓
matplotlib描画
 ↓
画像
 ↓
PNG圧縮
 ↓
Base64文字列
 ↓
画像へ復元
 ↓
表示
```

という変換が発生する。

これはリアルタイム波形表示としては遠回りである。

---

# 5. Base64変換のコスト

Base64はバイナリデータを文字列として扱える便利な方式である。

しかしBase64化すると、データサイズは元のバイナリデータより概ね約33%増える。

例えば、

```text
PNG
100 KB
```

だった場合、

```text
Base64
約133 KB
```

程度になる。

さらに、

```text
PNG生成
 ↓
Base64エンコード
 ↓
文字列転送
 ↓
Base64デコード
```

という処理も必要になる。

静的画像では問題にならなくても、頻繁な更新では余分な処理になる。

---

# 6. JavaScriptで直接グラフ描画する方法

pywebviewではJavaScriptを使用できる。

そのためPython側では画像を作らず、

```python
values = [
    12.3,
    12.5,
    12.7,
    13.1,
    # ...
]
```

のような数値データをJavaScriptへ渡す。

JavaScript側では、

```javascript
chart.setData(data);
```

のように既存グラフを更新する。

処理の流れは非常にシンプルになる。

```text
PLC
 ↓
Pythonで2,000点取得
 ↓
Python → JavaScript
 ↓
既存グラフへデータ設定
 ↓
Canvas描画
```

---

# 7. JavaScript方式が高速な理由

JavaScriptグラフライブラリでは、

```text
数値
 ↓
Canvas描画
```

という非常に直接的な処理ができる。

matplotlib方式にある、

- Figure作成
- PNG生成
- PNG圧縮
- BytesIO
- Base64変換
- Base64デコード
- img要素更新

などが不要になる。

さらに、グラフそのものを毎回作り直す必要もない。

---

# 8. グラフは毎回作り直さない

高速化で非常に重要なのが、

> グラフオブジェクトは最初に1回だけ作成し、その後はデータだけ更新する

という考え方である。

悪い例：

```javascript
function updateGraph(data) {
    const chart = new Chart(...);
}
```

更新のたびに新しいグラフを生成している。

推奨：

```text
アプリ起動
 ↓
グラフオブジェクト作成
 ↓

PLCデータ受信
 ↓
データだけ差し替える
 ↓
再描画
```

例えば、

```javascript
chart.setData(newData);
```

や、ライブラリに応じた更新APIを使用する。

これにより初期化処理を毎回行う必要がなくなる。

---

# 9. 2,000点程度は大きなデータではない

PLCから約2,000点のデータを受信する場合、

```text
0
1
2
...
1999
```

というXデータと、

```text
12.3
12.4
12.7
...
```

というYデータを描画することになる。

JavaScriptのCanvasベースのグラフライブラリにとって、2,000点程度は十分扱いやすい規模である。

したがって、

> 2,000点あるからpywebviewでは遅い

と考える必要は基本的にない。

むしろボトルネックになりやすいのは、

- PLC通信
- データ変換
- Python → JavaScript間の受け渡し
- SQLiteアクセス
- グラフの作り直し
- PNG / Base64変換

などである。

---

# 10. Chart.js

Chart.jsはJavaScriptの代表的なグラフライブラリである。

特徴：

- 導入しやすい
- ドキュメントが豊富
- 棒グラフ
- 折れ線グラフ
- 円グラフ
- 散布図
- 複数軸
- 凡例
- ツールチップ

などを扱える。

2,000点程度の折れ線グラフであれば十分高速に表示できる。

用途としては、

```text
一般的な業務アプリ
+
グラフ表示
```

に非常に向いている。

---

# 11. uPlot

uPlotは高速な時系列グラフ描画を重視したJavaScriptライブラリである。

特に、

- PLC波形
- モータ電流
- センサーデータ
- 時系列データ
- 大量点の折れ線
- 高速更新

などと相性がよい。

Chart.jsより汎用機能は少ないが、

> 波形を高速に描画する

という目的では非常に魅力的である。

今回のような用途では第一候補として検討する価値が高い。

---

# 12. Chart.jsとuPlotの使い分け

目安として次のように考える。

```text
一般的なグラフ
↓
Chart.js

高速な波形・時系列表示
↓
uPlot
```

比較すると、

| 項目 | Chart.js | uPlot |
|---|---|---|
| 導入しやすさ | ◎ | ○ |
| 情報量 | ◎ | ○ |
| 一般グラフ | ◎ | ○ |
| 波形表示 | ◎ | ◎ |
| 高速更新 | ○〜◎ | ◎ |
| 時系列大量データ | ○ | ◎ |
| UIとの親和性 | ◎ | ◎ |

2,000点程度であれば両者とも十分高速である。

---

# 13. Tkinterとの比較

TkinterはPython標準のGUIライブラリである。

しかし、

> Tkinterだからグラフが高速

というわけではない。

例えば、

```text
Tkinter
+
matplotlib
```

の場合、

```text
PLC
 ↓
Python
 ↓
matplotlib
 ↓
Tkinter Canvas
```

となる。

結局グラフ生成はmatplotlibが担当するため、matplotlibの描画コストは残る。

そのため高速波形表示では、

```text
pywebview
+
JavaScript
+
Canvas
```

の方が有利になる場合が多い。

---

# 14. pywebviewはWebだから遅いのか

pywebviewではHTML / CSS / JavaScriptを使用するため、

```text
Web
=
重そう
```

という印象を持ちやすい。

しかし現代のWeb描画エンジンは非常に高速である。

Canvasを使用したグラフ描画は、

- アニメーション
- ゲーム
- データ可視化
- リアルタイムチャート

などでも広く使用されている。

2,000点程度の折れ線グラフを描くこと自体は、大きな負荷ではない。

したがって、

> pywebviewを使っているから遅い

と考えるのではなく、

> pywebview内でどのような描画方法を使っているか

を見る必要がある。

---

# 15. PyQtGraph

Python側だけで高速な波形表示を行いたい場合、PyQtGraphは非常に有力である。

構成：

```text
PLC
 ↓
Python
 ↓
NumPy
 ↓
PyQtGraph
 ↓
画面
```

JavaScriptとのデータ受け渡しが存在しない。

PyQtGraphは、

- 計測アプリ
- オシロスコープ
- センサー表示
- DAQ
- FFT
- 科学技術計算

などで使用される高速描画ライブラリである。

---

# 16. PyQtGraphの長所

PyQtGraphの最大の特徴は、

> Pythonから直接、高速に波形描画できる

ことである。

例えば、

```python
curve.setData(values)
```

のようにデータを直接更新できる。

高速リアルタイム波形を最優先する場合には非常に強力である。

---

# 17. PyQtGraphの短所

一方で、

- PyQt / PySideの知識が必要
- GUI設計方法がHTML/CSSと異なる
- Web UIの自由度をそのまま使えない
- 既存pywebviewアプリの資産を流用しにくい

という点がある。

そのため、2,000点程度の波形を表示するだけなら、

> 最初からPyQtGraphへ移行する必要はない

と考える。

---

# 18. UI方式の比較

| UI構成 | 波形描画速度 | UI作成 | Python連携 | 主な用途 |
|---|---:|---|---|---|
| Tkinter + matplotlib | △ | ○ | ◎ | 小規模GUI |
| pywebview + matplotlib/Base64 | △ | ◎ | ◎ | 静的グラフ |
| pywebview + Chart.js | ◎ | ◎ | ○〜◎ | 業務アプリ |
| pywebview + uPlot | ◎〜非常に◎ | ◎ | ○〜◎ | PLC・センサー波形 |
| PyQt + PyQtGraph | 非常に◎ | △〜○ | ◎ | 高速計測アプリ |

---

# 19. 今後の標準方針

pywebviewを使用するアプリでは、グラフの用途によって描画方法を使い分ける。

## 静的な分析グラフ

次の用途ではmatplotlibを使用してよい。

- レポート
- ダッシュボード
- 画像保存
- 印刷
- 更新頻度が低いグラフ
- 複雑なPython側解析結果

```text
Python
 ↓
matplotlib
 ↓
PNG / Base64
 ↓
表示
```

---

## 高速更新する波形

PLCやセンサーのリアルタイム・準リアルタイム波形ではJavaScript描画を使用する。

```text
Python
 ↓
数値配列
 ↓
JavaScript
 ↓
uPlot / Chart.js
 ↓
Canvas
```

---

# 20. PLC受信から画面表示までの推奨構成

PLC監視をメインスレッドで行い、要求があったPLCのみThreadPoolExecutorで処理する構成を考える。

```text
メインスレッド
    │
    ├─ PLC1要求監視
    ├─ PLC2要求監視
    ├─ PLC3要求監視
    │
    └─ ...
            │
            │ 要求ON
            ▼
ThreadPoolExecutor
            │
            ▼
PLCから2,000点受信
            │
            ├────────→ UI表示
            │              ↓
            │           JavaScript
            │              ↓
            │            uPlot
            │
            └────────→ SQLite登録
                           ↓
                          Lock
```

この構成では、

- PLC通信は並行処理
- グラフ表示はJavaScript
- SQLite書込みはLockで排他制御

と役割を分ける。

---

# 21. SQLite登録を待ってから表示する必要はない

「最短で画面表示」が最優先であれば、

```text
PLC受信
 ↓
SQLite保存
 ↓
表示
```

とする必要はない。

代わりに、

```text
PLC受信完了
      │
      ├────────→ UI更新
      │
      └────────→ SQLite登録
```

と分岐させる。

つまり、

> SQLiteへのCOMMIT完了を待たずに波形表示を開始する

という設計が可能である。

もちろんSQLite登録失敗時のエラー処理は別途必要になる。

---

# 22. ThreadPoolExecutorとの組み合わせ

PLC通信はI/O待ちが多いためThreadPoolExecutorと相性がよい。

例えば、

```text
Thread A
PLC3からデータ受信中

Thread B
PLC7からデータ受信中
```

のように複数設備からの受信を並行して行える。

受信完了後、それぞれのスレッドからUI更新処理やSQLite登録処理へ進む。

ただしGUI更新にはUIスレッドの制約がある場合があるため、使用するpywebviewのAPIやイベント設計に従って安全にJavaScript側へデータを渡す必要がある。

---

# 23. SQLiteへの書き込み

複数PLCから同時に受信完了した場合、複数スレッドがSQLiteへINSERTしようとする可能性がある。

そのため書き込み部分のみLockを使用する。

考え方：

```python
data = read_from_plc()

with db_lock:
    save_to_database(data)
```

重要なのは、

```python
with db_lock:
    data = read_from_plc()
    save_to_database(data)
```

としないことである。

PLC通信中までLockしてしまうと、他のスレッドがSQLiteを使用できない時間が不必要に長くなる。

Lock対象はできるだけ小さくする。

---

# 24. PLC通信までLockしない

推奨：

```text
PLC通信
 ↓
自由に並行実行

SQLite書込み
 ↓
Lock
 ↓
1件ずつ
```

非推奨：

```text
Lock取得
 ↓
PLC通信待ち
 ↓
SQLite書込み
 ↓
Lock解放
```

PLC通信はネットワーク待ちが発生するため、その間DB Lockを保持する意味はない。

---

# 25. Queue方式との比較

SQLite登録方式としてQueueを使用する方法もある。

```text
PLC受信スレッド
 ↓
Queue
 ↓
DB専用スレッド
 ↓
SQLite
```

Queue方式は、

- 登録件数が非常に多い
- SQLite登録に時間がかかる
- PLC処理をDB待ちさせたくない

場合に有効である。

しかし、

```text
PLC約10台
要求発生時のみデータ受信
```

という程度であれば、Lock方式の方がシンプルで扱いやすい場合が多い。

---

# 26. 最適化で重要なのは「実測」

高速化では感覚だけで判断しない。

`time.perf_counter()`などを使い、各処理時間を測定する。

例えば、

```text
PLC受信            120 ms
データ変換           2 ms
SQLite INSERT        6 ms
Python→JS転送        3 ms
グラフ描画           4 ms
```

と測定できれば、

> 実際のボトルネックはPLC通信である

と判断できる。

逆に、

```text
PLC受信             40 ms
matplotlib描画      90 ms
Base64変換          15 ms
```

なら、グラフ方式を改善する効果が大きい。

---

# 27. time.perf_counter()による計測例

```python
from time import perf_counter


start = perf_counter()

data = read_from_plc()

received = perf_counter()

save_to_database(data)

saved = perf_counter()

print(
    f"PLC受信: "
    f"{(received - start) * 1000:.1f} ms"
)

print(
    f"DB保存: "
    f"{(saved - received) * 1000:.1f} ms"
)
```

可能であればJavaScript側でも描画時間を測定する。

これにより、

```text
PLC
Python
SQLite
JavaScript
描画
```

のどこに時間が掛かっているのか分かる。

---

# 28. 「Webだから遅い」ではなく処理経路を見る

性能を考えるとき、

```text
Tkinterだから速い
pywebviewだから遅い
```

という単純な比較は避ける。

重要なのは、

> データが画面に表示されるまでに何回変換されるか

である。

例えば、

```text
pywebview + uPlot

数値
 ↓
Canvas
```

は非常にシンプルである。

一方、

```text
Tkinter + matplotlib

数値
 ↓
matplotlib
 ↓
Canvas
```

ではmatplotlibによる描画処理が入る。

GUIフレームワークの名前だけでは性能は判断できない。

---

# 29. データの直接利用

PLCから受信した2,000点を一度SQLiteへ保存し、

```text
SQLite
 ↓
SELECT
 ↓
グラフ
```

と読み直す必要はない。

表示用には受信したデータをそのまま利用する。

推奨：

```text
PLC
 ↓
data
 ├────────→ JavaScript
 │
 └────────→ SQLite
```

非推奨：

```text
PLC
 ↓
SQLite
 ↓
SELECT
 ↓
JavaScript
```

後者は不要なDBアクセスを増やす。

---

# 30. 推奨アーキテクチャ

今後のpywebviewによるPLC波形アプリでは、基本的に次の構成を標準とする。

```text
┌───────────────────────────────┐
│ メインスレッド                │
│                               │
│ PLC要求監視                   │
└──────────────┬────────────────┘
               │
               │ 要求ON
               ▼
┌───────────────────────────────┐
│ ThreadPoolExecutor            │
│                               │
│ PLCデータ受信                 │
└──────────────┬────────────────┘
               │
               ▼
         2,000点データ
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
┌─────────────┐  ┌─────────────┐
│ UI表示      │  │ SQLite保存  │
│             │  │             │
│ JavaScript  │  │ Lock        │
│ uPlot       │  │ INSERT      │
└─────────────┘  └─────────────┘
```

---

# 31. UI描画の標準

今後の標準：

```text
静的グラフ
    ↓
matplotlib

高速波形
    ↓
JavaScript

一般グラフ
    ↓
Chart.js

PLC / センサー波形
    ↓
uPlot

極端に高速な計測UI
    ↓
PyQtGraph
```

---

# 32. pywebviewを継続するメリット

pywebviewを使用し続ける最大のメリットは、

```text
Python
+
HTML
+
CSS
+
JavaScript
```

を役割ごとに使い分けられることである。

Python：

- PLC通信
- SQLite
- ファイル処理
- データ加工
- 業務ロジック

JavaScript：

- UI操作
- グラフ描画
- DOM更新

HTML / CSS：

- 画面構造
- デザイン
- レイアウト

という分担にできる。

---

# 33. HTML/CSSによるUI自由度

例えば、

```text
┌──────────────────────────────────────┐
│ MC003 モータ電流                    │
│                                      │
│         ／＼          ／＼          │
│ _______/    \________/    \_____    │
│                                      │
├────────────────┬─────────────────────┤
│ 最大値 12.4 A │ 平均値 6.8 A        │
├────────────────┴─────────────────────┤
│ 判定：OK                             │
└──────────────────────────────────────┘
```

のようなUIもHTML/CSSなら比較的容易に作成できる。

Tkinterで同等の画面を作るよりも、レイアウトや装飾の自由度が高い。

---

# 34. PyQtGraphへ移行する判断基準

次のような状況になった場合はPyQtGraphを検討する。

- 数万〜数十万点以上を頻繁に更新する
- 1秒間に何十回も波形を更新する
- オシロスコープに近い表示が必要
- JavaScriptへの転送がボトルネックになった
- グラフ描画時間を極限まで短くしたい
- UIより計測性能を最優先する

ただし、必ず実測してから判断する。

2,000点程度であれば、pywebview + JavaScriptで十分な可能性が非常に高い。

---

# 35. 最終的な標準方針

今後のpywebviewアプリでは次のルールを基本とする。

## ルール1

頻繁に更新するグラフでは、matplotlib → Base64方式を原則使用しない。

---

## ルール2

PLCやセンサーの波形データは、PythonからJavaScriptへ数値データとして直接渡す。

---

## ルール3

JavaScript側ではグラフオブジェクトを毎回作り直さず、既存グラフのデータだけ更新する。

---

## ルール4

一般グラフはChart.js、波形・時系列表示はuPlotを第一候補とする。

---

## ルール5

SQLite保存用データと画面表示用データは、PLC受信後に分岐させる。

```text
PLC
 ↓
data
 ├→ UI
 └→ SQLite
```

---

## ルール6

最短表示を求める場合、SQLiteへのCOMMIT完了を待ってから画面更新する必要はない。

---

## ルール7

SQLiteへの書込み競合がある場合は、書込み部分だけLockする。

---

## ルール8

PLC通信部分までLockしない。

---

## ルール9

性能問題が発生した場合は、まず`time.perf_counter()`などで処理時間を測定する。

---

## ルール10

2,000点程度の波形表示だけを理由にpywebviewを捨てたりPyQtへ移行したりしない。

---

# 36. まとめ

PLCから約2,000点のデータを受信し、できるだけ早くPC画面へ表示したい場合、重要なのは単純な描画速度だけではない。

処理全体を、

```text
PLC通信
 ↓
Python
 ↓
UI転送
 ↓
グラフ描画
```

という一連の流れとして考える必要がある。

matplotlibは分析・帳票・静的グラフには非常に優秀である。

しかし高速更新では、

```text
matplotlib
 ↓
PNG
 ↓
Base64
 ↓
画像表示
```

という処理は遠回りになる。

pywebviewでは、

```text
Python
 ↓
数値配列
 ↓
JavaScript
 ↓
uPlot / Chart.js
```

という構成にすることで、非常にシンプルかつ高速な波形表示が実現できる。

約2,000点程度であれば、pywebview + JavaScriptは十分実用的であり、今後の標準方式として採用できる。

最終的な基本方針は次のとおりとする。

```text
静的分析
    matplotlib

リアルタイム・高速波形
    pywebview + JavaScript

一般グラフ
    Chart.js

PLC・センサー波形
    uPlot

極端なリアルタイム計測
    PyQtGraph
```

そして性能に疑問が生じた場合は、推測ではなく、

```text
PLC受信時間
Python処理時間
DB保存時間
Python→JavaScript転送時間
JavaScript描画時間
```

を個別に計測し、実際のボトルネックを確認してから最適化する。

この考え方を、今後のpywebviewアプリにおけるグラフ描画の標準方針とする。
