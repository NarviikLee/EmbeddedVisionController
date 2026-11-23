import time

from communication.serial_comm import (
    connect_serial,
    send_tilt,
)

if __name__ == "__main__":
    ser = None

    try:
        ser = connect_serial()
        print("[INFO] Serial connected")

        print("[TEST] TILT UP")
        for i in range(4):
            send_tilt(ser, "UP")
            print(f"UP {i + 1}/4")
            time.sleep(0.3)

        time.sleep(1.0)

        print("[TEST] TILT DOWN")
        for i in range(4):
            send_tilt(ser, "DOWN")
            print(f"DOWN {i + 1}/4")
            time.sleep(0.3)

        print("[INFO] TILT test complete")

    except Exception as e:
        print(f"[ERROR] {e}")

    finally:
        if ser is not None:
            ser.close()