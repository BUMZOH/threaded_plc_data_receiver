from __future__ import annotations

import csv
import threading
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
PLC_IP_ADDRESS = "192.168.8.1"
POLL_INTERVAL_SECONDS = 0.1
DATA_POINT_COUNT = 1000

BASE_DIRECTORY = Path(__file__).resolve().parent
DATA_DIRECTORY = BASE_DIRECTORY / "data"


# -----------------------------------------------------------------------------
# CLASSES
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class MotorConfig:
    """モータごとのPLCデバイスと保存先設定。"""

    name: str
    request_device: str
    completion_device: str
    data_start_device: str
    output_directory: Path


MOTOR_CONFIGS = (
    MotorConfig(
        name="motor1",
        request_device="B100",
        completion_device="B200",
        data_start_device="EM30000",
        output_directory=DATA_DIRECTORY / "motor1",
    ),
    MotorConfig(
        name="motor2",
        request_device="B101",
        completion_device="B201",
        data_start_device="EM32000",
        output_directory=DATA_DIRECTORY / "motor2",
    ),
    MotorConfig(
        name="motor3",
        request_device="B102",
        completion_device="B202",
        data_start_device="EM34000",
        output_directory=DATA_DIRECTORY / "motor3",
    ),
)


class MotorReceiver:
    """PLC要求監視とモータ電流データ受信を管理する。"""

    def __init__(self, plc_ip_address: str) -> None:
        self.plc_ip_address = plc_ip_address

        # モータ台数分を並列実行できる固定サイズのスレッドプール。
        self.executor = ThreadPoolExecutor(
            max_workers=len(MOTOR_CONFIGS),
            thread_name_prefix="motor-receiver",
        )

        # PLC監視ループを停止するためのイベント。
        self.stop_event = threading.Event()

        # 要求信号がOFFへ戻るまで、同じ要求を再受付しないための状態。
        self.request_latched = {
            config.name: False
            for config in MOTOR_CONFIGS
        }

        # モータごとに受信処理が実行中かを表す。
        self.is_receiving = {
            config.name: False
            for config in MOTOR_CONFIGS
        }

        self.state_lock = threading.Lock()

    def run(self) -> None:
        """要求デバイスを監視する。"""
        self._create_output_directories()
        self._print_startup_message()

        while not self.stop_event.is_set():
            try:
                for config in MOTOR_CONFIGS:
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

    def _check_request(self, config: MotorConfig) -> None:
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
                f"デバイス読み込みエラー: "
                f"device={config.request_device}, response={response}"
            )

        with self.state_lock:
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

    def _receive_and_save(self, config: MotorConfig) -> None:
        """電流値を受信・保存し、PLCへ受信完了を通知する。"""
        try:
            print(
                f"[{current_time()}] {config.name}: "
                f"データ受信開始 ({config.data_start_device}, "
                f"{DATA_POINT_COUNT}点)"
            )

            # 2Wordで1点のため、32ビットデータとして1000点読み込む。
            values = kv_com.read_devices_d(
                self.plc_ip_address,
                config.data_start_device,
                DATA_POINT_COUNT,
            )

            csv_path = save_csv(config, values)

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
                f"    保存先: {csv_path}\n"
                f"    完了通知ON: {config.completion_device}"
            )

        except (ConnectionError, OSError, TimeoutError, RuntimeError, ValueError) as error:
            print(f"[{current_time()}] {config.name}: 受信処理エラー: {error}")

        finally:
            with self.state_lock:
                self.is_receiving[config.name] = False

    @staticmethod
    def _create_output_directories() -> None:
        for config in MOTOR_CONFIGS:
            config.output_directory.mkdir(parents=True, exist_ok=True)

    def _print_startup_message(self) -> None:
        print("=" * 72)
        print("モータ電流値 受信アプリ")
        print("=" * 72)
        print(f"PLC IPアドレス : {self.plc_ip_address}")
        print(f"監視周期       : {POLL_INTERVAL_SECONDS} 秒")
        print(f"受信点数       : 各モータ {DATA_POINT_COUNT} 点 (32ビット)")
        print("=" * 72)

        for config in MOTOR_CONFIGS:
            print(
                f"{config.name}: 要求={config.request_device}, "
                f"データ={config.data_start_device}, "
                f"完了={config.completion_device}"
            )


class AppApi:
    """GUIから呼び出すPython API。"""

    def __init__(self, receiver: MotorReceiver) -> None:
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
            monitor_thread = self.monitor_thread
            self.receiver.stop()

        if monitor_thread is not None:
            monitor_thread.join()

        with self.lock:
            if self.monitor_thread is monitor_thread:
                self.monitor_thread = None

        return {
            "status": "stopped",
            "message": "停止中",
        }

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
def save_csv(config: MotorConfig, values: list[int]) -> Path:
    """受信した電流値をCSVファイルへ保存する。"""
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
        writer.writerow(("point_no", "current_value"))

        for point_no, value in enumerate(values, start=1):
            writer.writerow((point_no, value))

    return csv_path


def current_time() -> str:
    """コンソール表示用の現在時刻を返す。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    receiver = MotorReceiver(PLC_IP_ADDRESS)
    api = AppApi(receiver)

    window = webview.create_window(
        title="モータ電流値 受信アプリ",
        url="index.html",
        js_api=api,
        width=500,
        height=300,
        resizable=False,
    )

    window.events.closed += api.shutdown

    webview.start()


if __name__ == "__main__":
    main()
