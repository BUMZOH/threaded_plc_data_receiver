"""SQLiteに保存された測定波形をpywebview + Chart.jsで1件ずつ表示する。"""

from __future__ import annotations

import csv
import sqlite3
import struct
from pathlib import Path

import webview

import data_analysis


BASE_DIRECTORY = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIRECTORY.parent / "data" / "measurement_data.db"
HTML_PATH = BASE_DIRECTORY / "index.html"
OUTPUT_DIRECTORY = BASE_DIRECTORY / "output"


class Api:
    """JavaScript側から呼び出すPython API。"""

    def get_filter_options(self) -> dict:
        """data_name一覧と測定日時の範囲を返す。"""
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
        data_name: str,
        judge: str,
        start_at: str,
        end_at: str,
    ) -> dict:
        """指定条件に一致する測定データをSQLiteから読み込む。"""
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

    def append_analysis_csv(
        self,
        data_name: str,
        function_name: str,
        record_id: int,
        measured_at: str,
        judge: str,
        features: list[dict],
    ) -> None:
        """解析結果をCSVファイルへ追記する。"""

        OUTPUT_DIRECTORY.mkdir(exist_ok=True)

        csv_path = OUTPUT_DIRECTORY / f"{data_name}({function_name}).csv"

        file_exists = csv_path.exists()

        feature_names = [
            feature["name"]
            for feature in features
        ]

        feature_values = [
            feature["value"]
            for feature in features
        ]

        # 特徴量が5個未満の場合は空欄で埋める
        while len(feature_names) < 5:
            feature_names.append("")

        while len(feature_values) < 5:
            feature_values.append("")

        with csv_path.open("a", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)

            # 新規ファイルの場合だけヘッダーを書く
            if not file_exists:
                writer.writerow([
                    "id",
                    "measured_at",
                    "judge",
                    *feature_names,
                ])

            writer.writerow([
                record_id,
                measured_at,
                judge,
                *feature_values,
            ])

    

def main() -> None:
    """アプリを起動する。"""
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"データベースが見つかりません: {DATABASE_PATH}"
        )

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
