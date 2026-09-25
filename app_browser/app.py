"""SQLiteに保存された測定波形をpywebview + Chart.jsで1件ずつ表示する。"""

from __future__ import annotations

import base64
import csv
import sqlite3
import struct
from pathlib import Path

import requests
import webview

import data_analysis


BASE_DIRECTORY = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIRECTORY.parent / "data" / "measurement_data.db"
HTML_PATH = BASE_DIRECTORY / "index.html"
OUTPUT_DIRECTORY = BASE_DIRECTORY / "output"

SERVER_URL = "http://127.0.0.1:5000"


class Api:
    """JavaScript側から呼び出すPython API。"""

    def get_remote_data_names(self) -> list[str]:
        """リモートサーバからdata_name一覧を取得する"""
        response = requests.get(
            f"{SERVER_URL}/data-names",
            timeout=10,
        )

        response.raise_for_status()

        return response.json()

    def get_remote_date_range(self) -> dict:
        """リモートサーバから測定日時の範囲を取得する。"""
        response = requests.get(
            f"{SERVER_URL}/date-range",
            timeout=10,
        )

        response.raise_for_status()

        return response.json()

    def load_remote_data(
        self,
        data_name: str,
        judge: str,
        start_at: str,
        end_at: str,
    ) -> dict:
        """リモートサーバから測定データを読み込む。"""
        rows = self.get_remote_measurements(
            data_name,
            judge,
            start_at,
            end_at,
        )

        records = []

        for row in rows:
            binary_data = row["data"]

            point_count = len(binary_data) // 4

            values = struct.unpack(
                f"<{point_count}i",
                binary_data,
            )

            records.append(
                {
                    "id": row["id"],
                    "data_name": row["data_name"],
                    "measured_at": row["measured_at"],
                    "judge": row["judge"],
                    "values": list(values),
                }
            )

        return {
            "records": records,
            "record_count": len(records)
        }

    def get_remote_measurements(
            self,
            data_name: str,
            judge: str,
            start_at: str,
            end_at: str,
    ) -> list[dict]:
        """リモートサーバから測定データを取得する。"""
        params = {
            "data_name": data_name,
            "start_at": start_at,
            "end_at": end_at,
        }

        if judge != "ALL":
            params["judge"] = judge

        response = requests.get(
            f"{SERVER_URL}/measurements",
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        rows = response.json()

        for row in rows:
            row["data"] = base64.b64decode(row["data"])

        return rows

    def get_filter_options(self, data_souce: str) -> dict:
        """data_name一覧と測定日時の範囲を返す。"""

        if data_souce == "local":
            return self.get_local_filter_options()

        # -- 以下 data_source == "remote" の場合 ---
        data_names = self.get_remote_data_names()
        date_range = self.get_remote_date_range()

        return {
            "data_names": data_names,
            "min_measured_at": date_range["start_at"],
            "max_measured_at": date_range["end_at"],
        }

    def check_local_database(self):
        """ローカルSQLiteの存在を確認する。"""
        if not DATABASE_PATH.exists():
            raise FileNotFoundError(
                f"データベースが見つかりません: {DATABASE_PATH}"
            )

    def get_local_filter_options(self) -> dict:
        """ローカルSQLiteからdata_name一覧と測定日時の範囲を取得する。"""
        self.check_local_database()

        with sqlite3.connect(DATABASE_PATH) as connection:
            data_names = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT DISTINCT data_name
                    FROM measurement_data
                    ORDER BY data_name
                    """
                )
            ]

            min_measured_at, max_measured_at = connection.execute(
                """
                SELECT MIN(measured_at), MAX(measured_at)
                FROM measurement_data
                """
            ).fetchone()

        return {
            "data_names": data_names,
            "min_measured_at": min_measured_at,
            "max_measured_at": max_measured_at,
        }

    def load_data(
        self,
        data_source: str,
        data_name: str,
        judge: str,
        start_at: str,
        end_at: str,
    ) -> dict:
        """指定条件に一致する測定データを読み込む。"""

        if data_source == "remote":
            return self.load_remote_data(
                data_name,
                judge,
                start_at,
                end_at,
            )

        # --- 以下 data_source == "local" の場合 ---
        self.check_local_database()

        sql = """
            SELECT id, data_name, measured_at, judge, data
            FROM measurement_data
            WHERE data_name = ?
              AND measured_at >= ?
              AND measured_at <= ?
        """
        params: list[str] = [data_name, start_at, end_at]

        if judge != "ALL":
            sql += " AND judge = ?"
            params.append(judge)

        sql += " ORDER BY measured_at, id"
        sql += " LIMIT 10000"    # 最大取得件数


        with sqlite3.connect(DATABASE_PATH) as connection:
            rows = connection.execute(sql, params).fetchall()

        records = []

        for record_id, name, measured_at, result, binary_data in rows:
            point_count = len(binary_data) // 4

            values = struct.unpack(
                f"<{point_count}i",
                binary_data,
            )

            records.append(
                {
                    "id": record_id,
                    "data_name": name,
                    "measured_at": measured_at,
                    "judge": result,
                    "values": list(values),
                }
            )

        return {
            "records": records,
            "record_count": len(records),
        }

    def get_analysis_functions(self) -> list[str]:
        """利用可能な解析関数名の一覧を返す。"""

        return data_analysis.get_analysis_function_names()

    def analyze_data(self, function_name: str, values: list[int]) -> dict:
        """指定された解析関数で波形データを解析する。"""
        return data_analysis.analyze(function_name, values)

    def output_analysis_csv(
        self,
        function_name: str,
        records: list[dict],
    ) -> dict:
        """検索結果全件の特徴量をCSVファイルへ出力する。"""

        if not records:
            raise ValueError("出力するデータがありません。")

        OUTPUT_DIRECTORY.mkdir(exist_ok=True)

        data_name = records[0]["data_name"]

        csv_path = OUTPUT_DIRECTORY / f"{data_name}({function_name}).csv"

        rows = []
        feature_names = None

        for record in records:
            result = data_analysis.analyze(function_name, record["values"])
            features = result["features"]

            if feature_names is None:
                feature_names = [feature["name"] for feature in features]

                while len(feature_names) < 5:
                    feature_names.append("")

            feature_values = [feature["value"] for feature in features]

            while len(feature_values) < 5:
                feature_values.append("")

            rows.append([
                record["id"],
                record["measured_at"],
                record["judge"],
                *feature_values,
            ])


        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)

            writer.writerow([
                "id",
                "measured_at",
                "judge",
                *feature_names,
            ])

            writer.writerows(rows)

        return {
            "record_count": len(rows),
            "csv_path": str(csv_path),
        }        


def main() -> None:
    """アプリを起動する。"""
    api = Api()

    webview.create_window(
        "Measurement Data Viewer",
        str(HTML_PATH),
        js_api=api,
        width=1200,
        height=800,
    )

    webview.start(debug=False)


if __name__ == "__main__":
    main()
