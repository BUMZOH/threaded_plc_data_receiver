import base64
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request


# ================================================
#   Settings
# ================================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "data" / "measurement_data.db"


# ================================================
#   Flask
# ================================================
app = Flask(__name__)


# ================================================
#   Get data names
# ================================================
@app.route("/data-names")
def get_data_names():
    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT DISTINCT data_name
        FROM measurement_data
        ORDER BY data_name
        """
    )

    rows = cursor.fetchall()

    conn.close()

    return jsonify([row[0] for row in rows])


# ================================================
#   Get date range
# ================================================
@app.route("/date-range")
def get_date_range():
    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            MIN(measured_at),
            MAX(measured_at)
        FROM measurement_data
        """
    )

    row = cursor.fetchone()

    conn.close()

    return jsonify(
        {
            "start_at": row[0],
            "end_at": row[1],
        }
    )


# ================================================
#   Get measurements
# ================================================
@app.route("/measurements")
def get_measurements():
    data_name = request.args.get("data_name")
    judge = request.args.get("judge")
    start_at = request.args.get("start_at")
    end_at = request.args.get("end_at")

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    sql = """
        SELECT
            id,
            data_name,
            measured_at,
            judge,
            data
        FROM measurement_data
        WHERE
            data_name = ?
    """

    params = [data_name]

    if start_at:
        sql += " AND measured_at >= ?"
        params.append(start_at)

    if end_at:
        sql += " AND measured_at <= ?"
        params.append(end_at)

    if judge:
        sql += " AND judge = ?"
        params.append(judge)

    sql += " ORDER BY measured_at"
    sql += " LIMIT 10000"

    cursor.execute(sql, params)

    rows = cursor.fetchall()

    print("rows:", len(rows))

    conn.close()

    data = []

    for row in rows:
        data.append(
            {
                "id": row[0],
                "data_name": row[1],
                "measured_at": row[2],
                "judge": row[3],
                "data": base64.b64encode(row[4]).decode("ascii"),
            }
        )

    return jsonify(data)



# ================================================
#   Main
# ================================================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )


