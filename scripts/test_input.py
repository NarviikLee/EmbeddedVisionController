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

                raw_center_x = target["center_x"]
                raw_center_y = target["center_y"]

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
                    filtered_center_y = float(raw_center_y)
                else:
                    filtered_center_y = (
                        alpha_y * raw_center_y
                        + (1 - alpha_y) * filtered_center_y
                    )

                # -------------------------
                # PAN 방향 판단
                # -------------------------
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
                        f"PAN={pan_direction}, "
                        f"raw_x={raw_center_x}, "
                        f"filtered_x={filtered_center_x:.1f}, "
                        f"error_x={pan_error:.1f} | "
                        f"TILT={tilt_direction}, "
                        f"raw_y={raw_center_y}, "
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

                if should_send_pan:

                    send_track(
                        ser,
                        pan_direction
                    )

                    if args.verbose:
                        print(
                            f"TX PAN -> {pan_direction}"
                        )

                    last_sent_pan_direction = pan_direction
                    last_pan_move_time = now

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
                        >= 0.4
                    ):
                        should_send_tilt = True

                if should_send_tilt:

                    send_tilt(
                        ser,
                        tilt_direction
                    )

                    if args.verbose:
                        print(
                            f"TX TILT -> {tilt_direction}"
                        )

                    last_sent_tilt_direction = tilt_direction
                    last_tilt_move_time = now

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

        print(
            "[INFO] Releasing camera..."
        )

        if cap is not None:
            cap.release()

        if ser is not None:
            ser.close()

        if not args.headless:
            cv2.destroyAllWindows()