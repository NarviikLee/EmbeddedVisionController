import cv2
import argparse
import time

from vision.detector import (
    load_label,
    load_model,
    preprocess_frame,
    run_inference,
    postprocess_detections,
    determine_pan_direction,
    determine_tilt_direction,
)

from communication.serial_comm import (
    connect_serial,
    send_track,
    send_tilt,
    send_move
)


def find_target(results, target_label="person"):
    candidates = [
        result
        for result in results
        if result["label"] == target_label
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda result: result["score"])


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without OpenCV GUI"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detection results"
    )

    args = parser.parse_args()

    interpreter, input_details, output_details = load_model(
        "models/efficientdet_lite0.tflite"
    )

    labels = load_label(
        "models/coco_labels.txt"
    )

    cap = None
    ser = None

    # PAN 상태
    previous_pan_direction = "CENTER"
    last_sent_pan_direction = None
    last_pan_move_time = 0.0

    # TILT 상태
    previous_tilt_direction = "CENTER"
    last_sent_tilt_direction = None
    last_tilt_move_time = 0.0

    # EMA
    alpha_x = 0.4
    alpha_y = 0.4

    filtered_center_x = None
    filtered_center_y = None


    # 객체를 찾지 못했을 때
    TARGET_LOST_TIMEOUT = 1.0

    last_target_seen_time = None
    target_lost = False
    try:
        cap = cv2.VideoCapture(0)
        ser = connect_serial()

        if not cap.isOpened():
            print("Camera Open Failed")
            exit()

        while True:
            start_time = time.monotonic()

            ret, frame = cap.read()

            if not ret:
                print("Frame read failed")
                break

            # 팬틸트 장착 방향 보정
            frame = cv2.flip(frame, -1)

            input_tensor = preprocess_frame(
                frame,
                input_details[0]["shape"]
            )

            boxes, classes, scores, num_detections = run_inference(
                interpreter,
                input_details,
                output_details,
                input_tensor,
            )

            res, results = postprocess_detections(
                frame,
                labels,
                boxes,
                classes,
                scores,
                num_detections,
            )

            if args.verbose and results:
                print(results[0])

            target = find_target(results)

            if target is not None:
                last_target_seen_time = time.monotonic()
                target_lost = False
                raw_center_x = target["center_x"]
                raw_center_y = target["center_y"]
                xmin, ymin, xmax, ymax = target["bbox"]

                # TILT용 상체 기준점 (bbox 상단 35%)
                tilt_target_y = int(
                    ymin + (ymax - ymin) * 0.35
                )

                frame_width = frame.shape[1]
                frame_height = frame.shape[0]

                # -------------------------
                # PAN EMA
                # -------------------------
                if filtered_center_x is None:
                    filtered_center_x = float(raw_center_x)
                else:
                    filtered_center_x = (
                        alpha_x * raw_center_x
                        + (1 - alpha_x) * filtered_center_x
                    )

                # -------------------------
                # TILT EMA
                # -------------------------
                if filtered_center_y is None:
                    filtered_center_y = float(tilt_target_y)
                else:
                    # filtered_center_y = (
                    #     alpha_y * raw_center_y
                    #     + (1 - alpha_y) * filtered_center_y
                    # )
                    filtered_center_y = (
                            alpha_y * tilt_target_y
                            + (1 - alpha_y) * filtered_center_y
                        )
                # -------------------------
                # PAN 방향 판단
                # -------------------------
                bbox_height = ymax - ymin
                bbox_ratio = bbox_height / frame_height


                pan_direction, pan_error = determine_pan_direction(
                    filtered_center_x,
                    frame_width,
                    previous_pan_direction,
                    enter_dead_zone=60,
                    exit_dead_zone=85,
                )

                # -------------------------
                # TILT 방향 판단
                # -------------------------
                tilt_direction, tilt_error = determine_tilt_direction(
                    filtered_center_y,
                    frame_height,
                    previous_tilt_direction,
                    enter_dead_zone=45,
                    exit_dead_zone=70,
                )

                previous_pan_direction = pan_direction
                previous_tilt_direction = tilt_direction

                if args.verbose:
                    print(
                        f"TILT={tilt_direction}, "
                        f"bbox_center_y={raw_center_y}, "
                        f"target_y={tilt_target_y}, "
                        f"filtered_y={filtered_center_y:.1f}, "
                        f"error_y={tilt_error:.1f}"
                    )

                now = time.monotonic()

                # =========================
                # PAN 전송 주기 계산
                # =========================
                abs_pan_error = abs(pan_error)

                if abs_pan_error > 150:
                    pan_move_interval = 0.20
                elif abs_pan_error > 100:
                    pan_move_interval = 0.30
                elif abs_pan_error > 70:
                    pan_move_interval = 0.40
                else:
                    pan_move_interval = 0.50

                should_send_pan = False

                if pan_direction == "CENTER":

                    if last_sent_pan_direction != "CENTER":
                        should_send_pan = True

                else:

                    if pan_direction != last_sent_pan_direction:
                        should_send_pan = True

                    elif (
                        now - last_pan_move_time
                        >= pan_move_interval
                    ):
                        should_send_pan = True
                abs_tilt_error = abs(tilt_error)
                if abs_tilt_error > 150:
                    tilt_move_interval = 0.30
                elif abs_tilt_error > 100:
                    tilt_move_interval = 0.40
                elif abs_tilt_error > 70:
                    tilt_move_interval = 0.50
                else:
                    tilt_move_interval = 0.60

                # =========================
                # TILT 전송
                # =========================
                should_send_tilt = False

                if tilt_direction == "CENTER":

                    if last_sent_tilt_direction != "CENTER":
                        should_send_tilt = True

                else:

                    if tilt_direction != last_sent_tilt_direction:
                        should_send_tilt = True

                    elif (
                        now - last_tilt_move_time
                        >= tilt_move_interval
                    ):
                        should_send_tilt = True
                # =========================
                # PAN / TILT 통합 UART 전송
                # =========================
                frame_center_y = frame_height // 2

                # UP/DOWN 시작 기준
                up_exit_line = frame_center_y - 70
                down_exit_line = frame_center_y + 70

                # UP/DOWN 종료 기준
                up_enter_line = frame_center_y - 45
                down_enter_line = frame_center_y + 45

                # 화면 중앙선
                cv2.line(res, (0, frame_center_y), (frame_width, frame_center_y),
                         (255, 255, 255), 1)

                # 시작 기준선 (빨강)
                cv2.line(res, (0, up_exit_line), (frame_width, up_exit_line),
                         (0, 0, 255), 2)
                cv2.line(res, (0, down_exit_line), (frame_width, down_exit_line),
                         (0, 0, 255), 2)

                # 종료 기준선 (노랑)
                cv2.line(res, (0, up_enter_line), (frame_width, up_enter_line),
                         (0, 255, 255), 1)
                cv2.line(res, (0, down_enter_line), (frame_width, down_enter_line),
                         (0, 255, 255), 1)

                # Bounding Box 중앙점 (파랑)
                cv2.circle(
                    res,
                    (raw_center_x, raw_center_y),
                    6,
                    (255, 0, 0),
                    -1
                )

                # TILT 목표점 (초록)
                cv2.circle(
                    res,
                    (raw_center_x, tilt_target_y),
                    6,
                    (0, 255, 0),
                    -1
                )

                # EMA 적용된 실제 판단점 (자홍)
                cv2.circle(
                    res,
                    (raw_center_x, int(filtered_center_y)),
                    5,
                    (255, 0, 255),
                    -1
                )
                if should_send_pan or should_send_tilt:

                    pan_command = (
                        pan_direction if should_send_pan else "HOLD"
                    )

                    tilt_command = (
                        tilt_direction if should_send_tilt else "HOLD"
                    )

                    sent_bytes = send_move(
                        ser,
                        pan_command,
                        tilt_command,
                    )

                    if args.verbose:
                        print(
                            f"TX MOVE -> {pan_command},{tilt_command} "
                            f"({sent_bytes} bytes)"
                        )

                    # 실제 전송 대상인 축만 기록 갱신
                    if should_send_pan:
                        last_sent_pan_direction = pan_direction
                        last_pan_move_time = now

                    if should_send_tilt:
                        last_sent_tilt_direction = tilt_direction
                        last_tilt_move_time = now
            elif (not target_lost and last_target_seen_time is not None and time.monotonic() - last_target_seen_time >= TARGET_LOST_TIMEOUT):
                target_lost = True
                
                filtered_center_x = None
                filtered_center_y = None

                previous_pan_direction = "CENTER"
                previous_tilt_direction = "CENTER"

                last_sent_pan_direction = None
                last_sent_tilt_direction = None

                print("[INFO] Target lost for 1 second")

            elapsed = time.monotonic() - start_time

            if elapsed > 0:
                fps = 1.0 / elapsed

                print(
                    f"FPS: {fps:.2f}, "
                    f"Frame Time: "
                    f"{elapsed * 1000:.1f} ms"
                )

            if not args.headless:

                cv2.imshow(
                    "Camera",
                    res
                )

                if (
                    cv2.waitKey(1)
                    & 0xFF
                    == ord("q")
                ):
                    break

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")

    except Exception as e:
        print(
            f"Unexpected error: {e}"
        )

    finally:
        print("[INFO] Cleaning up...")
        if ser is not None and ser.is_open:
            ser.close()
            print("[INFO] Serial port closed")

        if cap is not None:
            cap.release()
            print("[INFO] Camera released")

        if not args.headless:
            cv2.destroyAllWindows()