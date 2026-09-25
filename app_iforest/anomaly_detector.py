from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest


# ============================================================
# パス設定
# ============================================================
BASE_DIRECTORY = Path(__file__).resolve().parent
MODEL_DIRECTORY = BASE_DIRECTORY / "model"

MODEL_PATH = MODEL_DIRECTORY / "isolation_forest_model.joblib"


# ============================================================
# 学習済みモデルを読み込む
# ============================================================
@lru_cache(maxsize=1)
def _load_model() -> IsolationForest:
    """
    学習済みIsolation Forestモデルを読み込む。

    lru_cacheを使用しているため、同一プロセス内では
    最初の1回だけモデルファイルを読み込み、2回目以降は
    メモリ上のモデルを再利用する。
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"モデルファイルが見つかりません: {MODEL_PATH}"
        )

    model = joblib.load(MODEL_PATH)

    return model


# ============================================================
# 異常判定
# ============================================================
def predict_anomaly(
    features: dict[str, float],
    threshold: float,
) -> dict:
    """
    複数の特徴量を使って異常判定を行う。

    featuresのキーを特徴量名、値を特徴量の値として受け取る。
    学習済みIsolation Forestモデルからscore_samples()を求め、
    scoreがthresholdより小さい場合を異常（NG）と判定する。

    Parameters
    ----------
    features : dict[str, float]
        特徴量名と特徴量の値を格納した辞書。

    threshold : float
        異常判定に使用するしきい値。

    Returns
    -------
    dict
        score、threshold、prediction、is_anomaly、judgeを格納した
        判定結果。
    """
    model = _load_model()

    # 辞書のキーを列名、値を特徴量としてDataFrameを作成する
    X = pd.DataFrame([features])

    # Isolation Forestによる異常スコア
    score = float(model.score_samples(X)[0])

    # 独自しきい値による判定
    is_anomaly = score < threshold

    prediction = -1 if is_anomaly else 1
    judge = "NG" if is_anomaly else "OK"

    return {
        "features": features.copy(),
        "score": score,
        "threshold": float(threshold),
        "prediction": prediction,
        "is_anomaly": is_anomaly,
        "judge": judge
    }


# ============================================================
# テストコード
# ============================================================
if __name__ == "__main__":
    print("===== 異常判定モジュール テスト =====")

    threshold = -0.75

    # 正常データを想定
    result_normal = predict_anomaly(
        features={"peak_value": 10, "rms": 5.40},
        threshold=threshold,
    )

    print("\n【正常データ想定】")
    for key, value in result_normal.items():
        print(f"{key}: {value}")

    # 異常データを想定
    result_anomaly = predict_anomaly(
        features={"peak_value": 35, "rms": 10.82},
        threshold=threshold,
    )

    print("\n【異常データ想定】")
    for key, value in result_anomaly.items():
        print(f"{key}: {value}")



