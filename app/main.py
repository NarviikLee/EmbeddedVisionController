import cv2
from collections import deque
from vision.camera_test import calculate_brightness, determine_state
from communication.serial_comm import connect_serial, send_state, receive_packet


cap = None
ser = None
previous_state = None

brightness_buffer = deque(maxlen=5)


try:
	cap = cv2.VideoCapture(0)
	if not cap.isOpened():
		print("Camera Open Failed")
		exit()

	ser = connect_serial()
	while True:
		ret, frame = cap.read()

		if not ret:
			print("Not Connect Camera")
			break

		mean_brightness = calculate_brightness(frame)
		brightness_buffer.append(mean_brightness)
		filtered_brightness = sum(brightness_buffer) / len(brightness_buffer)
		state = determine_state(filtered_brightness,previous_state)
		
		if state != previous_state:
			sent_bytes = send_state(ser,state)
			print(
		        f"TX -> STATE:{state} | "
		        f"{sent_bytes} bytes | "
		        f"Brightness: {filtered_brightness:.1f}"
		    )
			previous_state = state
			command,payload = receive_packet(ser)
			print(f"RX <- {command}:{payload}")

		cv2.imshow("Camera", frame)

		key = cv2.waitKey(1)

		if key == ord('q'):
		    break
except Exception as e:
	print(f"{e}")

finally:
	if cap is not None:
		cap.release()

	if ser is not None:
		ser.close()
	cv2.destroyAllWindows()


