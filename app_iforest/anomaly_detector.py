from functools import lru_cache
from pathlib import Path
import json

import joblib
import pandas as pd


# ============================================================
# パス設定
# ============================================================

BASE_DIRECTORY = Path(__file__).resolve().parent
MODEL_DIRECTORY = BASE_DIRECTORY / "model"

MODEL_PATH = MODEL_DIRECTORY / "isolation_forest_model.joblib"
THRESHOLD_PATH = MODEL_DIRECTORY / "threshold.json"


# ============================================================
# 学習済みモデルと設定情報を読み込む
# ============================================================

@lru_cache(maxsize=1)
def _load_model():
    """
    学習済みIsolation Forestモデルとthreshold情報を読み込む。

    lru_cacheを使用しているため、同一プロセス内では
    最初の1回だけファイルを読み込み、2回目以降は
    メモリ上のモデルを再利用する。

    Returns
    -------
    tuple
        (model, model_info)
    """

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"モデルファイルが見つかりません: {MODEL_PATH}"
        )

    if not THRESHOLD_PATH.exists():
        raise FileNotFoundError(
            f"しきい値ファイルが見つかりません: {THRESHOLD_PATH}"
        )

    model = joblib.load(MODEL_PATH)

    with open(
        THRESHOLD_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        model_info = json.load(f)

    return model, model_info


# ============================================================
# 異常判定
# ============================================================

def predict_anomaly(
    peak_value: float,
    rms: float,
) -> dict:
    """
    peak_value と rms を使って異常判定を行う。

    Parameters
    ----------
    peak_value : float
        ピーク値

    rms : float
        RMS値

    Returns
    -------
    dict
        判定結果

        {
            "peak_value": 入力値,
            "rms": 入力値,
            "score": Isolation Forestのscore_samples(),
            "threshold": 独自しきい値,
            "prediction": 1 または -1,
            "is_anomaly": True または False,
            "judge": "OK" または "NG"
        }
    """

    model, model_info = _load_model()

    threshold = float(
        model_info["threshold"]
    )

    features = model_info["features"]

    # 学習時と同じ列名・列順でDataFrameを作成する
    input_data = {
        "peak_value": peak_value,
        "rms": rms,
    }

    X = pd.DataFrame(
        [
            [
                input_data[feature]
                for feature in features
            ]
        ],
        columns=features,
    )

    # Isolation Forestによる異常スコア
    score = float(
        model.score_samples(X)[0]
    )

    # 独自しきい値による判定
    is_anomaly = score < threshold

    prediction = (
        -1
        if is_anomaly
        else 1
    )

    judge = (
        "NG"
        if is_anomaly
        else "OK"
    )

    return {
        "peak_value": float(peak_value),
        "rms": float(rms),
        "score": score,
        "threshold": threshold,
        "prediction": prediction,
        "is_anomaly": is_anomaly,
        "judge": judge,
    }


# ============================================================
# テストコード
# ============================================================

if __name__ == "__main__":

    print("===== 異常判定モジュール テスト =====")

    # 正常データを想定
    result_normal = predict_anomaly(
        peak_value=10,
        rms=5.40,
    )

    print()
    print("【正常データ想定】")

    for key, value in result_normal.items():
        print(f"{key}: {value}")


    # 異常データを想定
    result_anomaly = predict_anomaly(
        peak_value=35,
        rms=10.82,
    )

    print()
    print("【異常データ想定】")

    for key, value in result_anomaly.items():
        print(f"{key}: {value}")
