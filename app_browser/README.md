# Measurement Data Viewer v2

SQLiteの `measurement_data` テーブルに保存されたBLOB波形を、
pywebview + Chart.js で1件ずつ表示するアプリです。

## 表示方法

1. `data_name` を選択
2. `judge` を `すべて / OK / NG` から選択
3. 開始日時・終了日時を指定
4. `検索` を押す
5. 検索結果の1件目を表示
6. `<` で前のデータ、`>` で次のデータを表示

現在位置は `3 / 12 件` のように表示します。

## 軸設定

- X最小
- X最大
- Y最小
- Y最大
- `軸を適用`
- `自動`

X軸はサンプル番号、Y軸は32bit符号あり整数のデータ値です。

## 起動

```powershell
pip install pywebview
python app.py
```
