import time


def slow_add(x, y):
    print(f"Starting slow_add({x}, {y})...")
    time.sleep(5)  # simulate slow work
    result = x + y
    print(f"Finished: {result}")
    return result