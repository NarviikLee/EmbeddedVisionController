import cv2
import argparse
from vision.detector import (
    load_label,
    load_model,
    preprocess_frame,
    run_inference,
    postprocess_detections,
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
    previous_direction = None
    ser = None
    try:
        cap = cv2.VideoCapture(0)
        ser = connect_serial()
        if not cap.isOpened():
            print("Camera Open Failed")
            exit()
        while True:
            ret, frame = cap.read()
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
                direction = target["direction"]
                if direction != previous_direction:
                    sent_bytes = send_track(ser, direction)
                    command, payload = receive_packet(ser)
                    print(f"TX -> TRACK:{direction} | {sent_bytes} bytes")
                    print(f"Rx <- {command}:{payload}")
                    previous_direction = direction
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
