"""SQLiteに保存された測定波形をpywebview + Chart.jsで1件ずつ表示する。"""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import webview


BASE_DIRECTORY = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIRECTORY.parent / "data" / "measurement_data.db"
HTML_PATH = BASE_DIRECTORY / "index.html"


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
