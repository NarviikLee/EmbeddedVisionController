import cv2
import argparse
import time
from vision.detector import (
    load_label,
    load_model,
    preprocess_frame,
    run_inference,
    postprocess_detections,
    determine_direction,
)

from communication.serial_comm import (
    connect_serial,
    send_track,
    receive_packet,
)

def find_target(results, target_label="person"):
    for result in results:
        if result["label"] == target_label:
            return result
    return None
if __name__ == '__main__':

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
    interpreter, input_details, output_details = load_model('models/efficientdet_lite0.tflite')
    labels = load_label('models/coco_labels.txt')


    cap = None
    previous_direction = "CENTER"
    ser = None
    last_sent_direction = None
    last_move_time = 0.0

    MOVE_INTERVAL = 0.2
    try:
        cap = cv2.VideoCapture(0)
        ser = connect_serial()
        if not cap.isOpened():
            print("Camera Open Failed")
            exit()
        while True:
            ret, frame = cap.read()
            frame = cv2.flip(frame, -1)
            if not ret:
                print("Frame read failed")
                break
            input_tensor = preprocess_frame(frame, input_details[0]['shape'])

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
            # print(results)
            if args.verbose and results:
                print(results[0])
            target = find_target(results)
            if target is not None:
                center_x = target["center_x"]
                frame_width = frame.shape[1]

                direction, error_x = determine_direction(
                    center_x,
                    frame_width,
                    previous_direction
                )

                if args.verbose:
                    print(f"direction={direction}, error_x={error_x}")

                now = time.monotonic()

                # 히스테리시스 상태는 매 프레임 갱신
                previous_direction = direction

                should_send = False

                if direction == "CENTER":
                    # CENTER 진입 시 한 번만 전송
                    if last_sent_direction != "CENTER":
                        should_send = True

                else:
                    # LEFT/RIGHT로 새로 바뀌면 즉시 전송
                    if direction != last_sent_direction:
                        should_send = True

                    # 같은 LEFT/RIGHT가 계속되면 일정 주기로 반복 전송
                    elif now - last_move_time >= MOVE_INTERVAL:
                        should_send = True

                if should_send:
                    sent_bytes = send_track(ser, direction)
                    command, payload = receive_packet(ser)

                    print(f"TX -> TRACK:{direction} | {sent_bytes} bytes")
                    print(f"Rx <- {command}:{payload}")

                    last_sent_direction = direction
                    last_move_time = now
            if not args.headless:
                cv2.imshow("Camera", res)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:

        print("[INFO] Releasing camera...")
        if cap is not None:
            cap.release()
        if ser is not None:
            ser.close()
        if not args.headless:
            cv2.destroyAllWindows()
