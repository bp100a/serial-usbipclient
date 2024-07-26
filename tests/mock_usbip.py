"""mock USBIP server"""

import os
import json
import platform
import socket
from threading import Thread, Event
from time import time, sleep
from queue import Queue
import logging
from typing import Optional

from protocol.packets import CommonHeader
from usbip_defs import BasicCommands


class MockUSBIP:
    """mock USBIP server"""
    def __init__(self, host: str, port: int, logger: logging.Logger):
        """set up our instance"""
        self.host: str = host
        self.port: int = port
        self.logger: logging.Logger = logger
        self.queue: Queue = Queue()
        self.server_socket: socket.socket | None = None
        self.thread: Thread = Thread(name=f'mock-usbip@{self.host}:{self.port}', target=self.run, daemon=True)
        self.event: Event = Event()
        self._is_windows: bool = platform.system() == 'Windows'
        self._protocol_responses: dict[str, list[str]] = {}
        self.setup()
        self.event.clear()
        self.thread.start()
        start_time: float = time()
        while time() - start_time < 5.0:
            if self.event.is_set():
                return
            sleep(0.010)  # allow thread time to start

        raise TimeoutError(f"Timed out waiting for USBIP server to start, waited {round(time() - start_time, 2)} seconds")

    def setup(self):
        """setup our instance"""
        data_path: str = os.path.join(os.getcwd(), 'usbip_packets.json')
        with open(file=data_path, mode='r') as recording:
            self._protocol_responses = json.loads(recording.read())

    def shutdown(self):
        """shutdown the USBIP server thread"""
        if self.thread and self.event.is_set():
            self.event.clear()  # -> 0, thread will exit loop if we aren't blocking on accept()
            if self.server_socket:
                if not self._is_windows:  # in linux-land, need to shut down as well
                    self.server_socket.shutdown(socket.SHUT_RDWR)
                self.server_socket.close()  # if we are waiting for accept(), should unblock

            if self.event.wait(timeout=5.0):
                self.thread.join(timeout=1.0)
                self.thread = None
                return
            raise TimeoutError(f"Timed out waiting for USBIP server to acknowledge shutdown")

    def process_message(self, client: socket.socket, message: bytes) -> None:
        """process the message sent"""
        header: CommonHeader = CommonHeader.unpack(message)
        if header.command == BasicCommands.REQ_DEVLIST:
            for output in self._protocol_responses['OP_REP_DEVLIST']:
                data: bytes = bytes.fromhex(output)
                client.sendall(data)

    def run(self):
        """standup the server, start listening"""
        self.server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.settimeout(None)  # so our accept() will block

        self.server_socket.listen(1)  # only allow one connection (testing)
        self.event.set()
        self.logger.info("\nmock USBIP server started @%s:%s", self.host, self.port)
        try:
            conn: Optional[socket.socket] = None
            while self.event.is_set():
                conn, address = self.server_socket.accept()  # accept new connection
                self.logger.info(f"Client @{address} connected")
                while conn and self.event.is_set():
                    message: bytes = conn.recv(1024)
                    if not message:
                        conn.shutdown(socket.SHUT_RDWR)
                        conn.close()
                        conn = None
                    else:
                        self.process_message(conn, message)

                if conn:
                    conn.shutdown(socket.SHUT_RDWR)
                    conn.close()  # close the connection
        except OSError as os_error:
            pass
        finally:
            self.event.set()  # indicate we are exiting
            self.logger.info("mock USBIP server stopped @%s:%s", self.host, self.port)
