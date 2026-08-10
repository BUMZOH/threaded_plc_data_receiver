"""PLCからモータ電流値を受信し、CSVファイルへ保存する。"""

from __future__ import annotations

import csv
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import kv_com


# -----------------------------------------------------------------------------
# 設定
# -----------------------------------------------------------------------------
PLC_IP_ADDRESS = "192.168.8.1"
POLL_INTERVAL_SECONDS = 0.1
DATA_POINT_COUNT = 1000

BASE_DIRECTORY = Path(__file__).resolve().parent


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
        request_device="B10.0",
        completion_device="B20.0",
        data_start_device="EM30000",
        output_directory=BASE_DIRECTORY / "motor1",
    ),
    MotorConfig(
        name="motor2",
        request_device="B10.1",
        completion_device="B20.1",
        data_start_device="EM32000",
        output_directory=BASE_DIRECTORY / "motor2",
    ),
    MotorConfig(
        name="motor3",
        request_device="B10.2",
        completion_device="B20.2",
        data_start_device="EM34000",
        output_directory=BASE_DIRECTORY / "motor3",
    ),
)


class MotorReceiver:
    """PLC要求監視とモータ電流データ受信を管理する。"""

    def __init__(self, plc_ip_address: str) -> None:
        self.plc_ip_address = plc_ip_address

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
        """要求デバイスを常時監視する。"""
        self._create_output_directories()
        self._print_startup_message()

        while True:
            try:
                for config in MOTOR_CONFIGS:
                    self._check_request(config)

            except (ConnectionError, OSError, TimeoutError, RuntimeError) as error:
                print(f"[{current_time()}] PLC通信エラー: {error}")

            except ValueError as error:
                print(f"[{current_time()}] PLCデータエラー: {error}")

            time.sleep(POLL_INTERVAL_SECONDS)

    def _check_request(self, config: MotorConfig) -> None:
        """1台分の受信要求を確認し、立上り時にサブスレッドを開始する。"""
        request_is_on = read_bit_device(
            self.plc_ip_address,
            config.request_device,
        )

        with self.state_lock:
            if not request_is_on:
                self.request_latched[config.name] = False
                return

            if self.request_latched[config.name]:
                return

            if self.is_receiving[config.name]:
                return

            self.request_latched[config.name] = True
            self.is_receiving[config.name] = True

        print(
            f"[{current_time()}] {config.name}: "
            f"受信要求ON ({config.request_device})"
        )

        thread = threading.Thread(
            target=self._receive_and_save,
            args=(config,),
            name=f"{config.name}-receiver",
            daemon=True,
        )
        thread.start()

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

            write_bit_device(
                self.plc_ip_address,
                config.completion_device,
                True,
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
        print(f"監視周期         : {POLL_INTERVAL_SECONDS} 秒")
        print(f"受信点数         : 各モータ {DATA_POINT_COUNT} 点（32ビット）")
        print("停止方法         : Ctrl + C")
        print("-" * 72)

        for config in MOTOR_CONFIGS:
            print(
                f"{config.name}: 要求={config.request_device}, "
                f"データ={config.data_start_device}, "
                f"完了={config.completion_device}"
            )

        print("-" * 72)
        print(f"[{current_time()}] PLC要求信号の監視を開始しました。")


def read_bit_device(plc_ip_address: str, device: str) -> bool:
    """PLCのビットデバイスを読み、ON/OFFをboolで返す。"""
    response = kv_com.read_device_u(plc_ip_address, device)

    if response in ("E0", "E1", "E2", "E3", "E4", "E5", "E6"):
        raise RuntimeError(
            f"デバイス読込みエラー: device={device}, response={response}"
        )

    try:
        value = int(response)
    except ValueError as error:
        raise RuntimeError(
            f"デバイス値を数値に変換できません: "
            f"device={device}, response={response}"
        ) from error

    if value not in (0, 1):
        raise RuntimeError(
            f"ビットデバイス値が0/1ではありません: "
            f"device={device}, value={value}"
        )

    return value == 1


def write_bit_device(
    plc_ip_address: str,
    device: str,
    is_on: bool,
) -> None:
    """PLCのビットデバイスへON/OFFを書き込む。"""
    value = 1 if is_on else 0
    response = kv_com.write_device_u(plc_ip_address, device, value)

    if response != "OK":
        raise RuntimeError(
            f"デバイス書込みエラー: device={device}, "
            f"value={value}, response={response}"
        )


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

    try:
        receiver.run()
    except KeyboardInterrupt:
        print(f"\n[{current_time()}] アプリを終了しました。")


if __name__ == "__main__":
    main()
