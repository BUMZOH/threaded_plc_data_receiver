# Isolation Forestによる設備異常検知 学習アプリ解説書

## 1. はじめに

このアプリは、設備から取得したサーボトルク関連データを使って、**Isolation Forestによる異常検知モデルを学習・検証・保存するための学習アプリ**です。

今回使用する主な特徴量は次の2つです。

- `peak_value`：波形などから取得したピーク値
- `rms`：RMS（Root Mean Square、二乗平均平方根）

CSVデータには実際の判定結果として `judge` 列があり、今回のデータでは大部分が `OK`、1件だけ `NG` です。

このアプリでは、単に全データを学習させるのではなく、**正常データだけを使ってIsolation Forestを学習**します。そして正常データを時系列で「学習用80%」「検証用20%」に分け、学習時より未来側の正常データを使って誤検出率を確認します。

さらに、Isolation Forest標準の `predict()` に判定を任せるのではなく、`score_samples()` から得られる異常スコアを使って、**正常学習データの下位パーセンタイルから独自の判定しきい値を決める**設計にしています。

最後に、完成したモデルを `joblib` 形式で保存し、判定しきい値や特徴量情報をJSON形式で保存します。

---

## 2. このアプリの目的

このアプリでは、次の処理を一通り実施します。

1. CSVファイルを読み込む
2. 正常データだけを抽出する
3. 正常データを時系列順に並べる
4. 正常データを学習用80%、検証用20%に分割する
5. `peak_value` と `rms` の2特徴量でIsolation Forestを学習する
6. `score_samples()` で異常スコアを計算する
7. 学習正常データの下位0.1%点から独自しきい値を決める
8. 検証正常データに対する誤検出率を確認する
9. 実際のNGデータを未知データとして評価する
10. 複数のしきい値候補を比較する
11. 学習済みモデルを保存する
12. しきい値や特徴量情報をJSONで保存する
13. 保存したモデルと設定を再読込し、NG判定が再現できることを確認する
14. 散布図とスコア分布ヒストグラムを表示する

---

## 3. 全体の処理イメージ

```text
servo_torque.csv
        |
        v
CSV読み込み
        |
        v
judge == "OK" の正常データだけ抽出
        |
        v
measured_at で時系列順に並べる
        |
        +-----------------------------+
        |                             |
        v                             v
過去80%                         未来20%
学習データ                      検証データ
        |                             |
        v                             |
IsolationForest.fit()                 |
        |                             |
        v                             |
score_samples()                       |
        |                             |
        v                             |
学習データの下位0.1%から             |
thresholdを決定                       |
        |                             |
        +--------------+--------------+
                       |
                       v
              検証データを評価
                       |
                       v
                  誤検出率確認

さらに別ルートで

実際のNGデータ
        |
        v
学習には使わず未知データとして評価
        |
        v
score < threshold ?
        |
        +---- Yes ----> 異常候補
```

この構成の重要な点は、**実際のNGデータをモデル学習やしきい値決定に使っていない**ことです。

NGデータは最後まで未知データとして残し、学習後に正しく異常として検出できるか確認します。

---

## 4. 使用ライブラリ

コード冒頭では次のライブラリを読み込んでいます。

```python
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
```

### `pathlib.Path`

ファイルやフォルダのパスを扱います。

```python
BASE_DIRECTORY = Path(__file__).resolve().parent
```

とすることで、Pythonファイル自身が置かれているフォルダを基準にできます。

Windowsの絶対パスを直接書くよりも、アプリを別PCへ移動しやすくなります。

### `json`

判定しきい値や使用特徴量など、モデルに付随する設定情報をJSONファイルへ保存するために使います。

### `joblib`

学習済みのscikit-learnモデルをファイルへ保存・読込するために使用します。

### `numpy`

主に次の2用途で使用しています。

- `np.percentile()`：独自しきい値の算出
- `np.where()`：しきい値を使った正常／異常判定

### `pandas`

CSV読込、データ抽出、時系列並べ替え、DataFrame操作など、データ処理全般を担当します。

### `matplotlib`

結果の散布図とヒストグラム表示に使います。

### `IsolationForest`

今回の異常検知モデル本体です。

---

## 5. フォルダ構成

このアプリは次のような構成を想定しています。

```text
project/
|
+-- app.py
|
+-- data/
|   +-- servo_torque.csv
|
+-- model/
    +-- isolation_forest_model.joblib
    +-- threshold.json
```

`model` フォルダは存在しなくても、プログラム実行時に自動作成されます。

---

## 6. 基本設定

```python
BASE_DIRECTORY = Path(__file__).resolve().parent

DATA_DIRECTORY = BASE_DIRECTORY / "data"
MODEL_DIRECTORY = BASE_DIRECTORY / "model"

CSV_PATH = DATA_DIRECTORY / "servo_torque.csv"

MODEL_PATH = MODEL_DIRECTORY / "isolation_forest_model.joblib"
THRESHOLD_PATH = MODEL_DIRECTORY / "threshold.json"
```

`BASE_DIRECTORY` を基準にしているため、アプリの配置場所が変わっても同じ相対構成なら動作できます。

---

## 7. 使用する特徴量

```python
FEATURES = [
    "peak_value",
    "rms",
]
```

今回のIsolation Forestは2特徴量で学習します。

各データは、概念的には次の2次元座標として扱われます。

```text
(peak_value, rms)
```

たとえば、

```text
(10, 5.40)
(12, 5.80)
(13, 5.70)
```

のような点が大量に存在し、その中で孤立しやすい点ほど異常らしいと評価されます。

1特徴量の `peak_value` だけでは同じ `peak_value` を持つデータ同士を区別できませんでした。

`rms` を加えたことで、

```text
peak_value = 13, rms = 5.30
peak_value = 13, rms = 5.70
```

のように、同じピーク値でもRMSが異なれば異なる状態として評価できるようになります。

---

## 8. 学習比率

```python
TRAIN_RATIO = 0.8
```

正常データのうち、

- 過去80%：学習用
- 未来20%：検証用

として使用します。

今回、ランダム分割ではなく**時系列分割**にしていることが重要です。

設備異常検知では、実運用も基本的に

```text
過去データで学習
        ↓
未来データを評価
```

という流れになるためです。

---

## 9. 独自しきい値の設定

```python
THRESHOLD_PERCENTILE = 0.1
```

これは、学習正常データの異常スコアのうち、**下位0.1%点をしきい値とする**設定です。

たとえば学習正常データの下位0.1%点が、

```text
-0.750212
```

だった場合、

```python
score < -0.750212
```

なら異常候補と判定します。

重要なのは、Isolation Forest標準の `predict()` を最終判定に使っていないことです。

このアプリでは、

```text
Isolation Forest
    ↓
score_samples()
    ↓
異常度を数値化
```

までをモデルの仕事とし、

```text
score
    ↓
独自thresholdと比較
    ↓
正常 / 異常候補
```

は設備アプリ側のルールとして分離しています。

---

## 10. モデル保存先フォルダの作成

```python
MODEL_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)
```

`model` フォルダが存在しない場合は自動作成します。

- `parents=True`：親フォルダも必要なら作成
- `exist_ok=True`：すでに存在していてもエラーにしない

---

## 11. CSV読込と日時変換

```python
df = pd.read_csv(CSV_PATH)

df["measured_at"] = pd.to_datetime(
    df["measured_at"]
)
```

`measured_at` を文字列のまま扱わず、pandasの日時型へ変換します。

これにより、

```python
.sort_values("measured_at")
```

で正しい時系列順に並べられます。

---

## 12. 正常データだけを抽出

```python
ok_df = (
    df[df["judge"] == "OK"]
    .copy()
    .sort_values("measured_at")
    .reset_index(drop=True)
)
```

ここでは3つの処理を連続して行っています。

### 12.1 `judge == "OK"` だけ抽出

```python
df[df["judge"] == "OK"]
```

実際のNGデータは学習から除外します。

### 12.2 `.copy()`

抽出結果を独立したDataFrameとして扱います。

### 12.3 `.sort_values("measured_at")`

古いデータから新しいデータの順へ並べます。

### 12.4 `.reset_index(drop=True)`

並べ替え後のインデックスを0から振り直します。

---

## 13. 時系列で学習80%・検証20%へ分割

```python
split_index = int(
    len(ok_df) * TRAIN_RATIO
)
```

たとえば正常データが5237件なら、

```text
5237 × 0.8 ≒ 4189
```

となります。

その位置を境に、

```python
train_df = ok_df.iloc[
    :split_index
].copy()

validation_df = ok_df.iloc[
    split_index:
].copy()
```

と分割します。

`iloc` は行番号によるスライスです。

```text
0 ～ 4188          → train_df
4189 ～ 最後       → validation_df
```

というイメージです。

---

## 14. 特徴量行列の作成

```python
X_train = train_df[FEATURES]

X_validation = validation_df[
    FEATURES
]
```

`FEATURES` は、

```python
[
    "peak_value",
    "rms",
]
```

なので、実際には、

```python
X_train = train_df[
    ["peak_value", "rms"]
]
```

と同じ意味です。

2列を指定しているため、`X_train` は2次元DataFrameになります。

---

## 15. Isolation Forestモデルの作成

```python
model = IsolationForest(
    contamination="auto",
    random_state=42,
)
```

### `contamination="auto"`

Isolation Forest内部の標準判定境界を設定するための指定です。

ただし、このアプリでは最終的に `model.predict()` の境界を使用しません。

`score_samples()` の結果に対して独自しきい値を適用するため、`contamination` は異常割合の最終ルールとしては使っていません。

### `random_state=42`

Isolation Forest内部ではランダムな木を作成します。

`random_state` を固定することで、同じデータなら原則として同じ学習結果を再現しやすくなります。

---

## 16. モデル学習

```python
model.fit(X_train)
```

ここでIsolation Forestが正常データの分布を学習します。

重要なのは、

```text
X_train = 正常データのみ
```

という点です。

実NGデータはこの段階では一切モデルに見せていません。

---

## 17. `score_samples()` で異常スコアを計算

```python
train_df["score"] = model.score_samples(
    X_train
)
```

`score_samples()` は各データの異常らしさを数値として返します。

今回のscikit-learnのIsolation Forestでは、基本的に

```text
値が高い  → 正常らしい
値が低い  → 異常らしい
```

と読みます。

今回の実データでは、正常群がおよそ `-0.4 ～ -0.7` 付近に分布し、実NGはさらに低い値になりました。

---

## 18. 学習データから独自しきい値を決める

```python
threshold = np.percentile(
    train_df["score"],
    THRESHOLD_PERCENTILE,
)
```

`THRESHOLD_PERCENTILE = 0.1` なので、正常学習データのスコアの下位0.1%点を求めています。

数式的には、しきい値を $T$ とすると、

$$
T = \mathrm{Percentile}(\mathrm{score}_{train}, 0.1)
$$

と考えられます。

判定は、

$$
\mathrm{score} < T
$$

なら異常候補です。

---

## 19. 検証データを未知データとして評価

```python
validation_df["score"] = (
    model.score_samples(
        X_validation
    )
)
```

ここで重要なのは、`validation_df` がモデル学習に使われていないことです。

つまり、

```text
過去80%で学習
        ↓
未来20%を未知データとして投入
```

という検証になっています。

---

## 20. 独自しきい値による判定

```python
validation_df["prediction"] = (
    np.where(
        validation_df["score"]
        < threshold,
        -1,
        1,
    )
)
```

`np.where()` は条件によって値を切り替えます。

今回なら、

```text
score < threshold
    ↓ Yes
prediction = -1

score >= threshold
    ↓
prediction = 1
```

です。

このアプリでは、

- `1`：正常
- `-1`：異常候補

として扱っています。

---

## 21. False Positive（誤検出）の確認

```python
false_positive_data = (
    validation_df[
        validation_df["prediction"]
        == -1
    ]
)
```

検証データはすべて実際には `OK` です。

したがって、ここで `-1` と判定されたデータはすべてFalse Positive、つまり誤検出です。

誤検出率は、

$$
\mathrm{FalsePositiveRate}
=
\frac{\mathrm{FalsePositiveCount}}
{\mathrm{ValidationCount}}
\times 100
$$

で計算しています。

```python
false_positive_rate = (
    false_positive_count
    / validation_count
    * 100
)
```

今回の検証では、下位0.1%しきい値に対して、未来側の正常データでも約0.1%程度の誤検出率となりました。

---

## 22. 実NGを完全な未知データとして評価

```python
ng_df = (
    df[df["judge"] == "NG"]
    .copy()
)
```

NGデータは学習にも、しきい値作成にも使用していません。

そのため、この1件は完全な未知データとして評価できます。

```python
ng_df["score"] = (
    model.score_samples(
        X_ng
    )
)
```

そして、

```python
ng_df["prediction"] = (
    np.where(
        ng_df["score"]
        < threshold,
        -1,
        1,
    )
)
```

として独自しきい値で判定します。

今回の実験では、実NGのスコアはしきい値より低くなり、`-1` と正しく異常判定されました。

---

## 23. 複数しきい値候補の比較

アプリでは、

```python
percentiles = [
    0.1,
    0.5,
    1.0,
    2.0,
    5.0,
]
```

を比較します。

各パーセンタイルについて、

1. 学習データから候補しきい値を作る
2. 検証正常データに適用する
3. 誤検出件数を数える
4. 誤検出率を計算する
5. 実NGを検出できるか確認する

という処理を行っています。

この考え方は非常に重要です。

しきい値を厳しくすると、

```text
誤検出は減る
        ↓
しかし弱い異常を見逃す可能性がある
```

一方、しきい値を緩くすると、

```text
異常を拾いやすくなる
        ↓
正常まで異常扱いしやすくなる
```

というトレードオフがあります。

NGデータが今後増えてくれば、RecallやFalse Positive Rateなどを見ながら、より適切なしきい値を選べるようになります。

---

## 24. 学習済みモデルの保存

```python
joblib.dump(
    model,
    MODEL_PATH,
)
```

これで学習済みIsolation Forestモデルを、

```text
model/isolation_forest_model.joblib
```

へ保存します。

実運用アプリでは毎回 `fit()` する必要はありません。

保存済みモデルを読み込んで、

```python
model.score_samples(...)
```

だけ実行できます。

---

## 25. thresholdと設定情報をJSON保存

```python
model_info = {
    "threshold": float(threshold),
    "threshold_percentile": THRESHOLD_PERCENTILE,
    "features": FEATURES,
    "train_ratio": TRAIN_RATIO,
    "train_count": len(train_df),
    "validation_count": len(validation_df),
    "validation_false_positive_count": int(
        false_positive_count
    ),
    "validation_false_positive_rate": float(
        false_positive_rate
    ),
}
```

モデル本体とは別に、判定に必要な情報をJSONで保存します。

特に重要なのは、

```json
"threshold"
```

と、

```json
"features"
```

です。

たとえば実運用アプリ側では、

```python
features = loaded_info["features"]
threshold = loaded_info["threshold"]
```

として、学習時と同じ特徴量・しきい値を確実に使用できます。

---

## 26. JSONに特徴量名を保存する理由

Isolation Forestモデルだけ保存しても、

```text
このモデルは何の特徴量で学習したのか？
```

という情報がコード外から分かりにくくなります。

今回、

```json
"features": [
    "peak_value",
    "rms"
]
```

と保存しているため、実運用側で、

```python
X = df[loaded_info["features"]]
```

のようにできます。

これにより、

```text
学習時     peak_value + rms
運用時     peak_valueだけ
```

のような入力ミスを防ぎやすくなります。

---

## 27. 保存データの再読込確認

モデルを保存しただけではなく、すぐに再読込しています。

```python
loaded_model = joblib.load(
    MODEL_PATH
)
```

JSONも同様です。

```python
with open(
    THRESHOLD_PATH,
    "r",
    encoding="utf-8",
) as f:

    loaded_info = json.load(f)
```

この確認を入れることで、

```text
保存できたつもり
```

ではなく、

```text
実際に保存したファイルから読込可能
```

までチェックできます。

---

## 28. 再読込したモデルでNGを再評価

```python
loaded_ng_scores = (
    loaded_model.score_samples(
        X_ng
    )
)
```

さらに、

```python
loaded_ng_prediction = np.where(
    loaded_ng_scores
    < loaded_threshold,
    -1,
    1,
)
```

として再判定します。

これで、

```text
学習直後のモデル
```

と、

```text
ファイル保存 → 再読込したモデル
```

で同じ判定ができることを確認しています。

実運用アプリでは後者の形を使用することになります。

---

## 29. グラフ1：`peak_value × rms` 散布図

このグラフでは、

- 正常判定された検証データ
- 誤検出された検証データ
- 実際のNG

を2次元特徴量空間に表示します。

横軸：

```text
peak_value
```

縦軸：

```text
rms
```

です。

この図の目的は、Isolation Forestの判定結果を人間が直感的に確認することです。

今回の実データでは、実NG `(35, 10.82)` が正常群から大きく離れていることを確認できました。

---

## 30. グラフ2：異常スコア分布

2つ目のグラフでは、

- 学習正常データのスコア
- 検証正常データのスコア
- 独自しきい値
- 実NGのスコア

を表示します。

このグラフを見ると、

```text
NG
 |
 |       threshold
 |           |
 |           |                    正常群
 |           |                 ███████
 |           |              ███████████
 +-----------+----------------------------> score
```

のように、正常群とNG、そして判定しきい値の位置関係を視覚的に理解できます。

---

## 31. `score_samples()` と `predict()` を分けて考える

今回のアプリで特に重要な設計思想です。

Isolation Forestには、

```python
model.predict(X)
```

もあります。

しかし今回の設備データでは、`contamination="auto"` の標準境界をそのまま使うと正常データの誤検出が多くなりました。

そこで、

```text
model.predict()
```

に最終判定を任せるのではなく、

```text
model.score_samples()
        ↓
独自threshold
        ↓
設備向け判定
```

としました。

これは、

```text
機械学習モデル
    ↓
異常度を計算する役割

設備アプリ
    ↓
どの異常度から警報にするか決める役割
```

という責務分離です。

設備アプリでは、誤報をどこまで許容できるかが機械・工程・保全運用によって変わるため、この構成は調整しやすいという利点があります。

---

## 32. なぜ正常データだけで学習するのか

今回の目的は、

```text
正常運転とはどのような状態か
```

をIsolation Forestに学習させることです。

その正常モデルから大きく外れる新規データを異常候補として検出します。

イメージすると、

```text
正常データ
    ↓
正常領域を学習
    ↓
          新しいデータ
              ↓
       正常領域の中？
        /          \
      Yes          No
       |            |
      正常        異常候補
```

という使い方です。

---

## 33. なぜNGデータを学習から外すのか

今回のNGデータを学習に含めると、Isolation ForestはNGも「観測済みのデータ」として扱います。

正常だけを学習させることで、NGを完全な未知データとして評価できます。

ただしIsolation Forestには、

```text
正常範囲の外へどれだけ遠く離れているか
```

を距離に比例して表現するモデルではない、という性質があります。

そのため、スコアの絶対値だけではなく、

```text
正常スコア分布の中でどの位置にあるか
```

を見ることが重要です。

---

## 34. 時系列分割を採用した理由

一般的な機械学習では `train_test_split()` を使ってランダムに分割することも多いですが、今回は設備データなので時系列順に分けています。

理由は、実運用では未来のデータを使って過去を予測することはできないからです。

今回の分割は、

```text
2026-09-02 前半
        ↓
学習

2026-09-02 後半
        ↓
検証
```

という形になり、実際の運用に近い検証になります。

---

## 35. 現時点での評価

今回のデータでは、正常データを時系列で80%・20%に分け、下位0.1%点をしきい値として使用した結果、

- 検証正常データに対する誤検出率は約0.1%
- 実NG 1件を異常として検出
- 実NGは正常データ群から明確に離れた位置に存在

という結果になりました。

ただし、NGが1件しかないため、

```text
下位0.1%が最適
```

と断定することはまだできません。

今後NGデータが増えた時点で、Recall、False Positive Rate、Precisionなどを使いながら再評価する必要があります。

---

## 36. 本番運用時の考え方

この学習アプリは、基本的に**モデルを作る側**です。

本番アプリでは学習処理を毎回行わず、

```text
isolation_forest_model.joblib
threshold.json
```

を読み込みます。

本番側の処理は概念的に非常にシンプルです。

```python
model = joblib.load(MODEL_PATH)

with open(
    THRESHOLD_PATH,
    "r",
    encoding="utf-8",
) as f:
    model_info = json.load(f)

threshold = model_info["threshold"]
features = model_info["features"]

X = df[features]

scores = model.score_samples(X)

predictions = np.where(
    scores < threshold,
    -1,
    1,
)
```

つまり本番では、

```text
新しい設備データ
        ↓
特徴量 peak_value / rms
        ↓
保存済みIsolation Forest
        ↓
score_samples()
        ↓
保存済みthresholdと比較
        ↓
正常 / 異常候補
```

となります。

---

## 37. 今後の発展

この学習アプリを基礎として、今後は次のような発展が考えられます。

- NGデータを増やしてRecallを評価する
- 日付の異なるデータで検証する
- 設備条件別にモデルを分ける
- 特徴量を追加する
- モデル更新時のバージョン管理を行う
- 学習日時をJSONへ保存する
- 学習期間、設備番号、品種などをモデル情報へ追加する
- pywebviewアプリから保存済みモデルを利用する
- Chart.jsで異常スコアや散布図を表示する

特に設備異常検知では、単に「モデル精度」を追うだけでなく、

```text
異常見逃しをどこまで許容するか
誤報をどこまで許容するか
```

という運用上の条件が重要になります。

---

## 38. まとめ

今回の学習アプリでは、Isolation Forestを設備異常検知へ利用するための基本構成を一通り実装しました。

最も重要なポイントは次の流れです。

```text
正常データだけを用意
        ↓
時系列で学習80%・検証20%
        ↓
Isolation Forest学習
        ↓
score_samples()
        ↓
学習正常データから独自thresholdを作成
        ↓
未来側の正常データで誤検出率を確認
        ↓
実NGを未知データとして評価
        ↓
モデル + threshold を保存
```

特に、

```text
Isolation Forest = 異常度を計算する
threshold        = 設備として異常判定する境界
```

と役割を分けたことが、このアプリの大きなポイントです。

モデル本体だけでなく、`threshold`、使用特徴量、検証結果も合わせて保存することで、次に作成する実運用アプリから安全に再利用しやすい構成になっています。

---

# 39. 完成版コード全文

以下が、今回完成した学習アプリのコード全文です。

```python
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest


# ============================================================
# 設定
# ============================================================

BASE_DIRECTORY = Path(__file__).resolve().parent

DATA_DIRECTORY = BASE_DIRECTORY / "data"
MODEL_DIRECTORY = BASE_DIRECTORY / "model"

CSV_PATH = DATA_DIRECTORY / "servo_torque.csv"

MODEL_PATH = MODEL_DIRECTORY / "isolation_forest_model.joblib"
THRESHOLD_PATH = MODEL_DIRECTORY / "threshold.json"


FEATURES = [
    "peak_value",
    "rms",
]

TRAIN_RATIO = 0.8

# 学習正常データのscore下位何%を
# 異常判定しきい値として使うか
THRESHOLD_PERCENTILE = 0.1


# ============================================================
# 保存先フォルダ作成
# ============================================================

MODEL_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# CSV読み込み
# ============================================================

df = pd.read_csv(CSV_PATH)

df["measured_at"] = pd.to_datetime(
    df["measured_at"]
)


print("===== データ件数 =====")
print(df["judge"].value_counts())


# ============================================================
# 正常データだけを取り出す
# ============================================================

ok_df = (
    df[df["judge"] == "OK"]
    .copy()
    .sort_values("measured_at")
    .reset_index(drop=True)
)


# ============================================================
# 正常データを時系列で
# 学習80% / 検証20% に分割
# ============================================================

split_index = int(
    len(ok_df) * TRAIN_RATIO
)

train_df = ok_df.iloc[
    :split_index
].copy()

validation_df = ok_df.iloc[
    split_index:
].copy()


print()
print("===== データ分割 =====")

print(
    "正常データ総数:",
    len(ok_df),
)

print(
    "学習データ:",
    len(train_df),
)

print(
    "検証データ:",
    len(validation_df),
)


print()
print("学習期間")

print(
    train_df["measured_at"].min(),
    "～",
    train_df["measured_at"].max(),
)


print()
print("検証期間")

print(
    validation_df["measured_at"].min(),
    "～",
    validation_df["measured_at"].max(),
)


# ============================================================
# 特徴量
# ============================================================

X_train = train_df[FEATURES]

X_validation = validation_df[
    FEATURES
]


# ============================================================
# Isolation Forest 学習
# ============================================================

model = IsolationForest(
    contamination="auto",
    random_state=42,
)

model.fit(X_train)


print()
print("===== 学習完了 =====")


# ============================================================
# 学習データのscoreを計算
# ============================================================

train_df["score"] = model.score_samples(
    X_train
)


# ============================================================
# 学習データだけから
# 独自しきい値を決める
# ============================================================

threshold = np.percentile(
    train_df["score"],
    THRESHOLD_PERCENTILE,
)


print()
print("===== しきい値 =====")

print(
    f"下位 {THRESHOLD_PERCENTILE}%"
)

print(
    f"threshold = {threshold:.6f}"
)


# ============================================================
# 検証用正常データを評価
# ============================================================

validation_df["score"] = (
    model.score_samples(
        X_validation
    )
)


validation_df["prediction"] = (
    np.where(
        validation_df["score"]
        < threshold,
        -1,
        1,
    )
)


# ============================================================
# 検証データの誤検出確認
# ============================================================

false_positive_data = (
    validation_df[
        validation_df["prediction"]
        == -1
    ]
)


validation_count = len(
    validation_df
)

false_positive_count = len(
    false_positive_data
)

false_positive_rate = (
    false_positive_count
    / validation_count
    * 100
)


print()
print(
    "===== 検証用正常データの結果 ====="
)

print(
    "検証件数:",
    validation_count,
)

print(
    "誤検出件数:",
    false_positive_count,
)

print(
    f"誤検出率: "
    f"{false_positive_rate:.3f}%"
)


# ============================================================
# 誤検出された検証データ
# ============================================================

print()
print(
    "===== 誤検出された検証データ ====="
)

print(
    false_positive_data[
        [
            "id",
            "measured_at",
            "peak_value",
            "rms",
            "score",
        ]
    ]
    .sort_values("score")
)


# ============================================================
# 実際のNGデータを未知データとして評価
# ============================================================

ng_df = (
    df[df["judge"] == "NG"]
    .copy()
)

X_ng = ng_df[FEATURES]


ng_df["score"] = (
    model.score_samples(
        X_ng
    )
)


ng_df["prediction"] = (
    np.where(
        ng_df["score"]
        < threshold,
        -1,
        1,
    )
)


print()
print(
    "===== 実際のNGデータ ====="
)

print(
    ng_df[
        [
            "id",
            "measured_at",
            "judge",
            "peak_value",
            "rms",
            "score",
            "prediction",
        ]
    ]
)


# ============================================================
# しきい値候補比較
#
# 学習データでしきい値を作り、
# 検証データで誤検出率を見る
# ============================================================

percentiles = [
    0.1,
    0.5,
    1.0,
    2.0,
    5.0,
]


comparison_results = []


for percentile in percentiles:

    candidate_threshold = (
        np.percentile(
            train_df["score"],
            percentile,
        )
    )


    validation_prediction = (
        np.where(
            validation_df["score"]
            < candidate_threshold,
            -1,
            1,
        )
    )


    candidate_false_positive_count = (
        validation_prediction
        == -1
    ).sum()


    candidate_false_positive_rate = (
        candidate_false_positive_count
        / len(validation_df)
        * 100
    )


    ng_prediction = (
        np.where(
            ng_df["score"]
            < candidate_threshold,
            -1,
            1,
        )
    )


    ng_detected_count = (
        ng_prediction
        == -1
    ).sum()


    comparison_results.append(
        {
            "percentile":
                percentile,

            "threshold":
                candidate_threshold,

            "false_positive_count":
                candidate_false_positive_count,

            "false_positive_rate":
                candidate_false_positive_rate,

            "ng_detected_count":
                ng_detected_count,
        }
    )


comparison_df = pd.DataFrame(
    comparison_results
)


print()
print(
    "===== しきい値候補比較 ====="
)

print(
    comparison_df.to_string(
        index=False,
        formatters={
            "threshold":
                "{:.6f}".format,

            "false_positive_rate":
                "{:.3f}".format,
        },
    )
)


# ============================================================
# 学習済みモデル保存
# ============================================================

joblib.dump(
    model,
    MODEL_PATH,
)


# ============================================================
# threshold とモデル設定をJSON保存
# ============================================================

model_info = {
    "threshold": float(threshold),
    "threshold_percentile": THRESHOLD_PERCENTILE,
    "features": FEATURES,
    "train_ratio": TRAIN_RATIO,
    "train_count": len(train_df),
    "validation_count": len(validation_df),
    "validation_false_positive_count": int(
        false_positive_count
    ),
    "validation_false_positive_rate": float(
        false_positive_rate
    ),
}


with open(
    THRESHOLD_PATH,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        model_info,
        f,
        ensure_ascii=False,
        indent=4,
    )


print()
print("===== モデル保存 =====")

print(
    "モデル:",
    MODEL_PATH,
)

print(
    "しきい値情報:",
    THRESHOLD_PATH,
)


# ============================================================
# 保存確認
# ============================================================

loaded_model = joblib.load(
    MODEL_PATH
)


with open(
    THRESHOLD_PATH,
    "r",
    encoding="utf-8",
) as f:

    loaded_info = json.load(f)


loaded_threshold = loaded_info[
    "threshold"
]


print()
print("===== 保存データ読み込み確認 =====")

print(
    "threshold:",
    loaded_threshold,
)

print(
    "features:",
    loaded_info["features"],
)


# ============================================================
# 読み込んだモデルでNGデータを再評価
# ============================================================

loaded_ng_scores = (
    loaded_model.score_samples(
        X_ng
    )
)


loaded_ng_prediction = np.where(
    loaded_ng_scores
    < loaded_threshold,
    -1,
    1,
)


print()
print(
    "===== 読み込み後のNG判定確認 ====="
)

for score, prediction in zip(
    loaded_ng_scores,
    loaded_ng_prediction,
):

    print(
        f"score = {score:.6f}, "
        f"prediction = {prediction}"
    )


# ============================================================
# グラフ1
# peak_value × rms
# ============================================================

validation_normal = (
    validation_df[
        validation_df["prediction"]
        == 1
    ]
)


plt.figure(
    figsize=(10, 6)
)


plt.scatter(
    validation_normal[
        "peak_value"
    ],
    validation_normal[
        "rms"
    ],
    s=20,
    alpha=0.5,
    label="Validation Normal",
)


plt.scatter(
    false_positive_data[
        "peak_value"
    ],
    false_positive_data[
        "rms"
    ],
    marker="x",
    s=60,
    label="False Positive",
)


plt.scatter(
    ng_df["peak_value"],
    ng_df["rms"],
    marker="x",
    s=150,
    label="Actual NG",
)


plt.xlabel(
    "peak_value"
)

plt.ylabel(
    "rms"
)

plt.title(
    "Isolation Forest Validation"
)

plt.grid()

plt.legend()


# ============================================================
# グラフ2
# 学習 / 検証 score分布
# ============================================================

plt.figure(
    figsize=(10, 6)
)


plt.hist(
    train_df["score"],
    bins=50,
    alpha=0.5,
    label="Train OK",
)


plt.hist(
    validation_df["score"],
    bins=50,
    alpha=0.5,
    label="Validation OK",
)


plt.axvline(
    threshold,
    linestyle="--",
    linewidth=2,
    label=(
        f"Threshold "
        f"({threshold:.3f})"
    ),
)


for ng_score in ng_df["score"]:

    plt.axvline(
        ng_score,
        linestyle="--",
        linewidth=2,
        label=(
            f"Actual NG "
            f"({ng_score:.3f})"
        ),
    )


plt.xlabel(
    "score_samples"
)

plt.ylabel(
    "Count"
)

plt.title(
    "Isolation Forest Score Distribution"
)

plt.grid()

plt.legend()


# ============================================================
# グラフ表示
# ============================================================

plt.show()
```
