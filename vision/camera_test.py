import cv2
from collections import deque

BRIGHT_THRESHOLD = 110
DARK_THRESHOLD = 90
INITIAL_THRESHOLD = 100
FILTER_WINDOW_SIZE = 5
CAMERA_INDEX = 0




def determine_state(brightness, previous_state):

    if previous_state is None:
        if brightness >= INITIAL_THRESHOLD:
            return "BRIGHT"
        else:
            return "DARK"

    elif brightness >= BRIGHT_THRESHOLD:
        return "BRIGHT"

    elif brightness <= DARK_THRESHOLD:
        return "DARK"

    else:
        return previous_state

def calculate_brightness(frame):
    height,width = frame.shape[:2]
    x1 = width//4
    x2 = width*3//4
    y1 = height//4
    y2 = height*3//4


    roi = frame[y1:y2, x1:x2]

    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    mean_brightness = gray_roi.mean()
    return mean_brightness

if __name__ == '__main__':
    cap = None
    brightness_buffer = deque(maxlen=FILTER_WINDOW_SIZE)
    previous_state = None
    try:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            print("Camera Open Failed")
            exit()
        while True:
            ret, frame  = cap.read()

            if not ret:
                print("Frame read failed")
                break
            mean_brightness = calculate_brightness(frame)
            brightness_buffer.append(mean_brightness)
            filtered_brightness = sum(brightness_buffer) / len(brightness_buffer)

            state = determine_state(filtered_brightness,previous_state)

            if state != previous_state:
                print(
                f"Raw: {mean_brightness:.2f} | "
                f"Filtered: {filtered_brightness:.2f} | "
                f"{previous_state} -> {state}"
                )
                previous_state = state
            

            # cv2.rectangle(frame,(x1,y1), (x2,y2), (0,255,0),2)
            cv2.putText(frame, f"State: {state} ({filtered_brightness:.1f})",(20,40), cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)

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
