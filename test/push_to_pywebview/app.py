import json
import time

import webview


def push_data(window):
    # アプリ起動後、3秒待つ
    time.sleep(3)
    
    values = [100, 200, 300, 400, 500]

    payload = json.dumps(
        {
            "data_name": "motor1",
            "values": values,
        }
    )

    window.run_js(
        f"window.receiveData({payload});"
    )

window = webview.create_window(
    "Push Sample",
    "index.html",
)

webview.start(
    push_data,
    window
)