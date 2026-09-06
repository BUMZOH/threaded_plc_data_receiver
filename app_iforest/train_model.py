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