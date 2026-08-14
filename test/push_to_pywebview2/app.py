import json
import threading
from datetime import datetime

import webview


class Clock:
    """時計処理を管理する。"""

    # Python内部用クラスのため、pywebviewのJavaScript API公開対象から除外する。
    _serializable = False

    def __init__(self):
        self.window = None
        self.stop_event = threading.Event()
        self.clock_thread = None

    def set_window(self, window):
        """JavaScriptへPushするためのpywebviewウィンドウを保持する。"""
        self.window = window

    def start(self):
        """時計処理を開始する。"""

        # すでに時計スレッドが動作中なら何もしない
        if (
            self.clock_thread is not None
            and self.clock_thread.is_alive()
        ):
            return

        # 前回の停止要求を解除する
        self.stop_event.clear()

        # 時計処理を別スレッドで開始する
        self.clock_thread = threading.Thread(
            target=self._clock_loop,
            name="clock-thread",
            daemon=True,
        )

        self.clock_thread.start()

    def stop(self):
        """時計処理の停止を要求する。"""
        self.stop_event.set()

    def _clock_loop(self):
        """1秒ごとに現在時刻をJavaScriptへPushする。"""

        while not self.stop_event.wait(1):
            current_time = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            payload = json.dumps(
                current_time,
                ensure_ascii=False,
            )

            if self.window is None:
                continue

            self.window.run_js(
                f"window.receiveTime({payload});"
            )


class AppApi:
    """JavaScriptから呼び出すPython API。"""

    def __init__(self, clock):
        self.clock = clock

    def start_clock(self):
        """JavaScriptから時計処理を開始する。"""
        self.clock.start()

    def stop_clock(self):
        """JavaScriptから時計処理を停止する。"""
        self.clock.stop()


clock = Clock()
api = AppApi(clock)

window = webview.create_window(
    "Push Clock Sample",
    "index.html",
    js_api=api,
)

clock.set_window(window)

webview.start()