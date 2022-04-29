import select
import socket
from _thread import start_new_thread


def start_socket(host, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()
    return server


def connect_to(host, port):
    client = socket.socket()
    client.connect((host, port))
    return client


class Bridge:
    def __init__(self):
        # Set default buffer size and status for server.
        self.ctrl_status = True
        self.buffer_size = 4096

    # Select which side is sending information and send it to the other.
    def recv_data(self, sender, receptor):
        while True:
            read, write, error = select.select([sender, receptor], [], [])
            data = read[0].recv(self.buffer_size)
            print(data)
            # Check if the connection is still standing.
            if len(data) == 0:
                break
            # Send the information to the other side.
            receptor.sendall(data) if read[0] == sender else sender.sendall(data)
        print("Socket disconnected")

    # Check if controller disconnected.
    def check_status(self, server):
        print("Checking controller status...")
        while self.ctrl_status:
            self.ctrl_status = False if len(server.recv(4096)) else None
        print("Controller closed!")

    # This is the function of the bridge. All users must connect to it to be redirected.
    # This server will have two types of user. The first will be those who will make use
    # of the service. The information of the first group will be processed by a controller
    # and sent to one of the other group. Each connection will have a receiver.
    def start_server(self, host, bridge):
        # Create the main server and the bridge controller.
        main_server = start_socket(host[0], host[1])
        bridge_server = start_socket(bridge[0], bridge[1])
        print("Waiting for controller connection on port {}".format(bridge[1]))
        controller, addr = bridge_server.accept()
        print("Controller starter on {}:{}".format(addr[0], addr[1]))

        # Start the inspection process.
        server = main_server.getsockname()
        print("Starting server at {}:{}".format(server[0], server[1]))
        start_new_thread(self.check_status, (controller,))

        while True:
            # Accept new connections and check controller status.
            client, addr = main_server.accept()
            print("New connection from {}:{}".format(addr[0], addr[1]))
            if not self.ctrl_status:
                break
            # Calls a new connection and starts a transmission thread.
            controller.sendall(b"new-thread")
            receptor, addr = bridge_server.accept()
            print("New pipe from {}:{}".format(addr[0], addr[1]))
            start_new_thread(self.recv_data, (client, receptor,))
        print("Server closed")

    # This is the bridge client function. their job is to process the connection
    # of the bridge to the other site that is selected.
    def start_client(self, forward, host):
        # Start controller to create new connections
        controller = connect_to(host[0], host[1])
        while True:
            # Receive the data and check the status of the server.
            data = controller.recv(self.buffer_size)
            print(data)
            if len(data) == 0:
                break
            # Establishes a new connection between the bridge and the service
            bridge = connect_to(host[0], host[1])
            server = connect_to(forward[0], forward[1])
            start_new_thread(self.recv_data, (bridge, server))
        print("Connection closed")
