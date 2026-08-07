from concurrent.futures import Future, ThreadPoolExecutor
import time

def work(name: str) -> None:
    time.sleep(1)
    print(f"{name}: 実行")


executor = ThreadPoolExecutor(max_workers=3)

futures: dict[str, Future[None]] = {}

futures["motor1"] = executor.submit(work,"motor1")

time.sleep(2)

if futures["motor1"].done():
    print("motor1は完了しています")
else:
    print("motor1はまだ実行中です")

executor.shutdown(wait=True)




