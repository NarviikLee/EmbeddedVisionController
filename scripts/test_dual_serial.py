import time

from communication.serial_comm import (
    connect_serial,
    send_track,
    send_tilt,
)

ser = None

try:
    ser = connect_serial()

    print("[INFO] Serial connected")

    # 1. PAN 단독 테스트
    print("\n[TEST 1] PAN LEFT")
    for i in range(3):
        send_track(ser, "LEFT")
        print(f"TX PAN -> LEFT ({i + 1}/3)")
        time.sleep(0.5)

    # 2. TILT 단독 테스트
    print("\n[TEST 2] TILT DOWN")
    for i in range(3):
        send_tilt(ser, "DOWN")
        print(f"TX TILT -> DOWN ({i + 1}/3)")
        time.sleep(0.5)

    # 3. PAN + TILT 연속 전송 테스트
    print("\n[TEST 3] PAN RIGHT + TILT UP")

    for i in range(3):
        send_track(ser, "RIGHT")
        print("TX PAN -> RIGHT")

        time.sleep(0.1)  # 두 패킷 사이 100ms 대기

        send_tilt(ser, "UP")
        print("TX TILT -> UP")

        time.sleep(0.6)

    # 4. 위치 유지
    print("\n[TEST 4] CENTER")
    send_track(ser, "CENTER")
    send_tilt(ser, "CENTER")

    print("[INFO] Test completed")

except KeyboardInterrupt:
    print("\n[INFO] Stopped by user")

except Exception as e:
    print(f"[ERROR] {e}")

finally:
    if ser is not None and ser.is_open:
        ser.close()
        print("[INFO] Serial port closed")