"""mock USBIP server"""

import os
import errno
import json
import platform
import socket
from threading import Thread, Event
from time import time, sleep
from queue import Queue
import logging
from typing import Optional

from protocol.packets import (CommonHeader, OP_REP_DEVLIST_HEADER, OP_REQ_IMPORT, OP_REP_DEV_PATH, OP_REP_IMPORT,
                              HEADER_BASIC, CMD_SUBMIT, USBIP_RET_SUBMIT, OP_REP_DEV_INTERFACE)
from protocol.urb_packets import UrbSetupPacket
from usbip_defs import BasicCommands
from usb_descriptors import DescriptorType


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
        self._urb_traffic: bool = False
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
        data_path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'usbip_packets.json')
        with open(file=data_path, mode='r') as recording:
            self._protocol_responses = json.loads(recording.read())

    def shutdown(self):
        """shutdown the USBIP server thread"""
        if self.thread and self.event.is_set():
            self.logger.info("usbip-server: clear event, wait for thread to recognize exit condition")
            self.event.clear()  # -> 0, thread will exit loop if we aren't blocking on accept()
            if self.server_socket:
                if not self._is_windows:  # in linux-land, need to shut down as well
                    self.server_socket.shutdown(socket.SHUT_RDWR)
                self.server_socket.close()  # if we are waiting for accept(), should unblock

            self.logger.info("usbip-server: waiting for event to signal (0->1)")
            if self.event.wait(timeout=10.0):
                self.thread.join(timeout=1.0)
                self.thread = None
                return
            raise TimeoutError(f"Timed out waiting for USBIP server to acknowledge shutdown")

    def process_message(self, client: socket.socket, message: bytes) -> None:
        """process the message sent"""
        self.logger.info(f"{self._urb_traffic=}, {message.hex()=}")
        if self._urb_traffic:
            urb_header: HEADER_BASIC = HEADER_BASIC.unpack(message)
            if urb_header.command == BasicCommands.CMD_SUBMIT:
                cmd_submit: CMD_SUBMIT = CMD_SUBMIT.unpack(message)
                urb_setup: UrbSetupPacket = UrbSetupPacket.unpack(cmd_submit.setup)
                ret_submit: Optional[USBIP_RET_SUBMIT] = None
                self.logger.info(f"Setup flags: {str(urb_setup)}")
                if urb_setup.value == DescriptorType.DEVICE_DESCRIPTOR << 8:
                    # return descriptor for device
                    ret_submit = USBIP_RET_SUBMIT.unpack(bytes.fromhex(self._protocol_responses['URB_SETUP'][0]))
                elif urb_setup.value == DescriptorType.CONFIGURATION_DESCRIPTOR << 8:
                    ret_submit = USBIP_RET_SUBMIT.unpack(bytes.fromhex(self._protocol_responses['URB_SETUP'][1]))
                elif urb_setup.value == DescriptorType.STRING_DESCRIPTOR << 8:
                    ret_submit = USBIP_RET_SUBMIT.unpack(bytes.fromhex(self._protocol_responses['URB_SETUP'][2]))
                if ret_submit:
                    ret_submit.seqnum = cmd_submit.seqnum
                    response: bytes = ret_submit.pack()
                    self.logger.info(f"ret_submit={response.hex()}")
                    client.sendall(response)
                    return

                failure: bytes = USBIP_RET_SUBMIT(status=0, direction=0, transfer_buffer=bytes()).pack()
                client.sendall(failure)
        else:
            header: CommonHeader = CommonHeader.unpack(message)
            if header.command == BasicCommands.REQ_DEVLIST:
                # return the device list
                for output in self._protocol_responses['OP_REP_DEVLIST']:
                    data: bytes = bytes.fromhex(output)
                    client.sendall(data)
            elif header.command == BasicCommands.REQ_IMPORT:
                # return specifics for device import (find the busid we are looking for)
                req_import: OP_REQ_IMPORT = OP_REQ_IMPORT.unpack(message)
                for path in self.read_paths():
                    if path.busid == req_import.busid:
                        rep_import: OP_REP_IMPORT = OP_REP_IMPORT(status=0, path=path.path, busid=req_import.busid, busnum=path.busnum,
                                                                  devnum=path.devnum, speed=path.speed, idVendor=path.idVendor,
                                                                  idProduct=path.idProduct, bcdDevice=path.bcdDevice,
                                                                  bDeviceClass=path.bDeviceClass, bDeviceSubClass=path.bDeviceSubClass,
                                                                  bDeviceProtocol=path.bDeviceProtocol, bConfigurationValue=path.bConfigurationValue,
                                                                  bNumConfigurations=path.bNumConfigurations, bNumInterfaces=path.bNumInterfaces)
                        data: bytes = rep_import.pack()
                        client.sendall(data)
                        self._urb_traffic = True
                        return
                else:
                    # device not found, return error
                    self.logger.warning(f"busid not found: {req_import.busid.hex()}")
                    failure: CommonHeader = CommonHeader(command=BasicCommands.RET_SUBMIT, status=errno.ENODEV)
                    client.sendall(failure.pack())
                    self._urb_traffic = False

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
                self.logger.info(f"usbip-server, client @{address} connected")
                try:
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
                    self.logger.info(f"usbip-server, client @{address} disconnected: {os_error}")
                    if conn:
                        conn.shutdown(socket.SHUT_RDWR)
                        conn.close()
                        conn = None
        except OSError as os_error:
            pass
        finally:
            self.event.set()  # indicate we are exiting
            self.logger.info("mock USBIP server stopped @%s:%s", self.host, self.port)

    def read_paths(self) -> list[OP_REP_DEV_PATH]:
        """read the paths from the JSON file"""
        devlist: bytes = bytes.fromhex("".join([item for item in self._protocol_responses['OP_REP_DEVLIST']]))
        devlist_header: OP_REP_DEVLIST_HEADER = OP_REP_DEVLIST_HEADER.unpack(devlist[:OP_REP_DEVLIST_HEADER.size])
        devices: bytes = devlist[OP_REP_DEVLIST_HEADER.size:]
        paths: list[OP_REP_DEV_PATH] = []
        for device_index in range(0, devlist_header.num_exported_devices):
            path: OP_REP_DEV_PATH = OP_REP_DEV_PATH.unpack(devices)
            paths.append(path)
            devices = devices[OP_REP_DEV_PATH.size:]
            for _ in range(0, path.bNumInterfaces):
                interface: OP_REP_DEV_INTERFACE = OP_REP_DEV_INTERFACE.unpack(devices)
                path.interfaces.append(interface)
                devices = devices[OP_REP_DEV_INTERFACE.size:]

        return paths
