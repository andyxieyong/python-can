# coding: utf-8

"""
Interface for WiFi compatible interfaces (win32/linux).

.. note::

"""

from __future__ import absolute_import

import time
import logging
import sys
import enum
import struct
import binascii
import select

from can import BusABC, Message

logger = logging.getLogger(__name__)

import socket
try:        # TODO: useless because always available with python ?
    import websocket
except ImportError:
    logger.warning("You won't be able to use the cannelloni can backend without "
                   "the socket module installed!")
    socket = None
    import websocket


class OpCodes(enum.Enum):
    """
    Op Codes for the Cannelloni Data Packet.
    """
    DATA = 0
    ACK = 1
    NACK = 2


class CannelloniDataPacket(object):
    def __init__(self):
        self.version = 0
        self.op_code = 0
        self.seq_no = 0
        self.count = 0


import threading


class MyTimer(threading.Timer):
    def __init__(self, t):
        threading.Thread.__init__(self)
        self.__event = threading.Event()
        self.__stop_event = threading.Event()
        self.__intervall = t

    def run(self):
        while not self.__stop_event.wait(self.__intervall):
            self.__event.set()

    def clear(self):
        self.__event.clear()

    def is_present(self):
        return self.__event.is_set()

    def cancel(self):
        self.__stop_event.set()


class CannelloniBus(BusABC):
    """
    cannelloni interface (WiFi)
    """

    _SLEEP_AFTER_SOCKET_OPEN = 1  # in seconds

    CANNELLONI_UDP_RX_PACKET_BUF_LEN = 1600  # Defines the size of the Receiving buffer
    CANNELLONI_DATA_PACKET_BASE_SIZE = 5  # Defines the Base size of an Cannelloni Data Packet
    CANNELLONI_FRAME_VERSION = 2  # Defines the used Cannelloni Frame Version

    CAN_EFF_FLAG = 0x80000000  # Flag for Extended Frame Format (29bit arbitration-ID)
    CAN_RTR_FLAG = 0x40000000  # Flag for Remote Transmit Request frame
    CAN_ERR_FLAG = 0x20000000  # Flag for Error Frame

    CAN_SFF_MASK = 0x000007FF  # Mask for the Standard Frame Format
    CAN_EFF_MASK = 0x1FFFFFFF  # Mask for the Extended Frame Format
    CAN_ERR_MASK = 0x1FFFFFFF  # Mask for the Error Frame

    CAN_MSG_FLAG_NONE = 0x00  # No message flags (Standard Frame Format)
    CAN_MSG_FLAG_EXTD = 0x01  # Extended Frame Format (29bit arbitration-ID)
    CAN_MSG_FLAG_RTR = 0x02  # Message is a Remote Transmit Request
    CAN_MSG_FLAG_SS = 0x04  # Transmit as a Single Shot Transmission
    CAN_MSG_FLAG_SELF = 0x08  # Transmit as a Self Reception Request
    CAN_MSG_FLAG_DLC_NON_COMP = 0x10  # Message's Data length code is larger than 8. Will break compliance with CAN2.0B

    __seq_no = 0x0

    def __init__(self, ip_address_ap, sleep_after_open=_SLEEP_AFTER_SOCKET_OPEN, **kwargs):
        """
        :param tuple ip_address_ap:
            ip_address and port from the WiFi Access Point
            Must not be empty.
        :param str btr:
            BTR register value to set custom can speed
        :param float sleep_after_open:
            Time to wait in seconds after opening socket connection
        """

        if not ip_address_ap:  # if None or empty
            raise TypeError("Must specify IP Address and Port from the Access Point.")

        self.__ap_address = ip_address_ap
        self.__ws = websocket.WebSocket()
        self.__ws.connect(url="ws://" + str(self.__ap_address[0]) + ":" + str(self.__ap_address[1]) + "/")

        self._udp_rx_packet_buf = bytearray()
        self.tx_buffer = list()
        self.frame_count = 0

        # TODO: set bit rate

        self.open()
        time.sleep(sleep_after_open)
        self.timer = MyTimer(0.0003)
        self.timer.start()
        super(CannelloniBus, self).__init__(ip_address_ap, **kwargs)

    def write(self, string):        # TODO: (needed?)
        pass

    def open(self):
        """
        Sends an init Message peer UDP to the Access Point.
        """
        #init_message = bytes("Cannelloni", "utf-8")
        #self.__socket.sendto(init_message, self.__ap_address)  # send init message to the Access Point

    def close(self):        # TODO: adapt on socket
        pass

    def _recv_internal(self, timeout):
        self.__ws.setblocking(False)

        can_id = None
        remote = False
        extended = False
        error_frame = False
        data = []

        ready = select.select([self.__ws], [], [], timeout)
        if ready[0]:
            self._udp_rx_packet_buf = self.__ws.recv()
        else:
            return None, False

        rcv_hdr = CannelloniDataPacket()
        (rcv_hdr.version, rcv_hdr.op_code, rcv_hdr.seq_no) = struct.unpack("BBB", self._udp_rx_packet_buf[0:3])
        rcv_hdr.count = struct.unpack("H", self._udp_rx_packet_buf[3:5])

        rcv_hdr.count = socket.ntohs(rcv_hdr.count[0])

        rcv_len = len(self._udp_rx_packet_buf)
        if rcv_len < self.CANNELLONI_DATA_PACKET_BASE_SIZE:
            print("Did not receive enough data", file=sys.stderr)
            return None, False

        if rcv_hdr.version != self.CANNELLONI_FRAME_VERSION:
            print("Recieved wrong cannelloni frame verion", file=sys.stderr)
            return None, False

        if rcv_hdr.op_code != OpCodes.DATA.value:
            print("Received wrong op code", file=sys.stderr)
            return None, False

        received_frames_count = rcv_hdr.count
        if received_frames_count == 0:
            print("No frame received", file=sys.stderr)
            return None, False

        for i in range(0, received_frames_count):    # TODO: use multiple frames
            can_id = struct.unpack("I", self._udp_rx_packet_buf[5:9])
            can_id = socket.ntohl(can_id[0])

            flags = self.CAN_MSG_FLAG_NONE
            if can_id & self.CAN_ERR_FLAG:  # TODO: is there something more to do ?
                error_frame = True

            if can_id & self.CAN_EFF_FLAG:
                flags = flags | self.CAN_MSG_FLAG_EXTD
                extended = True

            if can_id & self.CAN_RTR_FLAG:
                flags = flags | self.CAN_MSG_FLAG_RTR
                remote = True

            if flags & self.CAN_MSG_FLAG_EXTD:
                can_id = can_id & self.CAN_EFF_MASK
            else:
                can_id = can_id & self.CAN_SFF_MASK

            data_length_code = struct.unpack("B", self._udp_rx_packet_buf[9:10])
            data_length_code = data_length_code[0]

            if (flags & self.CAN_MSG_FLAG_RTR) == 0:
                data = bytearray(self._udp_rx_packet_buf[10:(10 + data_length_code)])

            if can_id is not None:
                message = Message(arbitration_id=can_id,
                                  is_extended_id=extended,
                                  timestamp=time.time(),  # Better than nothing... TODO: maybe use timestamp from ESP32
                                  is_remote_frame=remote,
                                  is_error_frame=error_frame,
                                  dlc=data_length_code,
                                  data=data)
                return message, False
        return None, False

    # def send(self, msg, timeout=None):
    #     """
    #     Builds a cannelloni packet and send the given CAN Messages peer UDP.
    #
    #     :param msg: CAN Message
    #     :type msg: can.Message()
    #     :param timeout: Defines the socket timeout
    #     :type timeout: int
    #     """
    #     self.__socket.settimeout(timeout)   # TODO: Wait on what?
    #
    #     udp_tx_packet_buf, packet_size = self.__cannelloni_build_packet(msg, 1)  # TODO: multiple frames
    #     if packet_size < 0:
    #         print("cannelloni build packet failed", file=sys.stderr)
    #
    #     send = self.__socket.sendto(udp_tx_packet_buf, self.__ap_address)  # TODO: try catch?
    #     if send < 0:
    #         print("sento error: %s" % send, file=sys.stderr)

    def send_internal(self):
        udp_tx_packet_buf, packet_size = self.__cannelloni_build_packet(self.tx_buffer, self.frame_count)  # TODO: multiple frames

        if packet_size < 0:
            print("cannelloni build packet failed", file=sys.stderr)
        udp_tx_packet_buf = bytearray(udp_tx_packet_buf)
        send = self.__ws.send(udp_tx_packet_buf)  # TODO: try catch?
        if send < 0:
            print("sento error: %s" % send, file=sys.stderr)
        self.tx_buffer.clear()

    def send(self, msg, timeout=None):
        self.tx_buffer.append(msg)
        self.frame_count = self.frame_count + 1
        if self.timer.is_present() or len(self.tx_buffer) >= 6:
            self.send_internal()
            self.frame_count = 0
            self.timer.clear()

    def shutdown(self):
        self.close()
        self.__ws.close()

    def __cannelloni_build_packet(self, can_msg, frame_count):
        """
        Gets a defined number of CAN messages and builds an cannelloni packet.

        :param can_msg: CAN messages
        :type can_msg: [int]
        :param frame_count: number of CAN messages in can_msg
        :type frame_count: int

        :return udp_tx_packet_buf: cannelloni packet for transmitting peer udp
        :rtype udp_tx_packet_buf: bytes
        :return packet_size: size of the udp_tx_packet_buf
        :rtype packet_size: int
        """

        snd_hdr = CannelloniDataPacket()
        snd_hdr.version = self.CANNELLONI_FRAME_VERSION
        snd_hdr.op_code = OpCodes.DATA.value
        snd_hdr.seq_no = self.__seq_no
        snd_hdr.count = 0
        snd_hdr.count = socket.htons(frame_count)

        self.__seq_no = self.__seq_no + 1
        if self.__seq_no > 0xFF:
            self.__seq_no = 0

        udp_tx_packet_buf = struct.pack('BBB', snd_hdr.version, snd_hdr.op_code, 0xff)
        udp_tx_packet_buf = udp_tx_packet_buf + struct.pack('H', snd_hdr.count)

        for i in range(0, frame_count):
            can_id = can_msg[i].arbitration_id
            if can_msg[i].is_extended_id:
                can_id = can_id | self.CAN_EFF_FLAG
            if can_msg[i].is_remote_frame:
                can_id = can_id | self.CAN_RTR_FLAG

            can_id = socket.htonl(can_id)

            udp_tx_packet_buf = udp_tx_packet_buf + struct.pack("I", can_id)
            udp_tx_packet_buf = udp_tx_packet_buf + struct.pack("B", can_msg[i].dlc)

            if not can_msg[i].is_remote_frame:
                for n in range(0, can_msg[i].dlc):
                    udp_tx_packet_buf = udp_tx_packet_buf + struct.pack("B", can_msg[i].data[n])

        packet_size = len(udp_tx_packet_buf)
        return udp_tx_packet_buf, packet_size
