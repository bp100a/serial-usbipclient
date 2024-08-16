"""test packet generation using py-datastruct"""
from dataclasses import dataclass
from time import time

from common_test_base import CommonTestBase

from serial_usbipclient.protocol.packets import (
    CMD_SUBMIT,
    OP_REP_DEV_INTERFACE,
    OP_REP_DEVLIST_HEADER,
    OP_REQ_DEVLIST,
    USBIP_RET_SUBMIT,
)
from serial_usbipclient.protocol.urb_packets import DeviceDescriptor, UrbSetupPacket
from serial_usbipclient.protocol.usb_descriptors import DescriptorType
from serial_usbipclient.protocol.usbip_defs import BasicCommands, Direction
from serial_usbipclient.protocol.usbip_protocol import (
    URBSetupRequestType,
    URBStandardDeviceRequest,
)
from serial_usbipclient.usbip_client import USB_Endpoint, USBIP_Connection, USBIPClient


class TestPacketGeneration(CommonTestBase):
    """test packet generation using py-datastruct"""

    @dataclass
    class MockUSBIP_Connection(USBIP_Connection):  # pylint: disable=invalid-name
        """mock the USBIP Connection for testing"""

        def __init__(self, **kwargs):
            """set up instance variables"""
            super().__init__(**kwargs)
            self.command: CMD_SUBMIT | None = None

        def __post__init__(self):
            """some setup"""
            super().__post_init__()
            self.endpoint.input = USB_Endpoint()

        def send_command(self, command: CMD_SUBMIT) -> int:
            """get the command"""
            self.command = command
            return 0

    def test_request_devlist(self):
        """test requesting the device list"""
        start_time = time()
        loop: int = 10000
        for _ in range(0, loop):
            req_devlist: OP_REQ_DEVLIST = OP_REQ_DEVLIST()
            request_data: bytes = req_devlist.pack()
            self.assertEqual(request_data, b'\x01\x11\x80\x05\x00\x00\x00\x00')

        elapsed_time = time() - start_time
        rate: float = elapsed_time / loop
        print(f"\n{round(rate * 1_000_000, 2)}us per iteration")

        legacy_method: bytes = OP_REQ_DEVLIST().packet()
        self.assertEqual(legacy_method, b'\x01\x11\x80\x05\x00\x00\x00\x00')
        OP_REQ_DEVLIST().unpack(io=b'\x01\x11\x80\x05\x00\x00\x00\x00')
        OP_REQ_DEVLIST().new(data=b'\x01\x11\x80\x05\x00\x00\x00\x00')

    def test_cmd_submit(self):
        """test parsing using data from specification"""
        cmd_in: bytes = bytes.fromhex('00000001'  # command
                                      '00000d06'  # sequence #
                                      '0001000f'  # device/bus id (1-15)
                                      '00000000'  # direction (USBIP_DIR_OUT)
                                      '00000001'  # endpoint
                                      '00000000'  # transfer_flags
                                      '00000040'  # transfer_buffer_length
                                      '00000000'  # start_frame (0 -> not iso transfer)
                                      'ffffffff'  # number_of_packets (0xffffffff -> not iso transfer)
                                      '00000004'  # interval
                                      '0000000000000000'  # setup
                                      # transfer_buffer
                                      'ffffffff860008a784ce5ae21237630000000000000000000000000000000000'
                                      '0000000000000000000000000000000000000000000000000000000000000000')

        submit: CMD_SUBMIT = CMD_SUBMIT.unpack(cmd_in)
        self.assertEqual(submit.command, BasicCommands.CMD_SUBMIT)
        self.assertEqual(submit.seqnum, 0xd06)
        self.assertEqual(submit.direction, Direction.USBIP_DIR_OUT)
        self.assertEqual(submit.ep, 0x1)
        self.assertEqual(submit.transfer_flags, 0x0)
        self.assertEqual(submit.start_frame, 0x0)
        self.assertEqual(submit.number_of_packets, 0xffffffff)
        self.assertEqual(submit.setup, b'\0'*8)
        self.assertEqual(submit.transfer_buffer_length, 64)  # 64 bytes
        self.assertEqual(submit.transfer_buffer_length, len(submit.transfer_buffer))

        # create a packet of bytes from arguments to verify defaults
        submit = CMD_SUBMIT(seqnum=0xd06,
                            devid=0x1000f,
                            direction=Direction.USBIP_DIR_OUT,
                            ep=1,
                            transfer_flags=0, interval=4,
                            transfer_buffer_length=len(cmd_in[-64:]),
                            transfer_buffer=cmd_in[-64:])
        self.assertEqual(submit.command, BasicCommands.CMD_SUBMIT)
        generated: bytes = submit.pack()
        self.assertEqual(cmd_in, generated)

    def test_queue_urb(self):
        """Test serialization of command to queue a URB read request"""

        usb: TestPacketGeneration.MockUSBIP_Connection = TestPacketGeneration.MockUSBIP_Connection()
        usb.endpoint.input = USB_Endpoint()
        USBIPClient.read(usb=usb, size=1024)  # generate a command to queue up a read
        # serialize the command that was generated
        usb.command.pack()

    def test_cmd_response(self):
        """test command response parsing"""
        cmd_resp: bytes = bytes.fromhex('00000003'  # command
                                        '00000d05'  # sequence #
                                        '00000000'  # devid
                                        '00000000'  # direction
                                        '00000000'  # endpoint
                                        '00000000'  # status
                                        '00000040'  # actual_length
                                        '00000000'  # start_frame (0-> not iso)
                                        'ffffffff'  # number of packets (0xffffffff -> not iso)
                                        '00000000'  # error_count
                                        '0000000000000000'  # padding
                                        # transfer_buffer
                                        'ffffffff860011a784ce5ae2123763612891b102010000040000000000000000'
                                        '0000000000000000000000000000000000000000000000000000000000000000')
        resp: USBIP_RET_SUBMIT = USBIP_RET_SUBMIT.unpack(io=cmd_resp)
        self.assertEqual(resp.command, BasicCommands.RET_SUBMIT)
        self.assertEqual(resp.seqnum, 0xd05)
        self.assertEqual(resp.direction, 0x0)
        self.assertEqual(resp.ep, 0x0)
        self.assertEqual(resp.status, 0x0)
        self.assertEqual(resp.start_frame, 0x0)
        self.assertEqual(resp.number_of_packets, -1)
        self.assertEqual(resp.error_count, 0x0)
        self.assertEqual(resp.padding, b'\0'*8)
        self.assertEqual(resp.actual_length, 64)  # 64 bytes
        self.assertEqual(resp.actual_length, len(resp.transfer_buffer))

        resp = USBIP_RET_SUBMIT()
        self.assertEqual(resp.command, BasicCommands.RET_SUBMIT)

    def test_sizing(self):
        """test sizes generated for the packets"""
        self.assertEqual(48, CMD_SUBMIT.size)
        self.assertEqual(8, OP_REQ_DEVLIST.size)
        self.assertEqual(4, OP_REP_DEV_INTERFACE.size)

        self.assertEqual(48, CMD_SUBMIT(transfer_buffer_length=0).size)
        self.assertEqual(8, OP_REQ_DEVLIST().size)
        self.assertEqual(4, OP_REP_DEV_INTERFACE().size)

        self.assertEqual(12, OP_REP_DEVLIST_HEADER.size)

    def test_urb_endianness(self):
        """test packets generated for URBs have correct (little) endianess"""
        setup: UrbSetupPacket = UrbSetupPacket(
            request_type=URBSetupRequestType.DEVICE_TO_HOST.value,
            request=URBStandardDeviceRequest.GET_DESCRIPTOR.value,
            value=DescriptorType.DEVICE_DESCRIPTOR.value << 8,
            length=DeviceDescriptor.size)

        self.assertEqual(setup.pack().hex(), '8006000100001200')
