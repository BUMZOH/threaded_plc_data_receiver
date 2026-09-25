from __future__ import annotations

import csv
import json
import sqlite3
import struct
import threading
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import webview

# Original Module
from common_lib_mw import kv_com


# -----------------------------------------------------------------------------
# 設定
# -----------------------------------------------------------------------------
BASE_DIRECTORY = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIRECTORY / "config.json"
DATA_DIRECTORY = BASE_DIRECTORY.parent / "data"
DATABASE_PATH = DATA_DIRECTORY / "measurement_data.db"

SQLITE_LOCK = threading.Lock()

# PythonからJavaScriptへPushするためのpywebviewウィンドウ。
# js_apiの公開オブジェクトツリーには含めず、モジュールレベルで管理する。
APP_WINDOW: webview.Window | None = None

# -----------------------------------------------------------------------------
# CLASSES
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class DataConfig:
    """計測データごとのPLCデバイスと保存先設定。"""

    name: str
    request_device: str
    completion_device: str
    data_start_device: str
    judge_ok_device: str
    judge_ng_device: str
    output_directory: Path

def load_config() -> dict:
    """JSON設定ファイルを読み込む。"""
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)

CONFIG = load_config()

PLC_IP_ADDRESS = CONFIG["plc_ip_address"]
POLL_INTERVAL_SECONDS = CONFIG["poll_interval_seconds"]
DATA_POINT_COUNT = CONFIG["data_point_count"]

DATA_CONFIGS = tuple(
    DataConfig(
        name=config["name"],
        request_device=config["request_device"],
        completion_device=config["completion_device"],
        data_start_device=config["data_start_device"],
        judge_ok_device=config["judge_ok_device"],
        judge_ng_device=config["judge_ng_device"],
        output_directory=DATA_DIRECTORY / config["output_directory"],
    )
    for config in CONFIG["data_configs"]
)

# ---------------------------------------------------------
class DataReceiver:
    """PLC要求監視と計測データ受信を管理する。"""
    # Python内部用クラスのため、pywebviewのJavaScript API公開対象から除外する。
    # Executor / Event / Lockなどの内部オブジェクトを解析対象にしない。
    _serializable = False

    def __init__(self, plc_ip_address: str) -> None:
        self.plc_ip_address = plc_ip_address
        self.save_mode = "sqlite"

        # データ項目数分を並列実行できる固定サイズのスレッドプール。
        self.executor = ThreadPoolExecutor(
            max_workers=len(DATA_CONFIGS),
            thread_name_prefix="data-receiver",
        )

        # PLC監視ループを停止するためのイベント。
        self.stop_event = threading.Event()

        # 要求信号がOFFへ戻るまで、同じ要求を再受付しないための状態。
        self.request_latched = {
            config.name: False
            for config in DATA_CONFIGS
        }

        # データ項目ごとに受信処理が実行中かを表す。
        self.is_receiving = {
            config.name: False
            for config in DATA_CONFIGS
        }

        self.state_lock = threading.Lock()

    def run(self) -> None:
        """要求デバイスを監視する。"""
        self._create_output_directories()

        if self.save_mode == "sqlite":
            initialize_database()

        self._print_startup_message()

        while not self.stop_event.is_set():
            try:
                for config in DATA_CONFIGS:
                    if self.stop_event.is_set():
                        break

                    self._check_request(config)

            except (ConnectionError, OSError, TimeoutError, RuntimeError) as error:
                print(f"[{current_time()}] PLC通信エラー: {error}")

            except ValueError as error:
                print(f"[{current_time()}] PLCデータエラー: {error}")

            self.stop_event.wait(POLL_INTERVAL_SECONDS)

        print(f"[{current_time()}] PLC監視を停止しました。")

    def stop(self) -> None:
        """PLC監視の停止を要求する。"""
        self.stop_event.set()

    def _check_request(self, config: DataConfig) -> None:
        """1台分の受信要求を確認し、立上り時に受信処理をスレッドプールへ投入する。"""
        response = kv_com.read_device_b(
            self.plc_ip_address,
            config.request_device,
        )

        if response == "1":
            request_is_on = True
        elif response == "0":
            request_is_on = False
        else:
            raise RuntimeError(
                f"デバイス読み込みエラー:"
                f"device={config.request_device}, response={response}"
            )

        with self.state_lock:
            # <注意> 下に行くほど、上の条件の反対(not)が含まれている
            
            if not request_is_on:
                # 要求=OFF の場合
                self.request_latched[config.name] = False
                return

            if self.request_latched[config.name]:
                # 要求=ON が連続した場合
                return

            if self.is_receiving[config.name]:
                # 要求=ON latch=OFF データ受信中の場合
                return

            # 受信処理 開始時の記録
            self.request_latched[config.name] = True
            self.is_receiving[config.name] = True

        push_status(
            f"{config.name} データ受信開始"
        )

        print(
            f"[{current_time()}] {config.name}: "
            f"受信要求ON ({config.request_device})"
        )

        self.executor.submit(
            self._receive_and_save,
            config,
        )

    def _receive_and_save(self, config: DataConfig) -> None:
        """計測データを受信・保存し、PLCへ受信完了を通知する。"""
        try:
            print(
                f"[{current_time()}] {config.name}: "
                f"データ受信開始 ({config.data_start_device}), "
                f"{DATA_POINT_COUNT}点"
            )

            # 2Wordで1点のため、32ビットデータとして指定した点数読み込む。
            values = kv_com.read_devices_l(
                self.plc_ip_address,
                config.data_start_device,
                DATA_POINT_COUNT,
            )

            # 受信データを判定する
            judge_is_ok = judge_data(values)

            if judge_is_ok:
                judge_device = config.judge_ok_device
                judge_result = "OK"
            else:
                judge_device = config.judge_ng_device
                judge_result = "NG"

            # 受信したデータをJavaScriptへPush
            push_data(config, values, judge_result)

            save_path = save_data(config, values, self.save_mode, judge_result)

            response = kv_com.write_device_b(
                self.plc_ip_address,
                judge_device,
                1,
            )

            if response != "OK":
                raise RuntimeError(
                    f"判定デバイス書き込みエラー: "
                    f"device={judge_device}, response={response}"
                )

            response = kv_com.write_device_b(
                self.plc_ip_address,
                config.completion_device,
                1,
            )

            if response != "OK":
                raise RuntimeError(
                    f"デバイス書き込みエラー: "
                    f"device={config.completion_device}, response={response}"
                )

            push_status(
                f"{config.name} 受信完了 / 判定 = {judge_result}"
            )

            print(
                f"[{current_time()}] {config.name}: 受信・保存完了\n"
                f"    保存先: {save_path}\n"
                f"    判定結果: {judge_result}\n"
                f"    判定通知ON: {judge_device}\n"
                f"    完了通知ON: {config.completion_device}"
            )

        except Exception as error:
            print(f"[{current_time()}] {config.name}: 受信処理エラー: {error}")

        finally:
            with self.state_lock:
                self.is_receiving[config.name] = False

    @staticmethod
    def _create_output_directories() -> None:
        for config in DATA_CONFIGS:
            config.output_directory.mkdir(parents=True, exist_ok=True)

    def _print_startup_message(self) -> None:
        print("=" * 72)
        print("設備データ 受信アプリ")
        print("=" * 72)
        print(f"PLC IPアドレス : {self.plc_ip_address}")
        print(f"監視周期       : {POLL_INTERVAL_SECONDS} 秒")
        print(f"受信点数       : 各データ {DATA_POINT_COUNT} 点 (32ビット)")
        print(f"保存形式       : {self.save_mode}")
        print("=" * 72)

        for config in DATA_CONFIGS:
            print(
                f"{config.name}: 要求={config.request_device}, "
                f"データ={config.data_start_device}, "
                f"完了={config.completion_device}"
            )


# ---------------------------------------------------------
class AppApi:
    """GUIから呼び出すPython API。"""

    def __init__(self, receiver: DataReceiver) -> None:
        self.receiver = receiver
        self.monitor_thread: threading.Thread | None = None
        self.lock = threading.Lock()
        self.is_shutting_down = False

    def start_monitoring(self) -> dict[str, str]:
        """PLC監視を開始する。"""
        with self.lock:
            if self.is_shutting_down:
                return {
                    "status": "stopped",
                    "message": "終了処理中",
                }

            if (
                self.monitor_thread is not None
                and self.monitor_thread.is_alive()
            ):
                return {
                    "status": "running",
                    "message": "監視中",
                }

            self.receiver.stop_event.clear()

            self.monitor_thread = threading.Thread(
                target=self.receiver.run,
                name="plc-monitor",
                daemon=False,
            )
            self.monitor_thread.start()

            print(f"[{current_time()}] PLC監視を開始しました。")

            return {
                "status": "running",
                "message": "監視中",
            }

    def stop_monitoring(self) -> dict[str, str]:
        """PLC監視を停止する。"""
        with self.lock:
            monitor_thread = self.monitor_thread    # 現在の監視スレッドを覚えておく
            self.receiver.stop()                    # stop_eventをONにして停止要求を出す

        if monitor_thread is not None:
            monitor_thread.join()                   #  監視スレッドが完全に終了するまで待つ

        with self.lock:
            # 現在のthreadと停止対象のthreadが一致しているか確認し、
            # self.monitor_threadをNoneに戻す
            if self.monitor_thread is monitor_thread:
                self.monitor_thread = None

        return {
            "status": "stopped",
            "message": "停止中",
        }

    def get_plc_ip_address(self) -> str:
        """PLC IPアドレスを返す。"""
        return self.receiver.plc_ip_address

    def get_data_names(self) -> list[str]:
        """グラフ表示対象として選択可能な測定項目名を返す。"""
        return [
            config.name
            for config in DATA_CONFIGS
        ]

    def set_save_mode(self, save_mode: str) -> None:
        """データ保存形式を設定する。"""
        if save_mode not in ("csv", "sqlite"):
            raise ValueError(f"保存形式が不正です: {save_mode}")

        self.receiver.save_mode = save_mode

    def get_saved_data(
            self,
            data_name: str,
            direction: str,
            current_key=None,
    ) -> dict | None:
        """指定した測定対象の保存データを返す。"""
        if self.receiver.save_mode == "sqlite":
            return load_saved_data_sqlite(
                data_name,
                direction,
                current_key,
            )

        if self.receiver.save_mode == "csv":
            return load_saved_data_csv(
                data_name,
                direction,
                current_key,
            )

        raise ValueError(
            f"保存形式が不正です: {self.receiver.save_mode}"
        )
 
    def get_status(self) -> dict[str, str]:
        """現在の監視状態を返す。"""
        with self.lock:
            if (
                self.monitor_thread is not None
                and self.monitor_thread.is_alive()
            ):
                return {
                    "status": "running",
                    "message": "監視中",
                }

        return {
            "status": "stopped",
            "message": "停止中",
        }

    def shutdown(self) -> None:
        """アプリ終了時の後処理を行う。"""
        with self.lock:
            if self.is_shutting_down:
                return

            self.is_shutting_down = True
            monitor_thread = self.monitor_thread
            self.receiver.stop()

        print(f"[{current_time()}] アプリを終了します。")

        if monitor_thread is not None:
            monitor_thread.join()

        self.receiver.executor.shutdown(wait=True)

        print(f"[{current_time()}] アプリを終了しました。")


# -----------------------------------------------------------------------------
# FUNCTIONS
# -----------------------------------------------------------------------------
def push_status(message: str) -> None:
    """通信状況をJavaScriptへPushする。"""
    if APP_WINDOW is None:
        return

    payload = json.dumps(
        message,
        ensure_ascii=False,
    )

    APP_WINDOW.run_js(
        f"window.receiveStatus({payload});"
    )


def push_data(
        config: DataConfig,
        values: list[int],
        judge_result: str,
) -> None:
    """受信した計測データをJavaScriptへPushする。"""
    if APP_WINDOW is None:
        return

    payload = json.dumps(
        {
            "data_name": config.name,
            "measured_at": current_time(),
            "judge": judge_result,
            "values": values,
        },
        ensure_ascii=False,
    )

    APP_WINDOW.run_js(
        f"window.receiveData({payload});"
    )


def judge_data(values: list[int]) -> bool:
    """受信データを判定し、OKならTrue、NGならFalseを返す。"""
    # 現状はOK(True)のみ返却する
    return True

def save_data(config: DataConfig, values: list[int], save_mode: str, judge_result: str) -> Path:
    """設定された保存形式に従って計測データを保存する。"""
    if save_mode == "csv":
        return save_csv(config, values)

    if save_mode == "sqlite":
        return save_sqlite(config, values, judge_result)

    raise ValueError(f"保存形式が不正です: {save_mode}")


def initialize_database() -> None:
    """SQLiteデータベースとテーブルを初期化する。"""
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS measurement_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_name TEXT NOT NULL,
                measured_at TEXT NOT NULL,
                judge TEXT NOT NULL CHECK (judge IN ('OK', 'NG')),
                data BLOB NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_measurement_data_name_time
            ON measurement_data (data_name, measured_at)
            """
        )


def save_sqlite(config: DataConfig, values: list[int], judge_result: str) -> Path:
    """受信した計測データをSQLiteへ保存する。"""
    if len(values) != DATA_POINT_COUNT:
        raise ValueError(
            f"受信点数が不正です: expected={DATA_POINT_COUNT}, "
            f"actual={len(values)}"
        )

    measured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 整数データをリトルエンディアンの32bit符号付き整数としてバイナリ化する
    binary_data = struct.pack(
        f"<{len(values)}i",
        *values,
    )

    with SQLITE_LOCK:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.execute(
                """
                INSERT INTO measurement_data (
                    data_name,
                    measured_at,
                    judge,
                    data
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    config.name,
                    measured_at,
                    judge_result,
                    binary_data,
                ),
            )

    return DATABASE_PATH


def load_saved_data_sqlite(
        data_name: str,
        direction: str,
        current_id: int | None = None,
) -> dict | None:
    """指定した測定対象の保存データをSQLiteから読み込む。"""

    if direction == "oldest":
        sql = """
            SELECT id, measured_at, judge, data
            FROM measurement_data
            WHERE data_name = ?
            ORDER BY id ASC
            LIMIT 1
        """
        params = (data_name,)

    elif direction == "latest":
        sql = """
            SELECT id, measured_at, judge, data
            FROM measurement_data
            WHERE data_name = ?
            ORDER BY id DESC
            LIMIT 1
        """
        params = (data_name,)

    elif direction == "previous":
        sql = """
            SELECT id, measured_at, judge, data
            FROM measurement_data
            WHERE data_name = ?
              AND id < ?
            ORDER BY id DESC
            LIMIT 1
        """
        params = (data_name, current_id)

    elif direction == "next":
        sql = """
            SELECT id, measured_at, judge, data
            FROM measurement_data
            WHERE data_name = ?
              AND id > ?
            ORDER BY id ASC
            LIMIT 1
        """
        params = (data_name, current_id)

    else:
        raise ValueError(f"読み込み方向が不正です: {direction}")

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(sql, params)
        row = cursor.fetchone()

    if row is None:
        return None

    record_id, measured_at, judge_result, binary_data = row

    # データ数 = BLOBのバイト数 ÷ 4（32ビット整数は4バイト）
    point_count = len(binary_data) // 4

    values = struct.unpack(
        f"<{point_count}i",
        binary_data,
    )

    return {
        "id": record_id,
        "data_name": data_name,
        "measured_at": measured_at,
        "judge": judge_result,
        "values": list(values)
    }

def load_saved_data_csv(
        data_name: str,
        direction: str,
        current_key: str | None = None,
) -> dict | None:
    """指定した測定対象の保存データをCSVファイルから読み込む。"""

    config = next(
        (
            config
            for config in DATA_CONFIGS
            if config.name == data_name
        ),
        None,
    )

    if config is None:
        raise ValueError(f"測定対象が不正です: {data_name}")

    csv_paths = sorted(
        config.output_directory.glob(f"{data_name}_*.csv"),
        key=lambda path: path.name,
    )

    if not csv_paths:
        return None

    if direction == "oldest":
        csv_path = csv_paths[0]

    elif direction == "latest":
        csv_path = csv_paths[-1]

    elif direction in ("previous", "next"):
        if current_key is None:
            return None

        file_names = [
            path.name
            for path in csv_paths
        ]

        if current_key not in file_names:
            return None

        current_index = file_names.index(current_key)

        if direction == "previous":
            next_index = current_index -1
        else:
            next_index = current_index + 1

        if not 0 <= next_index < len(csv_paths):
            return None

        csv_path = csv_paths[next_index]

    else:
        raise ValueError(f"読み込み方向が不正です: {direction}")

    values = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)

        # ヘッダー行を読み飛ばす
        next(reader)

        for row in reader:
            values.append(int(row[1]))

    timestamp_text = csv_path.stem.removeprefix(
        f"{data_name}_"
    )

    timestamp_text = timestamp_text[:15]

    measured_at = datetime.strptime(
        timestamp_text,
        "%Y%m%d_%H%M%S",
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    return {
        "id": csv_path.name,
        "data_name": data_name,
        "measured_at": measured_at,
        "values": values,
    }


def save_csv(config: DataConfig, values: list[int]) -> Path:
    """受信した計測データをCSVファイルへ保存する。"""
    if len(values) != DATA_POINT_COUNT:
        raise ValueError(
            f"受信点数が不正です: expected={DATA_POINT_COUNT}, "
            f"actual={len(values)}"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = config.output_directory / f"{config.name}_{timestamp}.csv"

    # 同じ秒に複数回保存された場合も、既存ファイルを上書きしない。
    sequence_number = 1
    while csv_path.exists():
        csv_path = config.output_directory / (
            f"{config.name}_{timestamp}_{sequence_number:03d}.csv"
        )
        sequence_number += 1

    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["point_no", "data_value"])

        for point_no, value in enumerate(values, start=1):
            writer.writerow([point_no, value])

    return csv_path


def current_time() -> str:
    """コンソール表示用の現在時刻を返す。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    global APP_WINDOW

    receiver = DataReceiver(PLC_IP_ADDRESS)
    api = AppApi(receiver)

    APP_WINDOW = webview.create_window(
        title="設備データ 受信アプリ",
        url="index.html",
        js_api=api,
        width=1000,
        height=800,
        resizable=True,
    )

    # pywebviewのウィンドウが閉じられたら api.shutdown() を実行する
    APP_WINDOW.events.closed += api.shutdown

    webview.start(debug=False)


# -----------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()
