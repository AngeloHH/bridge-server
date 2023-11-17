import queue
import secrets
import select
import socket
from threading import Thread


class TCPTunnel:
    def __init__(self, hostname: tuple or int):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.hostname = ('127.0.0.1', hostname)
        self.tunnel_client = None
        self.secret_key = secrets.token_hex(20)
        self.connections = {}
        self.jumpers = queue.Queue()
        self.recv_length = 1024
        self.hostname = self.hostname if type(hostname) == int else hostname

    def _solve_addr(self, connection: tuple or bytes):
        # If connection is a tuple, convert to address format
        if type(connection) == tuple:
            port = connection[1].to_bytes(2, byteorder='big')
            addr = bytes(map(int, connection[0].split('.')))
            return addr + port
        kwargs = dict(byteorder='big')
        port = int.from_bytes(connection[4:6], **kwargs)
        return '.'.join(map(str, connection[0:4])), port

    def _check_token(self, token: str or bytes = None) -> bool:
        # If no token is provided, send the current key to the server.
        if token is None:
            self.server_socket.send(self.secret_key.encode())
            # Receive the token verification from the server.
            token = self.server_socket.recv(self.recv_length)
        token = token.encode() if type(token) != bytes else token
        # Check if the token is the same as the secret key.
        return token == self.secret_key.encode()

    def _close_sockets(self, *args: socket.socket):
        # Helper method to gracefully close multiple
        # sockets.
        for old_socket in args:
            old_socket.shutdown(socket.SHUT_RDWR)
            old_socket.close()

    def transfer(self, client: socket.socket, tunnel: socket.socket):
        while True:
            # Use select to monitor sockets for data.
            read, write, error = select.select([client, tunnel], [], [])
            for selected in read:
                # Determine which socket is selected to send the data to the other.
                receptor = client if selected == tunnel else tunnel
                # Read data and check if the connection is closed.
                is_closed = receptor.send(selected.recv(self.recv_length)) == 0
                if is_closed: return self._close_sockets(client, tunnel)

    def assign(self):
        packet, kwargs = b'', dict(byteorder='big')
        while True:
            new_packet = self.tunnel_client.recv(self.recv_length)
            packet += new_packet
            if len(new_packet) == 0: break
            for data in range(0, len(packet), 12):
                # Extract the tunnel and client addresses from the
                # packet.
                data = packet[data:data + 12]
                tunnel = self._solve_addr(data[:6])
                client = self._solve_addr(data[6:])
                # Remove the processed packet from the data.
                packet = packet[12:]
                # Add the client and tunnel addresses to the queue
                self.jumpers.put((client, tunnel))
        self.tunnel_client = None

    def connect(self):
        while True:
            # Get connections from the queue.
            connections = self.jumpers.get()
            client, tunnel = connections
            no_client = client not in self.connections
            no_tunnel = tunnel not in self.connections
            if no_client or no_tunnel:
                self.jumpers.put((client, tunnel))
                continue
            # Get the client and tunnel sockets from the connections' dictionary.
            client = self.connections[client]
            tunnel = self.connections[tunnel]
            # Start a thread to transfer data between client and tunnel.
            Thread(target=self.transfer, args=(client, tunnel), daemon=True).start()

    def tunnel(self, token: str or bytes, port: int):
        # Establish a tunnel for forwarding data.
        packet, kwargs = b'', dict(byteorder='big')
        self.server_socket.connect(self.hostname)
        args = socket.AF_INET, socket.SOCK_STREAM
        self.secret_key = token if type(token) != bytes else token.decode()
        if not self._check_token():
            raise Exception('The selected token is invalid')
        while True:
            recv = self.server_socket.recv(self.recv_length)
            if len(recv) == 0: break
            packet += recv
            for data in range(0, len(packet), 6):
                # Extract a 6-byte packet, representing an IP address and
                # port, from the received packet.
                data = packet[data:data + 6]
                # Remove the processed data from the packet and solve the
                # address from the selected data.
                packet = packet[6:]
                addr = self._solve_addr(data)
                # Check if the address is a tunnel connection
                if addr in self.connections:
                    continue
                # Create client and server sockets for forwarding.
                server = socket.socket(*args)
                client = socket.socket(*args)
                client.connect(self.hostname)
                # Add the client socket to the connections' dictionary.
                self.connections[client.getsockname()] = client
                server.connect(('127.0.0.1', port))
                addr = self._solve_addr(client.getsockname())
                # Send the client address and tunnel address to the server and start a
                # thread for transferring data between client and server.
                self.server_socket.send(addr + data)
                Thread(target=self.transfer, args=(client, server), daemon=True).start()

    def server(self):
        # Start the server to accept client connections.
        self.server_socket.bind(self.hostname)
        self.server_socket.listen()
        Thread(target=self.connect, daemon=True).start()
        while True:
            # Accept client connections and start transfer threads.
            client, addr = self.server_socket.accept()
            if self.tunnel_client is not None:
                self.connections[addr] = client
                # Notify the tunnel of the newly connected client by
                # sending its address.
                addr = self._solve_addr(addr)
                self.tunnel_client.send(addr)
                continue
            if self._check_token(client.recv(self.recv_length)):
                self.tunnel_client = client
                self.tunnel_client.send(self.secret_key.encode())
                Thread(target=self.assign, daemon=True).start()
            else: client.close()
