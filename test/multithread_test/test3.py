import threading
from concurrent.futures import ThreadPoolExecutor


counter = 0
counter_lock = threading.Lock()


def increment() -> None:
    global counter

    with counter_lock:
        counter += 1


def main() -> None:
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(increment)
            for _ in range(1000)
        ]

        for future in futures:
            future.result()

    print(counter)


if __name__ == "__main__":
    main()