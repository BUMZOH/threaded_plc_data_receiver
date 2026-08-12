# PLCデータ受信からChart.jsグラフ描画までの処理時間測定

## 1. 目的

モータ電流値受信アプリについて、PLCからデータを受信してからChart.jsでグラフを描画するまでに、どの程度の時間が必要かを実測した。

本資料は、現段階で得られた測定結果を記録し、今後のアプリ設計・性能評価の基準として残すことを目的とする。

> **注意**\
> 本資料の数値は現段階での簡易測定結果であり、厳密なベンチマーク値ではない。PC負荷、PLC通信状態、WebViewの状態などによって変動する可能性がある。

------------------------------------------------------------------------

## 2. 測定対象アプリの概要

アプリは、おおむね次の流れでモータ電流値を表示する。

``` text
PLC
 │
 │ 32bitデータ × 1000点を受信
 ▼
Python
 │
 │ valuesとして保持
 │ JSONへ変換
 │ pywebview run_js()
 ▼
JavaScript
 │
 │ receiveMotorData()
 ▼
Chart.js
 │
 │ データ設定
 │ update("none")
 ▼
グラフ描画
```

Python側では `kv_com.read_devices_d()`
によりPLCデータを読み込み、受信後すぐに `_push_motor_data()`
を呼び出してJavaScriptへデータをPushする。

JavaScript側では受信した1000点をChart.jsのデータへ設定し、`update("none")`
によってグラフを更新する。

------------------------------------------------------------------------

## 3. 前提条件

### PLC

-   PLC：KEYENCE KV-5000
-   通信：Ethernet経由
-   Pythonから独自通信モジュール `kv_com` を使用

### データ

-   測定対象：モータ電流値
-   データ点数：**1000点**
-   1点：**32bit（2Word）**
-   PLCから読み込むデータ量：1000点 × 32bit
-   Pythonでは `list[int]` として受信

### GUI

-   Python GUI：pywebview
-   Python → JavaScript：`window.run_js()`
-   JavaScriptグラフライブラリ：Chart.js 4.5.1
-   グラフ種類：line chart
-   点描画：`pointRadius: 0`
-   Chart.jsアニメーション：無効 (`animation: false`)
-   更新：`motorCurrentChart.update("none")`

------------------------------------------------------------------------

## 4. PLCからPythonへのデータ受信時間

Pythonの `perf_counter()` を使用し、`kv_com.read_devices_d()`
の実行時間を測定した。

測定値は次のとおり。

    回数           測定時間
  ------ ------------------
       1   0.042 s（42 ms）
       2   0.048 s（48 ms）
       3   0.043 s（43 ms）
       4   0.039 s（39 ms）
       5   0.041 s（41 ms）

平均値は、

**約 42.6 ms**

となった。

したがって、現段階では
**PLCから1000点の32bitデータをPythonへ受信する時間は、おおよそ40～50
ms程度** と考えられる。

### `perf_counter()` の単位に注意

`perf_counter()` の差分は「秒」である。

例えば、

``` text
0.042
```

と表示された場合は0.042 msではなく、

``` text
0.042秒 = 42 ms
```

である。

ミリ秒で表示する場合は次のように1000倍する。

``` python
elapsed_time = (perf_counter() - start_time) * 1000
print(f"データ受信時間: {elapsed_time:.1f} ms")
```

------------------------------------------------------------------------

## 5. PLC受信＋JavaScript Pushまでの時間

次に計測終了位置を `_push_motor_data()` の後へ移動した。

これにより、概ね次の範囲を測定している。

``` text
計測開始
   │
   ├─ PLCから1000点受信
   │
   ├─ Pythonでvalues取得
   │
   ├─ JSON化
   │
   ├─ pywebview window.run_js()
   │
   └─ JavaScriptへPush
   │
計測終了
```

測定値は次のとおり。

    回数           測定時間
  ------ ------------------
       1   0.060 s（60 ms）
       2   0.052 s（52 ms）
       3   0.047 s（47 ms）
       4   0.051 s（51 ms）
       5   0.047 s（47 ms）

平均値は、

**約 51.4 ms**

となった。

PLC受信のみの平均が約42.6 msだったため、単純な差分では、

``` text
51.4 ms - 42.6 ms = 約8.8 ms
```

となる。

したがって、現段階の概算では
**Python側でのJSON化およびpywebview経由のJavaScript
Pushによる追加時間は約9 ms程度** と推定できる。

ただし、これは別々の5回測定の平均値を引いた結果である。PLC通信時間自体にもばらつきがあるため、**「Push処理が正確に8.8
ms」と断定できる値ではなく、おおよその目安**として扱う。

------------------------------------------------------------------------

## 6. Chart.jsによるグラフ描画時間

JavaScript側では `performance.now()` を使用して、`receiveMotorData()`
が開始してからChart.js更新後の `requestAnimationFrame()`
までを測定した。

測定結果は次のとおり。

    回数   描画時間
  ------ ----------
       1    10.8 ms
       2     6.6 ms
       3     5.6 ms
       4     5.8 ms
       5     6.2 ms
       6     3.3 ms

初回は10.8 msで、その後はおおむね3～7 ms程度で推移した。

そのため、現段階では
**Chart.jsのグラフ更新・描画時間は定常状態でおおよそ5～6 ms程度**
と考える。

初回だけ若干長いのは、ブラウザ内部の初回処理、JIT最適化、キャッシュ等の影響が含まれている可能性があるため、性能評価では2回目以降の値を定常値として見るのが妥当である。

------------------------------------------------------------------------

## 7. 現段階での処理時間まとめ

測定結果から、各処理時間は概ね次のように整理できる。

  処理                                      おおよその時間
  -------------------------- -----------------------------
  PLC → Python：1000点受信                     **約43 ms**
  Python → JavaScript Push              **約9 ms（概算）**
  Chart.jsグラフ描画                         **約5～6 ms**
  全体                         **約57～60 ms程度（概算）**

処理のイメージは次のとおり。

``` text
PLC
 │
 │ 1000点（32bit）受信
 │ 約43 ms
 ▼
Python
 │
 │ JSON化 + pywebview + run_js()
 │ 約9 ms（概算）
 ▼
JavaScript
 │
 │ Chart.js更新・描画
 │ 約5～6 ms
 ▼
画面表示

合計：約57～60 ms程度
```

したがって、**PLCから1000点のデータを読み始めてからグラフ表示まで、おおよそ60
ms前後**というのが現段階での目安となる。

------------------------------------------------------------------------

## 8. 結果から分かること

### 8.1 PLC通信が最も大きな割合を占める

全体約60 msのうち、PLCからPythonへのデータ受信が約43
msであり、現状ではPLC通信部分が最も大きな時間を占めている。

### 8.2 pywebviewによるJavaScript Pushは十分高速

1000点の整数データをJSON化して `window.run_js()`
でJavaScriptへ渡しても、今回の測定では追加時間は概算約9 msだった。

1000点程度のデータ表示用途では、pywebviewによるPython →
JavaScript間のデータ受け渡しは十分実用的な速度と考えられる。

### 8.3 Chart.jsの描画は非常に高速

1000点の折れ線グラフについて、定常時の描画時間は約5～6 msだった。

今回の設定では、

``` javascript
animation: false
```

``` javascript
pointRadius: 0
```

``` javascript
motorCurrentChart.update("none");
```

としており、高速なリアルタイム更新に適した設定になっている。

現段階では、**Chart.jsの描画処理がアプリ全体のボトルネックになる可能性は低い**と考えられる。

------------------------------------------------------------------------

## 9. 今後さらに正確に測定する場合

今回のJavaScript
Push時間は、PLC受信のみの平均値と、PLC受信＋Pushの平均値との差から求めた概算値である。

より正確に測定する場合は、1回の受信処理の中で区間ごとに `perf_counter()`
を取得する。

``` python
start_time = perf_counter()

values = kv_com.read_devices_d(
    self.plc_ip_address,
    config.data_start_device,
    DATA_POINT_COUNT,
)

receive_time = perf_counter()

self._push_motor_data(config, values)

push_time = perf_counter()

print(
    f"PLC受信: {(receive_time - start_time) * 1000:.1f} ms, "
    f"JS Push: {(push_time - receive_time) * 1000:.1f} ms, "
    f"合計: {(push_time - start_time) * 1000:.1f} ms"
)
```

この方法なら同一の受信処理について、

``` text
PLC受信
↓
JavaScript Push
```

を個別に測定できるため、通信時間のばらつきによる影響を小さくできる。

------------------------------------------------------------------------

## 10. 現時点での結論

今回の実測では、1000点・32bitのモータ電流データについて、

-   PLC → Python：約43 ms
-   Python → JavaScript：約9 ms（概算）
-   Chart.js描画：約5～6 ms
-   PLC受信開始 → グラフ表示：約60 ms前後（概算）

という結果になった。

特にChart.jsの描画時間は非常に短く、1000点程度の波形表示であれば十分高速である。

また、pywebviewを介したPython →
JavaScriptへのデータ転送についても、現段階では大きなボトルネックにはなっていない。

この結果から、**Python + pywebview +
Chart.jsという構成は、PLCから取得した1000点程度の波形データを高速に表示する用途に十分実用的**と判断できる。

今後データ点数を2000点、5000点などへ増やす場合は、本資料の測定値を基準として再度同じ方法で計測すると、データ点数増加に対する性能変化を比較しやすい。
