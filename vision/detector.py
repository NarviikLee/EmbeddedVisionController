import cv2
import numpy as np
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    from ai_edge_litert import interpreter as tflite


def load_label(label_path):
	with open(label_path, 'r') as f:
		return [line.strip() for line in f.readlines()]

def load_model(model_path):
	interpreter = tflite.Interpreter(model_path=model_path)
	interpreter.allocate_tensors()

	input_details = interpreter.get_input_details()
	output_details = interpreter.get_output_details()
	
	return interpreter, input_details,output_details


def determine_direction(center_x, frame_width, dead_zone=60):
    frame_center = frame_width // 2

    left_boundary = frame_center - dead_zone
    right_boundary = frame_center + dead_zone

    if center_x < left_boundary:
        return "LEFT"
    elif center_x > right_boundary:
        return "RIGHT"
    else:
        return "CENTER"

def preprocess_frame(frame,input_shape):
	height = input_shape[1]
	width = input_shape[2]
	resize = cv2.resize(frame,(width,height))
	rgb = cv2.cvtColor(resize,cv2.COLOR_BGR2RGB)
	input_tensor = rgb[np.newaxis]
	return input_tensor

def run_inference(interpreter, input_details, output_details, input_tensor):
	input_index = input_details[0]['index']
	interpreter.set_tensor(input_index,input_tensor)
	interpreter.invoke()
	boxes = interpreter.get_tensor(output_details[0]['index'])
	classes = interpreter.get_tensor(output_details[1]['index'])
	scores = interpreter.get_tensor(output_details[2]['index'])
	num_detections = interpreter.get_tensor(output_details[3]['index'])
	return boxes,classes,scores,num_detections

def postprocess_detections(frame,labels,boxes,classes,scores,num_detections):
	results = []
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
		center_x = (xmin_pixel + xmax_pixel) // 2
		direction = determine_direction(center_x=center_x,frame_width=w)
		text = f"{label} {score:.2f} {direction}"
		results.append({
		    "label": label,
		    "score": float(score),
		    "center_x": center_x,
		    "bbox": (xmin_pixel, ymin_pixel, xmax_pixel, ymax_pixel),
		    "direction": direction
		})
		cv2.putText(frame,text,(xmin_pixel, ymin_pixel),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
		cv2.rectangle(frame,(xmin_pixel,ymin_pixel), (xmax_pixel,ymax_pixel), (0,255,0),2)

	return frame,results
