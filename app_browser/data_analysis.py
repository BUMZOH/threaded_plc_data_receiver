"""測定波形の解析処理をまとめるモジュール。"""

def chuck_air_pressure_features(values):
    """チャックエア圧波形から特徴量を取得する。"""

    # 平均値&(Max-Min) データ位置は圧力が一定になる範囲
    target_values = values[150:250]

    average = sum(target_values) / len(target_values)
    max_min = max(target_values) - min(target_values)

    # 初期増加率 データ位置0～9の増加率(初めの90ms)
    increase_rate = (values[9] - values[0]) / 10

    return [
        {
            "name": "average",
            "value": round(average, 2),
        },
        {
            "name": "max_min",
            "value": max_min,
        },
        {
            "name": "initial_increase_rate",
            "value": round(increase_rate, 2),
        },
    ]


def remove_spike_noise(values):
    """1点だけ突出したスパイクノイズを前後2点の平均値に置き換える。"""

    filtered_values = values.copy()

    for i in range(1, len(values) - 1):

        previous_value = values[i - 1]
        current_value = values[i]
        next_value = values[i + 1]

        neighbor_average = (previous_value + next_value) / 2

        if current_value > neighbor_average * 1.5: # 異常判定条件
            filtered_values[i] = round(neighbor_average)

    return filtered_values


def spindle_motor_current_features(values):
    """スピンドルモータ電流波形から特徴量を取得する。"""

    values = remove_spike_noise(values)

    # データ位置201～310(110点)
    start = 201
    end = 310

    target_values = values[start: end + 1]

    # -------------------------
    # ピーク位置・ピーク値
    # -------------------------
    peak_candidates = []

    for i in range(start + 1, end):
        if values[i - 1] <= values[i] >= values[i + 1]:
            peak_candidates.append(i)

    # peak_candidatesに入っている位置の中から、valuesの値が一番大きくなる位置を探す
    if peak_candidates:
        peak_position = max(peak_candidates, key=lambda i: values[i])
        peak_value = values[peak_position]
    else:
        peak_position = None
        peak_value = None

    # -------------------------
    # RMS
    # -------------------------
    rms = (
        sum(value ** 2 for value in target_values)
        / len(target_values)
    ) ** 0.5

    return [
        {
            "name": "peak_position",
            "value": peak_position,
        },
        {
            "name": "peak_value",
            "value": peak_value,
        },
        {
            "name": "rms",
            "value": round(rms, 2),
        },
    ]


def tool_servo_torque_features(values):
    """ツールサーボトルク波形から特徴量を取得する。"""

    values = values.copy()

    # -------------------------
    # 前処理
    # 位置201以降で-5を下回った時点から後ろを0にする
    # (加工時でも-1程度にはなるため、0ではなく-5に設定)
    # -------------------------
    for i in range(201, len(values)):
        if values[i] < -5:
            for j in range(i, len(values)):
                values[j] = 0
            break

    # データ位置201～300
    start = 201
    end = 300

    target_values = values[start:end + 1]

    # -------------------------
    # ピーク位置・ピーク値
    # -------------------------
    peak_candidates = []

    for i in range(start + 1, end):
        if values[i - 1] <= values[i] >= values[i + 1]:
            peak_candidates.append(i)

    if peak_candidates:
        peak_position = max(
            peak_candidates,
            key= lambda i: values[i],
        )
        peak_value = values[peak_position]
    else:
        peak_position = None
        peak_value = None

    # -------------------------
    # RMS
    # -------------------------
    rms = (
        sum(value ** 2 for value in target_values)
        / len(target_values)
    ) ** 0.5

    return [
        {
            "name": "peak_position",
            "value": peak_position,
        },
        {
            "name": "peak_value",
            "value": peak_value,
        },
        {
            "name": "rms",
            "value": round(rms, 2),
        },
    ]


def basic_statistics(values):
    """波形の基本的な統計特徴量を取得する。"""

    minimum = min(values)
    maximum = max(values)
    average = sum(values) / len(values)

    return [
        {
            "name": "minimum",
            "value": minimum,
        },
        {
            "name": "maximum",
            "value": maximum,
        },
        {
            "name": "average",
            "value": round(average, 2),
        },
    ]


ANALYSIS_FUNCTIONS = {
    "chuck_air_pressure_features": chuck_air_pressure_features,
    "spindle_motor_current_features": spindle_motor_current_features,
    "tool_servo_torque_features": tool_servo_torque_features,
    "basic_statistics": basic_statistics,
}


def get_analysis_function_names():
    """登録されている解析関数名の一覧を返す。"""

    return list(ANALYSIS_FUNCTIONS.keys())

def analyze(function_name, values):
    """指定された解析関数を実行する。"""


    if function_name not in ANALYSIS_FUNCTIONS:
        raise ValueError(f"解析関数が見つかりません： {function_name}")

    function = ANALYSIS_FUNCTIONS[function_name]

    features = function(values)

    if len(features) > 5:
        raise ValueError("特徴量は最大5個までです。")

    return {
        "function_name": function_name,
        "features": features
    }



if __name__ == "__main__":

    data = [1,2,3,10,5,6]
    result = analyze("basic_statistics", data)
    print(result)

