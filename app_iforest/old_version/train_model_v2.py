from pathlib import Path

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

TRAIN_OK_PATH = DATA_DIRECTORY / "train_ok.csv"
TRAIN_NG_PATH = DATA_DIRECTORY / "train_ng.csv"
TEST_OK_PATH = DATA_DIRECTORY / "test_ok.csv"
TEST_NG_PATH = DATA_DIRECTORY / "test_ng.csv"

MODEL_DIRECTORY = BASE_DIRECTORY / "model"
MODEL_PATH = MODEL_DIRECTORY / "isolation_forest_model.joblib"

# 学習用正常データ利用数 (整数 または "max")
TRAIN_OK_DATA_NUM = "max"

# 以下CSVファイルのカラム名を設定する
FEATURE1 = "peak_value"
FEATURE2 = "rms"
FEATURES = [FEATURE1, FEATURE2]

# 以下はヒストグラムを見ながら設定する
# (グラフ表示時に確認するだけの目的で使用)
THRESHOLD = -0.8

# 整数、または "auto" (ヒストグラム分割設定)
BINS = "auto"

# Isolation Forest ハイパーパラメータ
RANDOM_STATE = 42
N_ESTIMATOR = 100    # default=100
MAX_SAMPLES = 8192   # default=256


# ============================================================
# 関数
# ============================================================
def load_csv(
    csv_path: Path,
    required: bool = True,
    max_data_num: int | str = "max",
) -> pd.DataFrame | None:
    if not csv_path.exists():
        if required:
            raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")

        return None

    if max_data_num == "max":
        df = pd.read_csv(csv_path)
    elif isinstance(max_data_num, int) and max_data_num > 0:
        df = pd.read_csv(csv_path, nrows=max_data_num)
    else:
        raise ValueError(
            'max_data_num は正の整数、または "max" を指定してください'
        )

    missing_features = [
        feature
        for feature in FEATURES
        if feature not in df.columns
    ]

    if missing_features:
        raise ValueError(f"{csv_path.name} に必要な特徴量がありません: {missing_features}")

    return df


def create_hist_bins(dataframes: list[pd.DataFrame | None]) -> int | np.ndarray:
    """
    ヒストグラムで使用するビンを作成する。

    BINSが整数の場合は、その値をそのまま使用する。
    BINSが"auto"の場合は、各DataFrameのscore列を結合し、
    全データ数の平方根を基準としてビン数を決定する。
    ビン数は最小10、最大100に制限する。
    最小スコアから最大スコアまでを等間隔に分割し、
    ヒストグラムで使用するビンの境界値を返す。
    """
    if BINS != "auto":
        return BINS

    score_arrays: list[np.ndarray] = []

    for df in dataframes:
        if df is None or df.empty:
            continue

        score_arrays.append(df["score"].to_numpy())

    if not score_arrays:
        return 10

    all_scores = np.concatenate(score_arrays)

    score_min = all_scores.min()
    score_max = all_scores.max()

    if score_min == score_max:
        return 1

    data_count = len(all_scores)

    bin_count = int(np.sqrt(data_count))
    bin_count = max(10, min(bin_count, 100))

    return np.linspace(score_min, score_max, bin_count + 1)


def add_prediction(df: pd.DataFrame, model: IsolationForest) -> pd.DataFrame:
    result_df = df.copy()

    X = result_df[FEATURES]

    result_df["score"] = model.score_samples(X)

    result_df["prediction"] = np.where(
        result_df["score"] < THRESHOLD, -1, 1
    )

    return result_df


def print_evaluation(
    title: str,
    df: pd.DataFrame,
    expected_prediction: int,
) -> None:
    count = len(df)

    if count == 0:
        print(f"\n===== {title} =====")
        print("データ件数: 0")
        return

    correct_count = (df["prediction"] == expected_prediction).sum()
    incorrect_count = count - correct_count
    correct_rate = correct_count / count * 100
    incorrect_rate = incorrect_count / count * 100

    print(f"\n===== {title} =====")
    print("データ件数:", count)
    print("正しく判定:", correct_count)
    print("誤判定", incorrect_count)
    print(f"正判定率: {correct_rate:.3f}%")
    print(f"誤判定率: {incorrect_rate:.3f}%")

    
# --- 以下 メインプロセス --------------------------------------------------------------

# ============================================================
# 保存先フォルダ作成
# ============================================================
MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)


# ============================================================
# CSV読み込み
# ============================================================
train_ok_df = load_csv(TRAIN_OK_PATH, max_data_num=TRAIN_OK_DATA_NUM)
train_ng_df = load_csv(TRAIN_NG_PATH, required=False)
test_ok_df = load_csv(TEST_OK_PATH)
test_ng_df = load_csv(TEST_NG_PATH)

print("===== 読み込みデータ件数 =====")
print("train_ok:", len(train_ok_df))

if train_ng_df is None:
    print("train_ng: ファイルなし")
else:
    print("train_ng:", len(train_ng_df))

print("test_ok:", len(test_ok_df))
print("test_ng:", len(test_ng_df))


# ============================================================
# 学習データ作成
# ============================================================
train_dataframes = [train_ok_df]

if train_ng_df is not None:
    train_dataframes.append(train_ng_df)

train_df = pd.concat(train_dataframes, ignore_index=True)
X_train = train_df[FEATURES]

print("\n===== 学習データ =====")
print("特徴量", FEATURES)
print("学習件数:", len(train_df))
print("しきい値", THRESHOLD)


# ============================================================
# Isolation Forest 学習
# ============================================================
model = IsolationForest(
    contamination="auto",
    random_state=RANDOM_STATE,
    n_estimators=N_ESTIMATOR,
    max_samples=MAX_SAMPLES,
)

model.fit(X_train)

print("\n===== 学習完了 =====")


# ============================================================
# 学習データとテストデータを評価
# ============================================================
train_ok_result = add_prediction(train_ok_df, model)

if train_ng_df is None:
    train_ng_result = None
else:
    train_ng_result = add_prediction(train_ng_df, model)

test_ok_result = add_prediction(test_ok_df, model)

test_ng_result = add_prediction(test_ng_df, model)


# ============================================================
# テスト結果
# ============================================================
print_evaluation("テスト用OKデータ", test_ok_result, expected_prediction=1)

print_evaluation("テスト用NGデータ", test_ng_result, expected_prediction=-1)


# ============================================================
# 誤判定データ表示
# ============================================================
test_ok_false_positive = (
    test_ok_result[test_ok_result["prediction"] == -1]
).copy()

test_ng_false_negative = (
    test_ng_result[test_ng_result["prediction"] == 1]
).copy()

print("\n===== OKなのにNGと判定されたデータ =====")
print(
    test_ok_false_positive[FEATURES + ["score", "prediction"]]
    .sort_values("score")
)

print("\n===== NGなのにOKと判定されたデータ =====")
print(
    test_ng_false_negative[FEATURES + ["score", "prediction"]]
    .sort_values("score", ascending=False)
)


# ============================================================
# 学習済みモデル保存
# ============================================================
joblib.dump(model, MODEL_PATH)

print("\n===== モデル保存 =====")
print("モデル:", MODEL_PATH)


# ============================================================
# グラフ1
# FEATURE1 × FEATURE2
# ============================================================
test_ok_normal = (
    test_ok_result[test_ok_result["prediction"] == 1]
)

test_ng_detected = (
    test_ng_result[test_ng_result["prediction"] == -1]
)

plt.figure(figsize=(10, 6))

plt.scatter(
    test_ok_normal[FEATURE1],
    test_ok_normal[FEATURE2],
    s=20,
    alpha=0.2,
    label="Test OK"
)

plt.scatter(
    test_ok_false_positive[FEATURE1],
    test_ok_false_positive[FEATURE2],
    marker="x",
    s=60,
    label="False Positive",
)

plt.scatter(
    test_ng_detected[FEATURE1],
    test_ng_detected[FEATURE2],
    marker="x",
    s=120,
    label="Detected NG",
)

plt.scatter(
    test_ng_false_negative[FEATURE1],
    test_ng_false_negative[FEATURE2],
    marker="o",
    s=120,
    facecolors="none",
    edgecolors="tab:red",
    linewidths=1.5,
    label="Missed NG",
)

plt.xlabel(FEATURE1)
plt.ylabel(FEATURE2)
plt.title("Isolation Forest Test Result")
plt.grid()
plt.legend()


# ============================================================
# グラフ2
# score分布
# ============================================================
hist_dataframes = [
    train_ok_result,
    train_ng_result,
    test_ok_result,
    test_ng_result,
]

hist_bins = create_hist_bins(hist_dataframes)

plt.figure(figsize=(10, 6))

plt.hist(
    train_ok_result["score"],
    bins=hist_bins,
    alpha=0.5,
    label="Train OK",
)

plt.hist(
    test_ok_result["score"],
    bins=hist_bins,
    alpha=0.5,
    label="Test OK",
)

# 学習用NGは青い縦線で表示
if (train_ng_result is not None and not train_ng_result.empty):
    for index, ng_score in enumerate(train_ng_result["score"]):
        label = "Train NG" if index == 0 else None

        plt.axvline(
            ng_score,
            color="tab:blue",
            linewidth=1.5,
            alpha=0.8,
            label=label,
        )

# テスト用NGはオレンジ縦線で表示
if not test_ng_result.empty:
    for index, ng_score in enumerate(test_ng_result["score"]):
        label = "Test NG" if index == 0 else None

        plt.axvline(
            ng_score,
            color="tab:orange",
            linewidth=1.5,
            alpha=0.8,
            label=label,
        )

plt.axvline(
    THRESHOLD,
    color="tab:green",
    linestyle="--",
    linewidth=2,
    label=f"Threshold ({THRESHOLD:.3f})",
)

plt.xlabel("score_samples")
plt.ylabel("Count")
plt.title("Isolation Forest Score Distribution")
plt.grid()
plt.legend()


# ============================================================
# グラフ3
# 評価結果サマリー
# ============================================================
train_ng_count = (0 if train_ng_result is None else len(train_ng_result))

test_ok_count = len(test_ok_result)
test_ok_correct = (test_ok_result["prediction"] == 1).sum()
test_ok_incorrect = test_ok_count - test_ok_correct

test_ng_count = len(test_ng_result)
test_ng_correct = (test_ng_result["prediction"] == -1).sum()
test_ng_incorrect = test_ng_count - test_ng_correct

if test_ok_count > 0:
    test_ok_correct_rate = test_ok_correct / test_ok_count * 100
else:
    test_ok_correct_rate = 0.0

if test_ng_count > 0:
    test_ng_correct_rate = test_ng_correct / test_ng_count * 100
else:
    test_ng_correct_rate = 0.0


fig, ax = plt.subplots(figsize=(10, 6))
ax.axis("off")
ax.set_title("Isolation Forest Evaluation Summary", fontsize=16, pad=20)


# モデル情報
model_info = [
    ["Features", ", ".join(FEATURES)],
    ["Threshold", f"{THRESHOLD:.6f}"],
    ["Train OK", f"{len(train_ok_result)}"],
    ["Train NG", f"{train_ng_count}"],
]

model_table = ax.table(
    cellText=model_info,
    colLabels=["Model / Data", "Value"],
    cellLoc="center",
    colLoc="center",
    bbox=[0.08, 0.58, 0.84, 0.30],
)

model_table.auto_set_font_size(False)
model_table.set_fontsize(11)


# テスト評価結果
evaluation_data = [
    ["Count", f"{test_ok_count}", f"{test_ng_count}"],
    ["Correct", f"{test_ok_correct}", f"{test_ng_correct}"],
    ["Incorrect", f"{test_ok_incorrect}", f"{test_ng_incorrect}"],
    ["Correct Rate[%]", f"{test_ok_correct_rate:.3f}", f"{test_ng_correct_rate:.3f}"],
]

evaluation_table = ax.table(
    cellText=evaluation_data,
    colLabels=["Evaluation", "Test OK", "Test NG"],
    cellLoc="center",
    colLoc="center",
    bbox=[0.08, 0.10, 0.84, 0.36],
)

evaluation_table.auto_set_font_size(False)
evaluation_table.set_fontsize(11)


# ============================================================
# グラフ表示
# ============================================================

plt.show()