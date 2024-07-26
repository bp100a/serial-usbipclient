"""mock USBIP server"""

import platform
import socket
from threading import Thread, Event
from time import time, sleep
from queue import Queue
import logging


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
        self.event.clear()
        self.thread.start()
        start_time: float = time()
        while time() - start_time < 5.0:
            if self.event.is_set():
                return
            sleep(0.010)  # allow thread time to start

        raise TimeoutError(f"Timed out waiting for USBIP server to start, waited {round(time() - start_time, 2)} seconds")

    def shutdown(self):
        """shutdown the USBIP server thread"""
        if self.thread and self.event.is_set():
            print(f"[{self.thread.name}] self.event.clear()!, {time()=}")
            self.event.clear()  # -> 0, thread will exit loop if we aren't blocking on accept()
            if self.server_socket:
                if not self._is_windows:  # in linux-land, need to shut down as well
                    self.server_socket.shutdown(socket.SHUT_RDWR)
                self.server_socket.close()  # if we are waiting for accept(), should unblock

            if self.event.wait(timeout=5.0):
                self.thread.join(timeout=1.0)
                self.thread = None
                return
            print(f"[{self.thread.name}]shutdown has timed out, {self.event.is_set()=}, {time()=}")
            raise TimeoutError(f"Timed out waiting for USBIP server to acknowledge shutdown")

    def run(self):
        """standup the server, start listening"""
        self.server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.settimeout(None)  # so our accept() will block

        # configure how many clients the server can listen simultaneously
        self.server_socket.listen(2)
        self.event.set()
        self.logger.info("\nmock USBIP server started @%s:%s", self.host, self.port)
        try:
            conn, address = self.server_socket.accept()  # accept new connection
            self.logger.info(f"Client @{address} connected")
            while self.event.is_set():
                sleep(0.010)  # faux processing data

            if conn:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()  # close the connection
        except OSError as os_error:
            print(f"[{self.thread.name}]mock USBIP server exception {str(os_error)}, {time()=}")
        finally:
            self.event.set()  # indicate we are exiting
            print(f"[{self.thread.name}]mock USBIP server is exiting! {self.event.is_set()=}, {time()=}")
            self.logger.info("mock USBIP server stopped @%s:%s", self.host, self.port)
