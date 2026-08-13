# SQLite保存データ閲覧機能 仕様書

## 1. 目的

設備データ受信アプリに、SQLiteへ保存した過去の計測データを閲覧する機能を追加する。

現在のリアルタイムグラフ表示機能をできるだけそのまま利用し、新しい画面や複雑な管理機能は追加しない。

本機能では、PLC監視を停止しているときに、現在の「グラフ表示」ドロップダウンリストで選択した測定対象について、SQLiteに保存されているデータを古い順・新しい順に移動しながらグラフ表示できるようにする。

---

## 2. 基本方針

今回の改造では、次の方針を優先する。

1. 現在の画面構成を大きく変更しない
2. 現在のChart.jsによるグラフ描画機能を再利用する
3. SQLite閲覧専用の別画面は作らない
4. Python側のSQLite処理は必要最小限にする
5. JavaScript側も既存のグラフ更新処理をできるだけ共通利用する
6. PLC監視中とSQLite閲覧を同時に行わない
7. SQLiteの `id` をレコード位置の基準として利用する

---

## 3. 現在のSQLite構成

SQLiteデータベースファイルは次のファイルを使用する。

```text
data/measurement_data.db
```

対象テーブルは、

```text
measurement_data
```

である。

現在のテーブル構成は次のとおり。

```sql
CREATE TABLE IF NOT EXISTS measurement_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_name TEXT NOT NULL,
    measured_at TEXT NOT NULL,
    data BLOB NOT NULL
)
```

各カラムの意味は次のとおり。

| カラム | 内容 |
|---|---|
| `id` | レコードを一意に識別する連番 |
| `data_name` | 測定対象名。`DataConfig.name` と対応 |
| `measured_at` | データ取得日時 |
| `data` | 32ビット符号付き整数配列を格納したBLOB |

また、現在は次のインデックスが作成されている。

```sql
CREATE INDEX IF NOT EXISTS idx_measurement_data_name_time
ON measurement_data (data_name, measured_at)
```

---

## 4. 画面仕様

現在のグラフの下に、SQLiteデータ閲覧用の操作部を追加する。

概念的な配置は次のようにする。

```text
┌──────────────────────────────────────────────┐
│                                              │
│                現在のグラフ                  │
│                                              │
└──────────────────────────────────────────────┘

取得日時: 2026-08-13 09:15:30

          |<      <      >      >|
```

画面全体を大きく変更せず、グラフ直下へ追加する。

---

## 5. データ取得日時表示

SQLiteから過去データを表示した場合、そのレコードの、

```text
measured_at
```

を画面へ表示する。

表示例：

```text
取得日時: 2026-08-13 09:15:30
```

SQLiteデータをまだ表示していない場合は、例えば、

```text
取得日時: -
```

とする。

リアルタイム受信データについては、今回の改造ではSQLite閲覧用の取得日時表示を更新する必要はない。

---

## 6. 閲覧ボタン

グラフの下に次の4ボタンを配置する。

```text
|<    <    >    >|
```

それぞれの機能は次のとおり。

| ボタン | 機能 |
|---|---|
| `|<` | 選択中の測定対象で一番古いデータを表示 |
| `<` | 現在表示しているデータの1つ前を表示 |
| `>` | 現在表示しているデータの1つ後を表示 |
| `>|` | 選択中の測定対象で一番新しいデータを表示 |

---

## 7. 「一番古いデータ」の動作

`|<` ボタンを押した場合、現在選択されている `data_name` の中から最も古いレコードを取得する。

基本的には `id` の昇順で先頭のレコードを取得する。

概念的には次のSQLになる。

```sql
SELECT id, data_name, measured_at, data
FROM measurement_data
WHERE data_name = ?
ORDER BY id ASC
LIMIT 1
```

取得したBLOBを32ビット符号付き整数配列へ戻し、既存グラフへ表示する。

---

## 8. 「一番新しいデータ」の動作

`>|` ボタンを押した場合、現在選択されている `data_name` の中から最も新しいレコードを取得する。

基本的には `id` の降順で先頭のレコードを取得する。

概念的には次のSQLになる。

```sql
SELECT id, data_name, measured_at, data
FROM measurement_data
WHERE data_name = ?
ORDER BY id DESC
LIMIT 1
```

---

## 9. 「1つ前のデータ」の動作

`<` ボタンを押した場合、現在表示しているSQLiteレコードの `id` より小さいレコードの中から、同じ `data_name` の直前レコードを取得する。

概念的には次のSQLになる。

```sql
SELECT id, data_name, measured_at, data
FROM measurement_data
WHERE data_name = ?
  AND id < ?
ORDER BY id DESC
LIMIT 1
```

これにより、現在表示しているデータから1件ずつ過去方向へ移動できる。

---

## 10. 「1つ後のデータ」の動作

`>` ボタンを押した場合、現在表示しているSQLiteレコードの `id` より大きいレコードの中から、同じ `data_name` の直後レコードを取得する。

概念的には次のSQLになる。

```sql
SELECT id, data_name, measured_at, data
FROM measurement_data
WHERE data_name = ?
  AND id > ?
ORDER BY id ASC
LIMIT 1
```

これにより、現在表示しているデータから1件ずつ新しい方向へ移動できる。

---

## 11. `id` を移動基準にする理由

`measurement_data` には、

```text
id INTEGER PRIMARY KEY AUTOINCREMENT
```

が存在する。

そのため今回の閲覧機能では、レコードの移動位置を管理するために `id` を利用する。

JavaScript側では、現在表示しているSQLiteレコードの `id` を保持する。

例えば概念的には、

```javascript
let currentRecordId = null;
```

のような状態を持つ。

SQLiteからデータを取得したときに、

```text
id
data_name
measured_at
values
```

をPythonからJavaScriptへ返し、その `id` を次回の `<` / `>` 操作に利用する。

---

## 12. 表示対象

SQLite閲覧対象は、現在の「グラフ表示」ドロップダウンリストに従う。

現在のドロップダウンリストには、

```text
すべて
ToolB_Cross_Torque
SpindleInverter_MotorCurrent
motor3
...
```

のように測定対象が表示される。

SQLite閲覧時には、具体的な `data_name` が必要になる。

そのため、SQLite閲覧ボタンを使用する場合は、

```text
すべて
```

ではなく、個別の測定対象を選択していることを前提とする。

`すべて` が選択されている場合はSQLite閲覧を実行しない。

これにより、

> 「前のデータ」がどの測定対象の前なのか

という曖昧さを避ける。

---

## 13. ドロップダウンリスト変更時

SQLiteデータ閲覧中に「グラフ表示」の測定対象を変更した場合、現在保持しているSQLiteレコード位置は無効とする。

つまり、

```text
currentRecordId = null
```

相当の状態へ戻す。

その後、

```text
|<
```

または、

```text
>|
```

を押すことで、新しく選択した測定対象の最古または最新データを表示できる。

この仕様により、異なる `data_name` 間で誤って前後移動することを防ぐ。

---

## 14. PLC監視中の動作

PLC監視中はSQLite閲覧機能を使用できないようにする。

つまり、状態が、

```text
監視中
```

の場合、

```text
|<
<
>
>|
```

の4ボタンを無効化する。

理由は、PLCからリアルタイムデータがPushされてグラフを書き換えている最中に、SQLiteから過去データを表示すると、

```text
リアルタイム表示
```

と、

```text
過去データ表示
```

が競合するためである。

今回の仕様では、この競合を複雑な制御で解決するのではなく、

> **PLC監視中はSQLite閲覧を禁止する**

という単純なルールで回避する。

---

## 15. PLC監視停止時の動作

PLC監視を停止すると、

```text
|<
<
>
>|
```

の4ボタンを使用可能にする。

ただし、

```text
グラフ表示 = すべて
```

の場合は、SQLite閲覧対象を一意に決定できないため閲覧しない。

個別の測定対象を選択した状態で操作する。

---

## 16. 既存グラフ描画機能の再利用

現在のJavaScriptでは、PLCからPushされたデータを、

```javascript
window.receiveData = function (payload) {
    ...
}
```

で受け取り、Chart.jsへ設定している。

現在のグラフ描画では主に、

```javascript
dataChart.data.labels = ...
dataChart.data.datasets[0].data = values;
dataChart.data.datasets[0].label = ...
dataChart.update("none");
```

を使用している。

今回のSQLite閲覧機能でも、別のChartを作成しない。

SQLiteから取得したBLOBをPython側で整数配列へ戻し、

```text
values
```

としてJavaScriptへ渡す。

その後、現在のChart.jsグラフへ同じ方法で表示する。

---

## 17. グラフ描画処理の共通化

極力シンプルにするため、PLCリアルタイム表示とSQLite過去データ表示でグラフ描画コードを重複させない。

現在 `window.receiveData()` の中にある実際のグラフ更新処理を、必要に応じて共通関数へ分離する。

概念例：

```javascript
function updateChart(dataName, values) {
    // X軸作成
    // datasets更新
    // 表示データ名更新
    // Chart.js update
}
```

PLCからPushされた場合：

```text
PLC
 ↓
window.receiveData()
 ↓
updateChart()
```

SQLiteを閲覧した場合：

```text
SQLite
 ↓
pywebview API
 ↓
JavaScript
 ↓
updateChart()
```

とする。

これにより、リアルタイム表示と過去データ表示で同じグラフ描画機能を利用できる。

---

## 18. SQLite BLOBの復元

現在、SQLite保存時には整数配列を次の形式でBLOB化している。

```python
struct.pack(
    f"<{len(values)}i",
    *values,
)
```

つまり、

```text
<
```

はリトルエンディアン、

```text
i
```

は32ビット符号付き整数を表す。

閲覧時は、この逆変換を行う。

概念的には、

```python
struct.unpack(...)
```

を使用してBLOBから整数配列へ戻す。

データ点数はBLOBサイズから求めることができる。

32ビット整数は1点4バイトなので、

```text
点数 = BLOBサイズ ÷ 4
```

となる。

これにより、SQLiteへ保存したデータをChart.jsが扱える整数配列へ戻す。

---

## 19. Python側API

`AppApi` にSQLite閲覧用APIを追加する。

複雑なAPI構成にはせず、必要最小限とする。

考えられる構成は、

```python
get_oldest_data(data_name)
get_previous_data(data_name, current_id)
get_next_data(data_name, current_id)
get_latest_data(data_name)
```

の4つである。

ただし実装時には、コード量を減らすため、

```python
get_saved_data(data_name, current_id, direction)
```

のように1つへまとめる方法も検討する。

最終的には、

> **読みやすさとシンプルさを優先する**

こととし、過度な抽象化は行わない。

---

## 20. PythonからJavaScriptへ返すデータ

SQLiteから正常にレコードを取得した場合、概念的に次のデータを返す。

```python
{
    "id": 123,
    "data_name": "ToolB_Cross_Torque",
    "measured_at": "2026-08-13 09:15:30",
    "values": [...]
}
```

JavaScript側では、

- `id` → 現在位置として保持
- `data_name` → 表示データ名
- `measured_at` → 取得日時表示
- `values` → Chart.jsへ表示

に使用する。

---

## 21. データが存在しない場合

対象のデータが存在しない場合は、例外扱いにはしない。

例えば、

- 選択した測定対象のSQLiteデータが1件もない
- 最古データを表示中にさらに `<` を押した
- 最新データを表示中にさらに `>` を押した

などである。

この場合はPython側から、

```python
None
```

相当を返し、JavaScript側では現在のグラフをそのまま維持する。

つまり、

> **端まで到達した場合は、それ以上移動しない**

という単純な動作とする。

---

## 22. 最古・最新位置でのボタン動作

最古データ表示中に、

```text
<
```

を押した場合、

```text
何もしない
```

とする。

最新データ表示中に、

```text
>
```

を押した場合も、

```text
何もしない
```

とする。

今回の初期実装では、ボタンごとに「これ以上データがない」ことを判定してdisabledへ切り替えるような複雑な制御は必須としない。

シンプルさを優先する。

---

## 23. SAVE_MODEがCSVの場合

本機能は、

> **SQLite保存データの閲覧機能**

である。

そのため、

```python
SAVE_MODE = "sqlite"
```

の場合を主対象とする。

`SAVE_MODE = "csv"` の場合は、SQLite閲覧機能を使用しない。

実装時には、Python側でSQLiteデータベースの存在確認を行い、データベースが存在しない場合はデータなしとして扱う。

CSVファイルを今回の4ボタンで閲覧する機能は追加しない。

---

## 24. SQLiteの同時アクセス

PLC監視中はSQLite閲覧を禁止するため、通常操作では、

```text
PLC受信スレッドによるSQLite書込み
```

と、

```text
GUIからのSQLite読込み
```

が同時に発生しない。

この仕様により、SQLiteアクセス制御を必要以上に複雑化しない。

現在のSQLite保存処理では書込み時に、

```python
SQLITE_LOCK
```

を使用している。

今回の閲覧機能は監視停止中のみ使用するため、読み込み処理についてはできるだけ単純な構成とする。

---

## 25. 画面状態と閲覧可否

基本的な状態は次のようになる。

| PLC状態 | SQLite閲覧 |
|---|---|
| 監視中 | 不可 |
| 停止中 | 可 |
| 終了処理中 | 不可 |

さらに停止中でも、

```text
グラフ表示 = すべて
```

の場合は閲覧対象が決まらないため、SQLite閲覧は実行しない。

---

## 26. 処理フロー

### 最古データを表示する場合

```text
ユーザー
  │
  │ |< をクリック
  ▼
JavaScript
  │
  ├─ PLC停止中か確認
  ├─ 選択中data_nameを取得
  │
  ▼
pywebview API
  │
  ▼
SQLite
  │
  ├─ data_nameで絞込み
  ├─ id昇順
  └─ 先頭1件取得
  │
  ▼
BLOBを整数配列へ復元
  │
  ▼
PythonからJavaScriptへ返却
  │
  ├─ id
  ├─ data_name
  ├─ measured_at
  └─ values
  │
  ▼
既存Chart.js描画処理
  │
  ▼
グラフ更新
  │
  ▼
取得日時表示更新
```

### 前後移動する場合

```text
現在表示中のrecord id
        │
        ├─ <  → idより小さい直近レコード
        │
        └─ >  → idより大きい直近レコード
```

---

## 27. 変更対象ファイル

今回の改造対象は次の4ファイルとする。

### `index.html`

追加内容：

- グラフ下の取得日時表示
- `|<`
- `<`
- `>`
- `>|`

の4ボタン

---

### `style.css`

追加内容：

- SQLite閲覧操作部の最低限のレイアウト
- 4ボタンの配置

現在のシンプルなデザインを維持する。

---

### `script.js`

追加・変更内容：

- SQLite閲覧ボタンのDOM取得
- 現在表示中SQLiteレコードIDの保持
- SQLite閲覧API呼び出し
- `measured_at` の表示
- PLC監視中の閲覧ボタン無効化
- ドロップダウン変更時の現在レコードIDリセット
- 既存グラフ描画処理の共通化

現在のChart.jsインスタンスはそのまま使用する。

---

### `app.py`

追加・変更内容：

- SQLite保存データ取得処理
- BLOBから32ビット符号付き整数配列への復元
- `AppApi` へのSQLite閲覧API追加
- 必要に応じたデータベース存在確認

既存の保存処理・PLC監視処理はできるだけ変更しない。

---

## 28. 今回実装しない機能

今回の改造では、機能を必要以上に広げない。

次の機能は対象外とする。

- 日付範囲検索
- カレンダーによるデータ選択
- レコード一覧表示
- テーブル形式でのSQLite閲覧
- データ削除
- データ編集
- CSV保存データの過去閲覧
- 複数測定対象の過去データ同時表示
- PLC監視中のSQLite閲覧
- 複雑なページング機能
- SQLite閲覧専用ウィンドウ

必要になった場合に将来機能として検討する。

---

## 29. 完成後の操作イメージ

### リアルタイム監視

```text
監視開始
   ↓
PLCデータ受信
   ↓
現在のグラフへリアルタイム表示
   ↓
SQLiteへ保存
```

この間、SQLite閲覧ボタンは使用不可。

### 過去データ閲覧

```text
監視停止
   ↓
グラフ表示から測定対象を選択
   ↓
>| を押す
   ↓
最新データ表示
   ↓
< を押す
   ↓
1つ前
   ↓
< を押す
   ↓
さらに1つ前
```

必要に応じて、

```text
|<
```

で最古、

```text
>|
```

で最新へ直接移動できる。

---

## 30. まとめ

今回追加するSQLite閲覧機能は、

> **現在のリアルタイムグラフを、そのままSQLite保存データの閲覧にも利用する**

ことを基本方針とする。

新しい表示画面や複雑な検索機能は作らず、

```text
グラフ表示対象選択
        │
        ▼
SQLiteから1レコード取得
        │
        ▼
BLOBを整数配列へ復元
        │
        ▼
現在のChart.jsへ表示
```

という単純な構成にする。

操作は、

```text
|<    <    >    >|
```

の4ボタンだけとし、

- `|<`：一番古いデータ
- `<`：1つ前のデータ
- `>`：1つ後のデータ
- `>|`：一番新しいデータ

を表示する。

また、SQLiteデータ表示時には、

```text
取得日時: measured_at
```

をグラフ下へ表示する。

PLC監視中はSQLite閲覧を禁止し、

> **リアルタイム監視と過去データ閲覧を明確に分離する**

ことで、処理をシンプルに保つ。

今回の改造では、既存の `measurement_data` テーブル、既存の `DataConfig.name`、既存のChart.jsグラフを最大限再利用し、最小限の追加コードでSQLite保存データを確認できる機能を実現する。
