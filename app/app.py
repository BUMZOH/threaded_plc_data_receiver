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
# PLC_IP_ADDRESS = "172.21.0.15"
PLC_IP_ADDRESS = "192.168.8.1"  # 自宅環境
POLL_INTERVAL_SECONDS = 0.1
DATA_POINT_COUNT = 500

SAVE_MODE = "sqlite"    # "csv" または "sqlite"

BASE_DIRECTORY = Path(__file__).resolve().parent
DATA_DIRECTORY = BASE_DIRECTORY / "data"
DATABASE_PATH = DATA_DIRECTORY / "measurement_data.db"

SQLITE_LOCK = threading.Lock()


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
    output_directory: Path


DATA_CONFIGS = (
    DataConfig(
        name="ToolB_Cross_Torque",
        request_device="B1000",
        completion_device="B1008",
        data_start_device="EM30000",
        output_directory=DATA_DIRECTORY / "data1",
    ),
    DataConfig(
        name="SpindleInverter_MotorCurrent",
        request_device="B1010",
        completion_device="B1018",
        data_start_device="EM31000",
        output_directory=DATA_DIRECTORY / "data2",
    ),
    DataConfig(
        name="motor3",
        request_device="B102",
        completion_device="B202",
        data_start_device="EM34000",
        output_directory=DATA_DIRECTORY / "motor3",
    ),
)

# ---------------------------------------------------------
class DataReceiver:
    """PLC要求監視と計測データ受信を管理する。"""

    # Python内部用クラスのため、pywebviewのJavaScript API公開対象から除外する。
    # window内部まで解析されて再帰エラーになることを防ぐ。
    _serializable = False

    def __init__(self, plc_ip_address: str) -> None:
        self.plc_ip_address = plc_ip_address
        self.window: webview.Window | None = None

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

        if SAVE_MODE == "sqlite":
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

    def set_window(self, window: webview.Window) -> None:
        """JavaScriptへ通知するためのpywebviewウィンドウを保持する。"""
        self.window = window

    def _push_data(
            self,
            config: DataConfig,
            values: list[int],
    ) -> None:
        """受信した計測データをJavaScriptへPushする。"""
        if self.window is None:
            return

        payload = json.dumps(
            {
                "data_name": config.name,
                "values": values,
            },
            ensure_ascii=False,
        )

        self.window.run_js(
            f"window.receiveData({payload});"
        )


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

            # 受信したデータをJavaScriptへPush
            self._push_data(config, values)

            save_path = save_data(config, values)

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

            print(
                f"[{current_time()}] {config.name}: 受信・保存完了\n"
                f"    保存先: {save_path}\n"
                f"    完了通知ON: {config.completion_device}"
            )

        except (ConnectionError, OSError, RuntimeError, ValueError) as error:
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
        print(f"保存形式       : {SAVE_MODE}")
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

    def get_data_names(self) -> list[str]:
        """グラフ表示対象として選択可能な測定項目名を返す。"""
        return [
            config.name
            for config in DATA_CONFIGS
        ] 
 
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
def save_data(config: DataConfig, values: list[int]) -> Path:
    """設定された保存形式に従って計測データを保存する。"""
    if SAVE_MODE == "csv":
        return save_csv(config, values)

    if SAVE_MODE == "sqlite":
        return save_sqlite(config, values)

    raise ValueError(f"保存形式が不正です: {SAVE_MODE}")


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


def save_sqlite(config: DataConfig, values: list[int]) -> Path:
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
                    data
                )
                VALUES (?, ?, ?)
                """,
                (
                    config.name,
                    measured_at,
                    binary_data,
                ),
            )

    return DATABASE_PATH


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
    if SAVE_MODE not in ("csv", "sqlite"):
        raise ValueError(f"保存形式が不正です: {SAVE_MODE}")

    receiver = DataReceiver(PLC_IP_ADDRESS)
    api = AppApi(receiver)

    window = webview.create_window(
        title="設備データ 受信アプリ",
        url="index.html",
        js_api=api,
        width=1000,
        height=800,
        resizable=True,
    )

    receiver.set_window(window)

    # pywebviewのウィンドウが閉じられたら api.shutdown() を実行する
    window.events.closed += api.shutdown

    webview.start(debug=True)


# -----------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()
