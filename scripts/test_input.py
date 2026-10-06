import time
import cv2
import numpy as np
import tflite_runtime.interpreter as tflite

interpreter = tflite.Interpreter(model_path='models/efficientdet_lite0.tflite')
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
# print(input_details)
# print(output_details)
with open('models/coco_labels.txt', 'r') as f:
    labels = [line.strip() for line in f.readlines()]
if __name__ == '__main__':
    cap = None
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Camera Open Failed")
            exit()
        while True:
            ret, frame  = cap.read()

            if not ret:
                print("Frame read failed")
                break
            resize_frame = cv2.resize(frame,(320,320))
            rgb = cv2.cvtColor(resize_frame,cv2.COLOR_BGR2RGB)
            input_tensor = rgb[np.newaxis]
            # print("shape:", input_tensor.shape)
            # print("dtype:", input_tensor.dtype)
            input_index = input_details[0]['index']
            interpreter.set_tensor(input_index,input_tensor)
            start = time.perf_counter()
            interpreter.invoke()
            end = time.perf_counter()
            inference_time  = (end-start) * 1000
            print(f"Inference time: {inference_time:.2f} ms")
            boxes = interpreter.get_tensor(output_details[0]['index'])
            classes = interpreter.get_tensor(output_details[1]['index'])
            scores = interpreter.get_tensor(output_details[2]['index'])
            num_detections = interpreter.get_tensor(output_details[3]['index'])

            count  = int(num_detections[0])
            h, w = frame.shape[:2]
            for i in range(count):
                score = scores[0][i]
                if score <0.5:
                    continue
                box = boxes[0][i]
                y_min,x_min,y_max,x_max = box
                xmin_pixel = max(0, min(w - 1, int(x_min * w)))
                xmax_pixel = max(0, min(w - 1, int(x_max * w)))
                ymin_pixel = max(0, min(h - 1, int(y_min * h)))
                ymax_pixel = max(0, min(h - 1, int(y_max * h)))
                class_id = int(classes[0][i])
                label = labels[class_id]
                text = f"{label} {score:.2f}"
                cv2.putText(frame,text,(xmin_pixel, ymin_pixel),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
                cv2.rectangle(frame,(xmin_pixel,ymin_pixel), (xmax_pixel,ymax_pixel), (0,255,0),2)
            cv2.imshow("Camera",frame)
            # cv2.imshow("ROI GRAY",gray_roi)
            key = cv2.waitKey(1)
            if key == ord('q'):
                break
    except Exception as e:
        print(f"Unexpected error: {e}")        
    finally:
        print("[INFO] Releasing camera...")
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()