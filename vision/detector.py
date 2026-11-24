import cv2
import numpy as np

try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    from ai_edge_litert import interpreter as tflite


DEFAULT_SCORE_THRESHOLD = 0.5


def load_label(label_path):
    with open(label_path, "r") as f:
        return [line.strip() for line in f.readlines()]


def load_model(model_path):
    interpreter = tflite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    return interpreter, input_details, output_details


def determine_pan_direction(
    center_x,
    frame_width,
    previous_pan_direction,
    enter_dead_zone=50,
    exit_dead_zone=70,
):
    frame_center_x = frame_width // 2
    error_x = center_x - frame_center_x

    if previous_pan_direction == "CENTER":
        if error_x < -exit_dead_zone:
            return "LEFT", error_x

        if error_x > exit_dead_zone:
            return "RIGHT", error_x

        return "CENTER", error_x

    if previous_pan_direction == "LEFT":
        if error_x >= -enter_dead_zone:
            return "CENTER", error_x

        return "LEFT", error_x

    if previous_pan_direction == "RIGHT":
        if error_x <= enter_dead_zone:
            return "CENTER", error_x

        return "RIGHT", error_x

    return "CENTER", error_x


def determine_tilt_direction(
    center_y,
    frame_height,
    previous_tilt_direction,
    enter_dead_zone=45,
    exit_dead_zone=70,
):
    frame_center_y = frame_height // 2
    error_y = center_y - frame_center_y

    if previous_tilt_direction == "CENTER":
        if error_y < -exit_dead_zone:
            return "UP", error_y

        if error_y > exit_dead_zone:
            return "DOWN", error_y

        return "CENTER", error_y

    if previous_tilt_direction == "UP":
        if error_y >= -enter_dead_zone:
            return "CENTER", error_y

        return "UP", error_y

    if previous_tilt_direction == "DOWN":
        if error_y <= enter_dead_zone:
            return "CENTER", error_y

        return "DOWN", error_y

    return "CENTER", error_y


def preprocess_frame(frame, input_shape):
    height = input_shape[1]
    width = input_shape[2]

    resized = cv2.resize(frame, (width, height))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    return rgb[np.newaxis]


def run_inference(
    interpreter,
    input_details,
    output_details,
    input_tensor,
):
    input_index = input_details[0]["index"]

    interpreter.set_tensor(input_index, input_tensor)
    interpreter.invoke()

    boxes = interpreter.get_tensor(
        output_details[0]["index"]
    )

    classes = interpreter.get_tensor(
        output_details[1]["index"]
    )

    scores = interpreter.get_tensor(
        output_details[2]["index"]
    )

    num_detections = interpreter.get_tensor(
        output_details[3]["index"]
    )

    return boxes, classes, scores, num_detections


def postprocess_detections(
    frame,
    labels,
    boxes,
    classes,
    scores,
    num_detections,
    score_threshold=DEFAULT_SCORE_THRESHOLD,
):
    results = []

    detection_count = int(num_detections[0])
    frame_height, frame_width = frame.shape[:2]

    for i in range(detection_count):

        score = float(scores[0][i])

        if score < score_threshold:
            continue

        box = boxes[0][i]

        y_min, x_min, y_max, x_max = box

        xmin_pixel = max(
            0,
            min(
                frame_width - 1,
                int(x_min * frame_width),
            ),
        )

        xmax_pixel = max(
            0,
            min(
                frame_width - 1,
                int(x_max * frame_width),
            ),
        )

        ymin_pixel = max(
            0,
            min(
                frame_height - 1,
                int(y_min * frame_height),
            ),
        )

        ymax_pixel = max(
            0,
            min(
                frame_height - 1,
                int(y_max * frame_height),
            ),
        )

        class_id = int(classes[0][i])

        if class_id < 0 or class_id >= len(labels):
            continue

        label = labels[class_id]

        center_x = (
            xmin_pixel + xmax_pixel
        ) // 2

        center_y = (
            ymin_pixel + ymax_pixel
        ) // 2

        result = {
            "label": label,
            "score": score,
            "center_x": center_x,
            "center_y": center_y,
            "bbox": (
                xmin_pixel,
                ymin_pixel,
                xmax_pixel,
                ymax_pixel,
            ),
        }

        results.append(result)

        text = f"{label} {score:.2f}"

        cv2.putText(
            frame,
            text,
            (xmin_pixel, ymin_pixel),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )

        cv2.rectangle(
            frame,
            (xmin_pixel, ymin_pixel),
            (xmax_pixel, ymax_pixel),
            (0, 255, 0),
            2,
        )

    return frame, results