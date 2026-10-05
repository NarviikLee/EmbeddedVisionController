
# buffer = bytearray()

def create_packet(command,payload):

	if not isinstance(command,str):
		raise TypeError("command must be a string")

	if not isinstance(payload,str):
		raise TypeError("payload must be a string")

	if not command:
		raise ValueError("command cannot be empty")
	if not payload:
		raise ValueError("payload cannot be empty")

	reserved_chars = (":","\n")

	if any(char in command or char in payload for char in reserved_chars):
		raise ValueError("Reserved character is not allowed")

	message = f"{command}:{payload}\n"
	return message.encode('utf-8')


def parse_packet(packet):
	message = packet.decode('utf-8')
	
	if not message.endswith("\n"):
		raise ValueError("Packet must end with newline")
	
	message = message.rstrip("\n")
	
	if message.count(":") != 1:
		raise ValueError("Invalid packet format")
	
	command, payload = message.split(":")

	if command == "" or payload == "":
		raise ValueError("message cannot be empty")
	return command, payload


if __name__ == "__main__":
    chunks = [
        b"STATE:BRIGHT\n",
        b"INVALID\n",
        b"TRACK:LEFT\n",
    ]

    buffer = bytearray()

    for chunk in chunks:
        buffer.extend(chunk)

        while b"\n" in buffer:
            index = buffer.find(b"\n")
            packet = buffer[:index + 1]
            buffer = buffer[index + 1:]

            try:
                command, payload = parse_packet(packet)
                print(command, payload)

            except UnicodeDecodeError as e:
                print(f"Decode error: {e}")

            except ValueError as e:
                print(f"Protocol error: {e}")