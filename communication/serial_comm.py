import serial
from communication.protocol import create_packet,parse_packet

PORT = "/dev/ttyACM0"
# PORT = "/dev/ttyAMA0"
BAUDRATE = 115200
TIMEOUT = 1
ser = None

def connect_serial():
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        timeout=TIMEOUT
    )
    return ser

def send_state(ser, state):
	packet = create_packet("STATE",state)
	sent_bytes = ser.write(packet)
	return sent_bytes

def receive_packet(ser):
	response = ser.readline()
	if not response:
		raise TimeoutError("Receive Time Over")
	command, payload = parse_packet(response)

	return command, payload

def send_track(ser, direction):
	packet = create_packet("TRACK",direction)
	sent_bytes = ser.write(packet)
	return sent_bytes



if __name__ == '__main__':	
	try:
		ser = connect_serial()
		sent_bytes = send_state(ser, "BRIGHT")
		print(sent_bytes)
		command, payload = receive_packet(ser)
		print(f"{command} : {payload}")
		print("Serial connected")
	except Exception as e:
		print(f"{e} 에러가 발생했습니다.")

	finally:
		if ser is not None:
			ser.close()