# 設備データ 受信アプリ

Version: 20260814-1

## 概要

KEYENCE PLCから設備データを受信し、PCへ保存・グラフ表示するアプリです。

PLCの受信要求を監視し、要求がONになると対象データを受信します。受信データは判定後、SQLiteまたはCSVへ保存し、pywebview上のChart.jsグラフへリアルタイム表示します。

現バージョンでは判定処理は仮実装で、常にOKを返します。

## 主な機能

-   PLC受信要求の常時監視
-   ThreadPoolExecutorによる複数データ項目の並行受信
-   32bit符号付き整数データの受信
-   PythonからJavaScriptへのリアルタイムPush
-   Chart.jsによる波形表示
-   SQLite / CSVへのデータ保存
-   SQLiteへのOK / NG判定結果保存
-   保存済みデータの履歴表示
-   PLCへのOK / NG判定通知
-   PLCへのデータ受信完了通知
-   PLC IPアドレスやデバイス設定のJSON外部設定

## ファイル構成

``` text
app.py
config.json
index.html
script.js
style.css
data/
    measurement_data.db
    data1/
    data2/
    data3/
common_lib_mw/
    kv_com.py
```

### app.py

アプリ本体です。PLC監視、データ受信、判定、SQLite/CSV保存、pywebviewとの連携を担当します。

### config.json

PLC
IPアドレス、監視周期、データ点数、各測定対象のPLCデバイスなどを設定します。

### index.html / script.js / style.css

pywebviewで表示する画面、Chart.jsによるグラフ描画、画面操作、デザインを担当します。

### measurement_data.db

SQLite形式の測定データベースです。

  カラム        内容
  ------------- -------------------------------
  id            レコードID
  data_name     データ名称
  measured_at   データ取得日時
  judge         判定結果（OK / NG）
  data          32bit整数データを格納したBLOB

## 基本的な処理の流れ

``` text
PLC受信要求を監視
        ↓
要求ON
        ↓
PLCからデータ受信
        ↓
OK / NG判定
        ↓
JavaScriptへPush・グラフ表示
        ↓
SQLiteまたはCSVへ保存
        ↓
PLCへ判定結果を通知
        ↓
PLCへ受信完了を通知
```

## 設定

主な設定は `config.json` で変更します。

-   PLC IPアドレス
-   PLC監視周期
-   1回のデータ受信点数
-   データ名称
-   受信要求デバイス
-   データ開始デバイス
-   OK / NG判定通知デバイス
-   受信完了デバイス
-   CSV出力先

## 現時点の注意事項

-   デフォルトの保存形式はSQLiteです。
-   CSV保存時にはOK / NG判定結果を保存しません。
-   SQLiteでは判定結果を `judge` カラムへ `OK` / `NG` として保存します。
-   現在の `judge_data()` は仮実装で、常にOKを返します。
-   実際の判定ロジックは現場運用・データ確認後に実装予定です。
-   PLC通信には独自モジュール `common_lib_mw/kv_com.py` を使用します。
-   画面のグラフ描画にはChart.jsを使用します。

## 今後について

Version 20260814-1 を一旦の現場運用版とします。

実設備で運用し、操作性、通信安定性、データ保存、判定処理、グラフ表示などを確認したうえで、必要な改善を行います。
