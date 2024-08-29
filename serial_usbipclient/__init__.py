"""definitions for serial-usbipclient interface"""
from . import version
from .usbip_client import *

PACKAGE_NAME: str = 'serial-usbipclient'

__versions__: str = version.get_version(PACKAGE_NAME)

__all__: list[str] = [
    'USBIPClient',  # manages connections USBIPD service
    'USBIP_Connection',  # a connection, via USBIPD, to a device
    'HardwareID',  # hardware ids to form connections to (pid/vid)

    # exceptions
    'USBIPError',
    'USBIPServerTimeoutError',
    'USBIPConnectionError',
    'USBIPResponseTimeoutError',
    'USBConnectionLostError',
    'USBAttachError',

]
