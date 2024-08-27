"""definitions for serial-usbipclient interface"""
from . import version
from .usbip_client import *

__versions__: str = version.__version__

__all__: list[str] = [
    'USBIPClient',  # manages connections USBIPD service
    'USBIP_Connection',  # a connection, via USBIPD, to a device
    'HardwareID'  # hardware ids to form connections to (pid/vid)
]
