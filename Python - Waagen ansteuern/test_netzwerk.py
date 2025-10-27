import socket
import time

HOST = "10.0.18.2"   # IP address of Processing laptop
PORT = 5005             # same port as in Processing

def send_message(msg):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall((msg + "\n").encode())

while True:
    user_input = input("Press Enter to send 'clicked', or type 'quit' to exit: ")
    if user_input == "quit":
        break
    send_message("clicked")
    print("Sent 'clicked' to Processing.")
