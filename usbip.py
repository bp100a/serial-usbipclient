"""USBIP main entry point"""

from usbip_defs import DEFAULT_PORT


class USBIPHost:
    """host for a USBIP connection"""
    def __init__(self, host: str, port: int = DEFAULT_PORT):
        """"set up local variables"""
        self._host: str = host
        self._port: int = port


class USBIPManager:
    """manages all USBIP connections"""
    def __init__(self):
        """setup local variables for manager"""
        self._hosts: list[USBIPHost] = []
