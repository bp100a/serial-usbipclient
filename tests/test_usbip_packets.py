from unittest import TestCase

import usbip_protocol


class TestUSBIPPackets(TestCase):
    """test formatting strings for the USBIP protocol packets"""
    def test_usbip_protocol(self):
        """test the packet formatting"""
        descriptors: list[tuple[callable, str, list[str]]] = [
            (usbip_protocol.UrbSetupPacket, '<BBHHH', ['request_type',
                                                       'request',
                                                       'value',
                                                       'index',
                                                       'length']),
            (usbip_protocol.OP_REP_DEVLIST_HEADER, '!I', ['number_exported_devices']),
            (usbip_protocol.OP_REP_DEV_PATH, '!>256s32sIIIHHHBBBBBB', ['path',
                                                                       'busid',
                                                                       'busnum',
                                                                       'devnum',
                                                                       'speed',
                                                                       'idVendor',
                                                                       'idProduct',
                                                                       'bcdDevice',
                                                                       'bDeviceClass',
                                                                       'bDeviceSubClass',
                                                                       'bDeviceProtocol',
                                                                       'bConfigurationValue',
                                                                       'bNumConfigurations',
                                                                       'bNumInterfaces']),
            (usbip_protocol.OP_REP_DEV_INTERFACE, '!BBBB', ['bInterfaceClass',
                                                            'bInterfaceSubClass',
                                                            'bInterfaceProtocol',
                                                            '_alignment']),
            (usbip_protocol.OP_REQ_IMPORT, '!32s', ['busid']),
            (usbip_protocol.OP_REP_IMPORT, '!256s32siiihhHBBBBBB', ['path',
                                                                    'busid',
                                                                    'busnum',
                                                                    'devnum',
                                                                    'speed',
                                                                    'idVendor',
                                                                    'idProduct',
                                                                    'bcdDevice',
                                                                    'bDeviceClass',
                                                                    'bDeviceSubClass',
                                                                    'bDeviceProtocol',
                                                                    'bConfigurationValue',
                                                                    'bNumConfigurations',
                                                                    'bNumInterfaces']),
            (usbip_protocol.HEADER_BASIC, '!>iiiii', ['command', 'seqnum',
                                                      'devid', 'direction', 'ep']),
            (usbip_protocol.CMD_SUBMIT, '!iiiIi8sss', ['transfer_flags',
                                                       'transfer_buffer_length',
                                                       'start_frame',
                                                       'number_of_packets',
                                                       'interval',
                                                       'setup',
                                                       'transfer_buffer',
                                                       'iso_packet_descriptor']),
            (usbip_protocol.RET_SUBMIT_PREFIX, '!iiiii8s', ['status',
                                                            'actual_length',
                                                            'start_frame',
                                                            'number_of_packets',
                                                            'error_count',
                                                            'padding']),
            (usbip_protocol.RET_SUBMIT_DATA, '!ss', ['transfer_buffer', 'iso_packet_descriptor']),
        ]

        errors: list[str] = []
        for packet_class, fmt, args in descriptors:
            packet = packet_class()
            if packet.fmt != fmt:
                errors.append(f"{packet.__class__.__name__}, {packet.fmt} != {fmt}")
            if packet.args != args:
                errors.append(f"{packet.__class__.__name__}, {packet.args} != {args}")

        self.assertFalse(errors)  # display any discrepancies

    def test_packet_hierarchy(self):
        """test packet construction"""
        errors: list[str] = []
        fmt: str = '!HHII'
        args: list[str] = ['usbip_version', 'command', 'status', 'number_exported_devices']
        packet = usbip_protocol.OP_REP_DEVLIST_HEADER()
        if packet.fmt != fmt:
            errors.append(f"{packet.__class__.__name__}, {packet.fmt} != {fmt}")
        if packet.args != args:
            errors.append(f"{packet.__class__.__name__}, {packet.args} != {args}")

        self.assertFalse(errors)
