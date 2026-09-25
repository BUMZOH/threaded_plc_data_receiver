# Isolation Forest 設備異常検知プロジェクト

設備から取得した特徴量を使って **Isolation Forest**
を学習し、設備データの異常判定を行うためのシンプルなプロジェクトです。

現在は次の2つの特徴量を使用します。

-   `peak_value`：計測データのピーク値
-   `rms`：RMS（Root Mean Square：二乗平均平方根）

このプロジェクトは、役割を次の2つに分離しています。

-   `train_model.py`
    -   CSVデータを読み込む
    -   Isolation Forestを学習する
    -   テストデータで判定結果を確認する
    -   学習済みモデルを保存する
    -   散布図・スコア分布・評価結果を表示する
-   `anomaly_detector.py`
    -   保存済みモデルを読み込む
    -   外部アプリから渡された特徴量を評価する
    -   独自しきい値と比較して `OK` / `NG` を返す

------------------------------------------------------------------------

## 1. このプロジェクトの考え方

Isolation Forestに最終的な `OK` / `NG` 判定をすべて任せるのではなく、

``` python
model.score_samples(X)
```

で異常スコアを求め、そのスコアを独自のしきい値 `THRESHOLD`
と比較します。

判定ルールは次のとおりです。

``` text
score < threshold
```

なら異常です。

``` text
設備データ
    ↓
peak_value / rms
    ↓
Isolation Forest
    ↓
score_samples()
    ↓
異常スコア
    ↓
score < threshold ?
    ↓
  Yes        No
   ↓          ↓
  NG         OK
```

役割を分けて考えると、

``` text
Isolation Forest
    → データの異常スコアを計算する

threshold
    → どのスコアから異常扱いするかを決める
```

という構成です。

------------------------------------------------------------------------

## 2. 想定フォルダ構成

``` text
project/
│
├─ train_model.py
├─ anomaly_detector.py
│
├─ data/
│   ├─ train_ok.csv
│   ├─ train_ng.csv      # 任意
│   ├─ test_ok.csv
│   └─ test_ng.csv
│
└─ model/
    └─ isolation_forest_model.joblib
```

`model` フォルダは `train_model.py`
実行時に、存在しなければ自動作成されます。

`train_ng.csv`
だけは任意です。存在しない場合でも学習処理を続行できます。

一方、次の3ファイルは現在のコードでは必須です。

``` text
train_ok.csv
test_ok.csv
test_ng.csv
```

------------------------------------------------------------------------

## 3. 必要なPythonパッケージ

主に次のパッケージを使用します。

``` text
numpy
pandas
matplotlib
scikit-learn
joblib
```

インストール例：

``` bash
pip install numpy pandas matplotlib scikit-learn joblib
```

------------------------------------------------------------------------

# 4. `train_model.py`

## 4.1 役割

`train_model.py` は **モデル作成・評価用プログラム** です。

現在の処理の流れは次のとおりです。

1.  学習用・テスト用CSVを読み込む
2.  必要な特徴量が存在するか確認する
3.  学習データを作成する
4.  Isolation Forestを学習する
5.  学習データとテストデータの `score_samples()` を計算する
6.  独自しきい値で `prediction` を付ける
7.  テスト用OK / NGデータの判定結果を集計する
8.  誤判定したデータを表示する
9.  学習済みモデルを保存する
10. 散布図を表示する
11. 異常スコアのヒストグラムを表示する
12. 評価結果のサマリーを表示する

------------------------------------------------------------------------

## 4.2 使用するCSV

### `train_ok.csv`

学習用のOKデータです。

``` python
TRAIN_OK_PATH = DATA_DIRECTORY / "train_ok.csv"
```

使用件数は、

``` python
TRAIN_OK_DATA_NUM = "max"
```

で設定します。

すべて使用する場合：

``` python
TRAIN_OK_DATA_NUM = "max"
```

先頭100件だけ使用する場合：

``` python
TRAIN_OK_DATA_NUM = 100
```

------------------------------------------------------------------------

### `train_ng.csv`

学習用のNGデータです。

``` python
TRAIN_NG_PATH = DATA_DIRECTORY / "train_ng.csv"
```

このファイルは任意です。

存在する場合、現在のコードでは `train_ok.csv` と結合され、Isolation
Forestの `fit()` に使用されます。

``` text
train_ok
    +
train_ng（存在する場合）
    ↓
pd.concat()
    ↓
学習データ
    ↓
IsolationForest.fit()
```

存在しない場合は `train_ok.csv` だけで学習します。

------------------------------------------------------------------------

### `test_ok.csv`

学習後のモデルに対して、正常データを正常と判定できるか確認するためのテストデータです。

------------------------------------------------------------------------

### `test_ng.csv`

学習後のモデルに対して、異常データを異常として検出できるか確認するためのテストデータです。

------------------------------------------------------------------------

## 4.3 CSVに必要な特徴量

現在の設定は、

``` python
FEATURE1 = "peak_value"
FEATURE2 = "rms"
FEATURES = [FEATURE1, FEATURE2]
```

です。

したがって、各CSVには少なくとも、

``` text
peak_value
rms
```

の2列が必要です。

必要な列が存在しない場合は `ValueError` を発生させます。

------------------------------------------------------------------------

## 4.4 Isolation Forestの設定

現在のハイパーパラメータは次のとおりです。

``` python
RANDOM_STATE = 42
N_ESTIMATOR = 100
MAX_SAMPLES = 8192
```

モデル作成部分：

``` python
model = IsolationForest(
    contamination="auto",
    random_state=RANDOM_STATE,
    n_estimators=N_ESTIMATOR,
    max_samples=MAX_SAMPLES,
)
```

その後、

``` python
model.fit(X_train)
```

で学習します。

### `random_state`

乱数を固定して、同じデータ・同じ設定なら結果を再現しやすくするための設定です。

### `n_estimators`

Isolation Forestを構成する木の本数です。

現在は、

``` python
N_ESTIMATOR = 100
```

です。

### `max_samples`

1本の木を作成するときに使用する最大サンプル数です。

現在は、

``` python
MAX_SAMPLES = 8192
```

です。

### `contamination="auto"`

Isolation Forest内部の標準的なしきい値計算には `"auto"`
を指定しています。

ただし、このプロジェクトの最終的な `OK` / `NG` 判定では
`model.predict()` を使用せず、`score_samples()` と独自の `THRESHOLD`
を使用します。

------------------------------------------------------------------------

# 5. 独自しきい値

現在の設定は、

``` python
THRESHOLD = -0.8
```

です。

この値は自動決定しているのではなく、コードのコメントどおり
**ヒストグラムを確認しながら設定するための値** です。

判定処理は、

``` python
result_df["score"] = model.score_samples(X)

result_df["prediction"] = np.where(
    result_df["score"] < THRESHOLD,
    -1,
    1,
)
```

です。

つまり、

``` text
score < -0.8
    ↓
prediction = -1
    ↓
NG
```

それ以外は、

``` text
prediction = 1
    ↓
OK
```

として扱います。

------------------------------------------------------------------------

# 6. テストデータによる評価

学習後、

``` python
test_ok_result
test_ng_result
```

を作成し、テストデータに対する判定結果を確認します。

## 6.1 Test OK

`test_ok.csv` は正常データなので、

``` text
prediction = 1
```

なら正しく判定できています。

`prediction = -1` になった場合は、

``` text
OKなのにNGと判定
```

したデータです。

一般的には False Positive（偽陽性）に相当します。

コードでは、

``` python
test_ok_false_positive = (
    test_ok_result[test_ok_result["prediction"] == -1]
).copy()
```

として抽出します。

------------------------------------------------------------------------

## 6.2 Test NG

`test_ng.csv` は異常データなので、

``` text
prediction = -1
```

なら異常を正しく検出できています。

`prediction = 1` になった場合は、

``` text
NGなのにOKと判定
```

したデータです。

一般的には False Negative（偽陰性）に相当します。

コードでは、

``` python
test_ng_false_negative = (
    test_ng_result[test_ng_result["prediction"] == 1]
).copy()
```

として抽出します。

------------------------------------------------------------------------

## 6.3 コンソールに表示する評価結果

`print_evaluation()` では、

``` text
データ件数
正しく判定した件数
誤判定件数
正判定率
誤判定率
```

を表示します。

これにより、しきい値を変更したときに、

``` text
正常データをNGにしすぎていないか
NGデータを見逃していないか
```

を確認できます。

------------------------------------------------------------------------

# 7. グラフによる確認

`train_model.py` は学習・評価後にMatplotlibでグラフを表示します。

画面は主に3つの領域で構成されています。

------------------------------------------------------------------------

## 7.1 特徴量の散布図

横軸：

``` text
peak_value
```

縦軸：

``` text
rms
```

として、テストデータの判定結果を表示します。

表示対象は、

``` text
Test OK
False Positive
Detected NG
Missed NG
```

です。

これにより、

``` text
正常データがどの範囲に分布しているか
NGデータがどこに存在するか
誤判定データがどこに存在するか
```

を視覚的に確認できます。

------------------------------------------------------------------------

## 7.2 `score_samples()` のヒストグラム

2つ目のグラフでは異常スコアの分布を表示します。

主に、

``` text
Train OK
Test OK
Train NG
Test NG
Threshold
```

を比較します。

OKデータはヒストグラムとして表示し、NGデータは縦線として表示します。

さらに、

``` python
ax2.axvline(THRESHOLD, ...)
```

で現在のしきい値を表示します。

このグラフが、`THRESHOLD` を検討するための重要な材料になります。

------------------------------------------------------------------------

## 7.3 ヒストグラムのビン数

``` python
BINS = "auto"
```

の場合、すべての評価対象スコアをまとめ、データ数の平方根を基準にビン数を決定します。

``` python
bin_count = int(np.sqrt(data_count))
```

ただし、

``` text
最小 10
最大 100
```

に制限しています。

固定したい場合は、

``` python
BINS = 50
```

のように整数を指定できます。

------------------------------------------------------------------------

## 7.4 評価結果サマリー

3つ目の領域には表形式で、

``` text
Features
Threshold
Train OK件数
Train NG件数
```

と、

``` text
Test OK / Test NG の件数
正判定件数
誤判定件数
正判定率
```

を表示します。

グラフと数値を同じ画面で確認できるため、しきい値調整時の比較がしやすくなっています。

------------------------------------------------------------------------

# 8. 学習済みモデルの保存

学習後、

``` python
joblib.dump(model, MODEL_PATH)
```

によってモデルを保存します。

保存先：

``` text
model/isolation_forest_model.joblib
```

`train_model.py` を再実行すると、同じパスへモデルが保存されます。

現在のコードでは **しきい値はモデルファイルには保存していません**。

`THRESHOLD` は `train_model.py` 側で設定し、実運用時は
`anomaly_detector.py` の `predict_anomaly()` に引数として渡します。

------------------------------------------------------------------------

# 9. `anomaly_detector.py`

## 9.1 役割

`anomaly_detector.py` は、保存済みIsolation Forestモデルを使って
**実際の異常判定を行うためのモジュール** です。

外部アプリから基本的に使用する関数は、

``` python
predict_anomaly()
```

です。

------------------------------------------------------------------------

## 9.2 モデルの読み込み

モデルは、

``` text
model/isolation_forest_model.joblib
```

から読み込みます。

モデルファイルが存在しない場合は、

``` python
FileNotFoundError
```

を発生させます。

------------------------------------------------------------------------

## 9.3 モデルは最初の1回だけ読み込む

モデル読み込み関数には、

``` python
@lru_cache(maxsize=1)
def _load_model():
```

を使用しています。

そのため同じPythonプロセス内で、

``` python
predict_anomaly(...)
predict_anomaly(...)
predict_anomaly(...)
```

と何度呼び出しても、モデルファイルを毎回ディスクから読み込む必要はありません。

``` text
最初の判定
    ↓
joblib.load()
    ↓
モデルをメモリに保持

2回目以降
    ↓
キャッシュ済みモデルを再利用
```

設備アプリから繰り返し異常判定する用途に向いた構成です。

------------------------------------------------------------------------

# 10. `predict_anomaly()` の使い方

現在の関数定義は、

``` python
def predict_anomaly(
    features: dict[str, float],
    threshold: float,
) -> dict:
```

です。

特徴量は辞書として渡します。

使用例：

``` python
from anomaly_detector import predict_anomaly


result = predict_anomaly(
    features={
        "peak_value": 10,
        "rms": 5.40,
    },
    threshold=-0.8,
)

print(result)
```

------------------------------------------------------------------------

## 10.1 判定処理

渡された辞書からDataFrameを作ります。

``` python
X = pd.DataFrame([features])
```

その後、

``` python
score = float(model.score_samples(X)[0])
```

で異常スコアを求めます。

判定は、

``` python
is_anomaly = score < threshold
```

です。

さらに、

``` python
prediction = -1 if is_anomaly else 1
judge = "NG" if is_anomaly else "OK"
```

として、人間や外部アプリから扱いやすい形へ変換します。

------------------------------------------------------------------------

## 10.2 戻り値

戻り値は辞書です。

``` python
{
    "features": {
        "peak_value": 10,
        "rms": 5.40,
    },
    "score": -0.45,
    "threshold": -0.8,
    "prediction": 1,
    "is_anomaly": False,
    "judge": "OK",
}
```

主なキーの意味：

  キー           内容
  -------------- ----------------------------------------
  `features`     判定に使用した特徴量
  `score`        `score_samples()` で計算した異常スコア
  `threshold`    呼び出し側から渡したしきい値
  `prediction`   正常=`1`、異常=`-1`
  `is_anomaly`   異常なら `True`
  `judge`        `"OK"` または `"NG"`

------------------------------------------------------------------------

# 11. `anomaly_detector.py` の単体テスト

`anomaly_detector.py` は直接実行することもできます。

``` bash
python anomaly_detector.py
```

ファイル末尾の、

``` python
if __name__ == "__main__":
```

以下が実行されます。

現在のテスト用しきい値は、

``` python
threshold = -0.75
```

です。

正常データ想定：

``` python
features={
    "peak_value": 10,
    "rms": 5.40,
}
```

異常データ想定：

``` python
features={
    "peak_value": 35,
    "rms": 10.82,
}
```

の2件を判定します。

この部分は `anomaly_detector.py` 単体の動作確認用です。

実運用時は外部アプリから `predict_anomaly()` を呼び出します。

------------------------------------------------------------------------

# 12. 実行手順

## STEP 1：CSVを配置する

`data` フォルダへ、

``` text
train_ok.csv
test_ok.csv
test_ng.csv
```

を配置します。

必要であれば、

``` text
train_ng.csv
```

も配置します。

------------------------------------------------------------------------

## STEP 2：設定を確認する

`train_model.py` の設定部分を確認します。

特に重要なのは、

``` python
FEATURE1 = "peak_value"
FEATURE2 = "rms"

TRAIN_OK_DATA_NUM = "max"

THRESHOLD = -0.8

N_ESTIMATOR = 100
MAX_SAMPLES = 8192
```

です。

------------------------------------------------------------------------

## STEP 3：モデルを学習する

``` bash
python train_model.py
```

を実行します。

正常に終了すると、

``` text
model/isolation_forest_model.joblib
```

が作成されます。

同時に、

-   テスト結果
-   誤判定データ
-   散布図
-   スコア分布
-   評価結果サマリー

を確認できます。

------------------------------------------------------------------------

## STEP 4：しきい値を確認する

スコア分布とテスト結果を見ながら、

``` python
THRESHOLD = -0.8
```

を調整します。

特に、

``` text
OKなのにNGと判定された件数
NGなのにOKと判定された件数
```

の両方を確認します。

------------------------------------------------------------------------

## STEP 5：異常判定モジュールをテストする

``` bash
python anomaly_detector.py
```

を実行します。

保存済みモデルが正常に読み込め、判定結果が返ることを確認します。

------------------------------------------------------------------------

# 13. 他のアプリから利用する

設備監視アプリなどからは、

``` python
from anomaly_detector import predict_anomaly
```

として読み込みます。

例：

``` python
THRESHOLD = -0.8

features = {
    "peak_value": peak_value,
    "rms": rms,
}

result = predict_anomaly(
    features=features,
    threshold=THRESHOLD,
)

if result["is_anomaly"]:
    print("異常候補です")
else:
    print("正常です")
```

判定文字列だけ必要なら、

``` python
print(result["judge"])
```

で、

``` text
OK
```

または、

``` text
NG
```

を取得できます。

------------------------------------------------------------------------

# 14. 学習側と判定側の関係

``` text
                  【モデル作成・評価】

train_ok.csv ─────┐
                  │
train_ng.csv ─────┤  ※任意
                  ↓
            train_model.py
                  ↓
          Isolation Forest
                  ↓
               fit()
                  ↓
       score_samples()で評価
                  ↓
        THRESHOLDと比較
                  ↓
       テスト結果・グラフ確認
                  ↓
    isolation_forest_model.joblib
                  │
                  │
                  ↓
                    【実運用】

             設備データ
                  ↓
        peak_value / rms
                  ↓
          anomaly_detector.py
                  ↓
          predict_anomaly()
                  ↓
       保存済みモデルを読み込む
                  ↓
           score_samples()
                  ↓
     呼び出し側のthresholdと比較
             /           \
           OK             NG
```

------------------------------------------------------------------------

# 15. 学習と実運用を分離する理由

設備データを1件判定するたびに、

``` python
model.fit()
```

を実行する必要はありません。

モデル作成時だけ、

``` text
train_model.py
    ↓
学習
評価
モデル保存
```

を行います。

通常運用では、

``` text
anomaly_detector.py
    ↓
保存済みモデルを読み込む
    ↓
新しいデータだけを評価
```

とします。

この分離により、設備アプリ側は機械学習の学習処理を持つ必要がなくなります。

設備アプリから見れば、

``` python
result = predict_anomaly(
    features=features,
    threshold=THRESHOLD,
)
```

を呼ぶだけです。

------------------------------------------------------------------------

# 16. 現在の実装で重要なポイント

## 16.1 `predict()` ではなく `score_samples()` を使う

このプロジェクトではIsolation Forest標準の、

``` python
model.predict()
```

を最終判定には使用しません。

``` python
model.score_samples()
```

でスコアを取得し、独自しきい値で判定します。

これにより、設備データを見ながら判定境界を自分で調整できます。

------------------------------------------------------------------------

## 16.2 しきい値はモデルとは別管理

現在の実装では、

``` text
isolation_forest_model.joblib
```

には学習済みIsolation Forestモデルだけを保存します。

しきい値はJSONなどへ保存していません。

そのため実運用側では、

``` python
predict_anomaly(
    features=features,
    threshold=THRESHOLD,
)
```

のように、使用するしきい値を明示的に渡します。

------------------------------------------------------------------------

## 16.3 特徴量も呼び出し側から辞書で渡す

以前の固定引数形式ではなく、

``` python
features={
    "peak_value": ...,
    "rms": ...,
}
```

という辞書形式になっています。

そのため `predict_anomaly()`
自体は、複数の特徴量をまとめて受け取れる構造です。

ただし、実際にモデルへ入力する列は **学習時の `FEATURES`
と一致させる必要があります**。

現在のモデルでは、

``` python
["peak_value", "rms"]
```

です。

------------------------------------------------------------------------

## 16.4 モデル読込をキャッシュする

`@lru_cache(maxsize=1)`
により、モデルファイルを毎回読み込まずメモリ上のモデルを再利用します。

設備から短い周期でデータを受信して繰り返し判定する場合でも、毎回
`joblib.load()` する必要がありません。

------------------------------------------------------------------------

# 17. しきい値調整の考え方

しきい値を変更すると、正常データの誤検出とNGデータの見逃しのバランスが変化します。

``` text
しきい値
    ↓
OK / NG の境界
    ↓
False Positive と False Negative のバランス
```

そのため、単純にNGをたくさん検出できればよいわけではありません。

このプロジェクトでは、

-   Test OKの正判定率
-   Test NGの正判定率
-   False Positive
-   False Negative
-   スコア分布
-   特徴量の散布図

を同時に確認できるようにしています。

実際の設備データを蓄積しながら、運用上適切な `THRESHOLD`
を決めていく想定です。

------------------------------------------------------------------------

# 18. 今後の発展候補

この構成を基礎として、今後は例えば次のような拡張が可能です。

-   SQLiteへ異常スコアを保存する
-   Tkinter / pywebviewアプリから `predict_anomaly()` を呼び出す
-   異常スコアの時系列グラフを表示する
-   異常候補発生時に警告を表示する
-   設備番号ごとにモデルを分ける
-   品種ごとにモデルを分ける
-   特徴量を追加する
-   モデル作成日時やバージョンを管理する
-   しきい値を設定ファイルへ保存する
-   実データ増加後にしきい値を再評価する
-   False Positive / False Negativeの推移を記録する

------------------------------------------------------------------------

# 19. まとめ

このプロジェクトの基本構成は非常にシンプルです。

``` text
train_model.py
    ↓
CSV読込
    ↓
Isolation Forest学習
    ↓
score_samples()
    ↓
独自THRESHOLDで評価
    ↓
テスト・グラフ確認
    ↓
モデル保存


anomaly_detector.py
    ↓
保存済みモデル読込
    ↓
新しい特徴量を受け取る
    ↓
score_samples()
    ↓
指定されたthresholdと比較
    ↓
OK / NG
```

重要なのは、

``` text
学習する処理
```

と、

``` text
実際に設備データを判定する処理
```

を分離していることです。

実運用アプリ側では機械学習の詳細を毎回意識せず、

``` python
result = predict_anomaly(
    features={
        "peak_value": peak_value,
        "rms": rms,
    },
    threshold=THRESHOLD,
)
```

と呼び出せば、

``` python
result["score"]
result["is_anomaly"]
result["judge"]
```

から必要な判定結果を取得できます。

このシンプルな構成を、今後の設備異常検知システムの基礎として使用します。
