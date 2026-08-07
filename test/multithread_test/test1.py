import time
from concurrent.futures import ThreadPoolExecutor


def work(name: str) -> None:
    print(f"{name}: 開始")
    time.sleep(2)
    print(f"{name}: 完了")


def main() -> None:
    with ThreadPoolExecutor(max_workers=3) as executor:
        executor.submit(work, "motor1")
        executor.submit(work, "motor2")
        executor.submit(work, "motor3")


if __name__ == "__main__":
    main()