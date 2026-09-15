#!/usr/bin/python3
"""Private TCP relay inside the Bridge network namespace."""
import select
import socket
import socketserver

TARGET = ("172.30.241.1", 18001)


class Relay(socketserver.BaseRequestHandler):
    def handle(self):
        upstream = socket.create_connection(TARGET, timeout=10)
        try:
            sockets = [self.request, upstream]
            while True:
                readable, _, _ = select.select(sockets, [], [], 60)
                if not readable:
                    continue
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (upstream if source is self.request else self.request).sendall(data)
        finally:
            upstream.close()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("127.0.0.1", 18000), Relay) as server:
        server.serve_forever()
