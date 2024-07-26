"""mock USBIP server"""

import socket
from threading import Thread, Event
from time import time, sleep
from queue import Queue
import logging


logger = logging.getLogger(__name__)


class MockUSBIP:
    """mock USBIP server"""
    def __init__(self, host: str, port: int):
        """set up our instance"""
        self.host: str = host
        self.port: int = port
        self.queue: Queue = Queue()
        self.server_socket: socket.socket | None = None
        self.thread: Thread = Thread(name=f'mock-usbip@{self.host}:{self.port}', target=self.run)
        self.event: Event = Event()
        self.thread.start()
        start_time: float = time()
        while time() - start_time < 5.0:
            if self.event.is_set():
                return
            sleep(0.010)  # allow thread time to start

        raise TimeoutError(f"Timed out waiting for USBIP server to start, waited {round(time() - start_time, 2)} seconds")

    def shutdown(self):
        """shutdown the USBIP server thread"""
        if self.thread:
            self.event.clear()  # -> 0, thread will exit loop
            if self.server_socket:
                self.server_socket.close()  # if we are waiting for accept(), should unblock

            start_time: float = time()
            while time() - start_time < 5.0:
                if self.event.is_set():
                    self.thread.join(timeout=5.0)
                    self.thread = None
                    return
            raise TimeoutError(f"Timed out waiting for USBIP server to acknowledge shutdown, waited {round(time() - start_time, 2)} seconds")

    def run(self):
        """standup the server, start listening"""
        self.server_socket = socket.socket()
        self.server_socket.bind((self.host, self.port))

        # configure how many clients the server can listen simultaneously
        self.server_socket.listen(2)
        self.event.set()
        try:
            conn, address = self.server_socket.accept()  # accept new connection
            logger.info(f"Client @{address} connected")
            while self.event.is_set():
                sleep(0.010)  # faux processing data

            if conn:
                conn.close()  # close the connection
        finally:
            self.event.set()  # indicate we are exiting
