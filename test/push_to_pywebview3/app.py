import json
import threading
from datetime import datetime

import webview


stop_event = threading.Event()
clock_thread = None
window = None


class AppApi:

    def start_clock(self):
        global clock_thread

        if (
            clock_thread is not None
            and clock_thread.is_alive()
        ):
            return

        stop_event.clear()

        clock_thread = threading.Thread(
            target=clock_loop,
            daemon=True,
        )

        clock_thread.start()

    def stop_clock(self):
        stop_event.set()


def clock_loop():
    while not stop_event.wait(1):
        current_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        payload = json.dumps(
            current_time,
            ensure_ascii=False,
        )

        window.run_js(
            f"window.receiveTime({payload});"
        )


api = AppApi()

window = webview.create_window(
    "Push Clock Sample",
    "index.html",
    js_api=api,
)

webview.start()