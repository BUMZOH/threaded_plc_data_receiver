# Measurement Data Viewer データ解析機能 仕様書

## 1. 目的

既存の Measurement Data Viewer に、現在表示している測定波形を対象としたデータ解析機能を追加する。

解析処理は Python 側で実行し、解析ロジックは `data_analysis.py` に分離する。

ユーザーは画面上のドロップダウンから解析関数を選択し、`解析` ボタンを押すことで、現在表示中の波形から最大5個の特徴量を取得できる。

解析結果はグラフ下部に 2行×5列 の表形式で表示する。

---

## 2. 基本方針

今回の改造では、既存の波形表示機能をできるだけ変更せず、解析機能を独立して追加する。

役割分担は次のようにする。

- `app.py`
  - pywebview API
  - JavaScript と Python の橋渡し
  - 解析関数一覧の取得
  - 解析実行API

- `data_analysis.py`
  - 実際の解析処理
  - 解析関数の管理
  - 特徴量の生成

- `script.js`
  - 解析関数ドロップダウンの初期化
  - 解析ボタン押下処理
  - 現在表示中の波形データを Python へ送信
  - 解析結果の表表示

- `index.html`
  - 解析関数選択UI
  - 解析ボタン
  - 特徴量表示テーブル

- `style.css`
  - 解析UIおよび表の見た目調整

---

## 3. 画面仕様

グラフの下に解析用UIを追加する。

例：

```text
解析関数 [ servo_peak_search ▼ ] [解析]

┌───────────────┬───────────────┬──────────┬──────────┬──────────┐
│ peak_position │ peak_value    │    -     │    -     │    -     │
├───────────────┼───────────────┼──────────┼──────────┼──────────┤
│ 255           │ 3556          │    -     │    -     │    -     │
└───────────────┴───────────────┴──────────┴──────────┴──────────┘
```

### 3.1 解析関数選択

ドロップダウンで解析関数を選択する。

例：

- `servo_peak_search`
- `motor_rms`
- `vibration_features`

解析関数一覧は JavaScript に直接固定記述せず、Python 側から取得する。

---

## 4. 解析実行方法

解析は自動実行ではなく、ユーザーが `解析` ボタンを押したときに実行する。

処理の流れは次の通り。

```text
現在表示中の波形
      ↓
JavaScript
      ↓
pywebview API
      ↓
Python
      ↓
data_analysis.py
      ↓
選択された解析関数
      ↓
特徴量
      ↓
JavaScript
      ↓
2行×5列の表へ表示
```

---

## 5. 解析対象データ

解析対象は、現在画面に表示している1件の波形とする。

JavaScript 側では現在のレコードを次のように取得できる。

```javascript
const record = records[currentIndex];
```

波形データは次の値を使用する。

```javascript
record.values
```

初期仕様では、現在表示中の `record.values` を pywebview 経由で Python に渡して解析する。

---

## 6. `data_analysis.py`

解析処理は `data_analysis.py` にまとめる。

例：

```text
project/
│
├─ app.py
├─ data_analysis.py
├─ index.html
├─ script.js
└─ style.css
```

### 6.1 解析関数の基本形

各解析関数は、波形データを受け取り、特徴量を返す。

例：

```python
def servo_peak_search(values):
    peak_value = max(values)
    peak_position = values.index(peak_value)

    return [
        {
            "name": "peak_position",
            "value": peak_position,
        },
        {
            "name": "peak_value",
            "value": peak_value,
        },
    ]
```

---

## 7. 特徴量の戻り値仕様

特徴量は番号付きキーではなく、リスト形式で返す。

### 採用する形式

```python
[
    {
        "name": "peak_position",
        "value": 255,
    },
    {
        "name": "peak_value",
        "value": 3556,
    },
]
```

### 採用しない形式

```python
{
    "feature_name1": "peak_position",
    "feature_value1": 255,
    "feature_name2": "peak_value",
    "feature_value2": 3556,
}
```

リスト形式にすることで、特徴量が2個・3個・5個と変化しても、同じ処理で扱える。

---

## 8. 特徴量数

1つの解析関数が返せる特徴量は最大5個とする。

例：

```python
if len(features) > 5:
    ...
```

6個以上返された場合はエラーとして扱う。

---

## 9. 解析結果全体の戻り値

将来の拡張性を考え、pywebview API から JavaScript へ返す結果は次の形式を推奨する。

```python
{
    "function_name": "servo_peak_search",
    "features": [
        {
            "name": "peak_position",
            "value": 255,
        },
        {
            "name": "peak_value",
            "value": 3556,
        },
    ],
}
```

この形式なら、将来的に次のような情報も追加しやすい。

```python
{
    "function_name": "servo_peak_search",
    "features": [...],
    "message": "解析成功",
}
```

---

## 10. 解析関数レジストリ

解析関数の選択には `if` 文を大量に並べず、関数レジストリを使用する。

例：

```python
ANALYSIS_FUNCTIONS = {
    "servo_peak_search": servo_peak_search,
    "motor_rms": motor_rms,
}
```

共通実行関数は次のようにする。

```python
def analyze(function_name, values):
    function = ANALYSIS_FUNCTIONS[function_name]
    return function(values)
```

---

## 11. ドロップダウン一覧の取得

解析関数一覧は `ANALYSIS_FUNCTIONS` のキーから取得する。

例：

```python
ANALYSIS_FUNCTIONS.keys()
```

JavaScript 側で解析関数名を固定記述しない。

これにより、新しい解析関数を追加した場合でも、Python 側の登録だけで画面へ反映しやすくなる。

---

## 12. 特徴量表示テーブル

表は常に 2行×5列 とする。

- 1行目：特徴名
- 2行目：特徴量

特徴量が5個未満の場合、未使用セルには `-` を表示する。

例：

```text
peak_position | peak_value | - | - | -
255           | 3556       | - | - | -
```

5個の場合：

```text
feature1 | feature2 | feature3 | feature4 | feature5
value1   | value2   | value3   | value4   | value5
```

表のサイズを固定することで、解析関数ごとに画面レイアウトが変化しないようにする。

---

## 13. 解析結果の更新タイミング

初期仕様では自動解析を行わない。

ユーザー操作：

```text
解析関数を選択
      ↓
解析ボタンを押す
      ↓
現在表示中の波形を解析
      ↓
結果表示
```

理由：

将来的に次のような重い解析を追加する可能性があるため。

- FFT
- フィルタ処理
- ピーク探索
- 統計特徴量
- Isolation Forest
- AutoEncoder

波形を切り替えるたびに自動解析すると、操作性が悪化する可能性がある。

---

## 14. 将来の自動解析

将来的には次のような機能追加を検討できる。

```text
☑ 自動解析
```

自動解析ONの場合：

```text
前後ボタンまたは直接ジャンプ
      ↓
波形変更
      ↓
選択中の解析関数を自動実行
      ↓
特徴量更新
```

初期実装には含めない。

---

## 15. 解析結果のDB保存

初期仕様では解析結果を SQLite へ保存しない。

解析結果は画面表示のみとする。

理由：

- 解析アルゴリズムは今後変更する可能性が高い
- 特徴量の種類も増減する可能性がある
- DB設計を解析仕様へ固定しすぎないため
- まずは解析ロジックの検証を優先するため

必要になった段階で、解析結果保存用テーブルを別途設計する。

---

## 16. 将来的なデータ受け渡し方法

初期仕様：

```text
JavaScript
    ↓
record.values
    ↓
Python
    ↓
data_analysis.py
```

将来的に波形データが大きくなった場合や解析負荷が増えた場合は、次の方式も検討する。

```text
JavaScript
    ↓
record id + 解析関数名
    ↓
Python
    ↓
SQLiteから対象波形を取得
    ↓
data_analysis.py
```

この方式では大きな波形データを JavaScript → Python へ再送する必要がなくなる。

ただし初期実装では複雑化を避け、`record.values` を直接渡す方式とする。

---

## 17. エラー処理

最低限、次のエラーを考慮する。

### 解析対象データがない

`records.length === 0` の場合は解析しない。

### 解析関数が選択されていない

解析を実行せず、メッセージを表示する。

### 存在しない解析関数名

Python 側でエラーとして扱う。

### 特徴量が6個以上

最大5個という仕様に反するためエラーとする。

### 解析関数内部で例外発生

pywebview API 側で例外を受け取り、JavaScript 側へエラー内容を返せる構成にする。

---

## 18. 初期実装の完成条件

今回の初期実装では、次の仕様を完成条件とする。

- `data_analysis.py` を新規作成
- 解析関数を別モジュールへ分離
- 解析関数レジストリ `ANALYSIS_FUNCTIONS` を使用
- ドロップダウンで解析関数を選択
- `解析` ボタンで明示的に実行
- 現在表示中の波形を解析
- Python 側で解析
- 1関数あたり最大5個の特徴量
- 特徴量は `name` / `value` のリスト形式
- 解析結果は 2行×5列 の表へ表示
- 未使用セルは `-`
- 解析結果はDBへ保存しない
- 自動解析機能は初期実装には含めない

---

## 19. 今後の拡張候補

将来的には次の機能を追加できる。

- 自動解析ON/OFF
- FFT
- RMS
- 最大値・最小値
- 平均
- 標準偏差
- ピーク位置
- ピーク値
- 波形立ち上がり時間
- 積分値
- Isolation Forest 用特徴量抽出
- AutoEncoder 用前処理
- 解析結果のCSV出力
- 解析結果のSQLite保存
- 解析結果の時系列表示
- 特徴量による検索・絞り込み

---

## 20. 設計上の考え方

今回の改造では、Measurement Data Viewer を単なる「波形表示ツール」から、

```text
波形を見る
    ↓
波形を解析する
    ↓
特徴量を確認する
```

という「波形解析ビューア」へ発展させる。

特に重要なのは、解析ロジックを `data_analysis.py` へ分離することである。

これにより、

```text
UI
↓
pywebview API
↓
解析ロジック
```

の責務が分離される。

今後、設備異常検知や機械学習向けの特徴量抽出を追加する場合でも、既存の表示処理を大きく変更せずに機能拡張できる構成とする。
