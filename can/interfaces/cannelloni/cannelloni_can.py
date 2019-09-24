# coding: utf-8

"""
Interface for WiFi compatible interfaces with cannelloni can.

.. note::

"""

from __future__ import absolute_import

import logging
import sys
import enum
import struct
import binascii
import select
import time
import threading
import queue


from can import BusABC, Message

logger = logging.getLogger(__name__)    # TODO: only one logger
LOG = logging.getLogger(__name__)

try:        # TODO: useless because always available with python ?
    import socket
except ImportError:
    logger.warning("You won't be able to use the cannelloni can backend without "
                   "the socket module installed!")
    socket = None
    import socket


class OpCodes(enum.Enum):
    """
    Op Codes for the Cannelloni Data Packet.
    """
    DATA = 0
    ACK = 1
    NACK = 2


class CannelloniDataPacket(object):
    """
    Header for one Cannelloni UDP Packet
    """
    def __init__(self):
        self.version = 0
        self.op_code = 0
        self.seq_no = 0
        self.count = 0


class MyTimer(object):
    def __init__(self, t):
        self.__event = threading.Event()
        self.__interval = t
        self.__timer = threading.Timer(self.__interval, self.__set_event)

    def run(self):
        self.__timer.start()

    def reset(self):
        self.__timer.cancel()
        self.__timer = threading.Timer(self.__interval, self.__set_event)
        self.__timer.start()

    def __set_event(self):
        self.__event.set()

    def clear(self):
        self.__event.clear()

    def is_present(self):
        return self.__event.is_set()


class MyThread(threading.Thread):
    def __init__(self, func, arg=None):
        threading.Thread.__init__(self)
        self.__running = threading.Event()
        self.__running.set()
        self.__func = func
        self.__arg = arg

    def run(self):
        while self.__running.is_set():
            self.__func()

    def cancel(self):
        self.__running.clear()


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

    def __init__(self, ap_address, sleep_after_open=_SLEEP_AFTER_SOCKET_OPEN, do_open=True, disable_rx = False, **kwargs):
        """
        :param tuple ap_address:
            ip_address and port from the WiFi Access Point
            Must not be empty.
        :param str btr:
            BTR register value to set custom can speed
        :param float sleep_after_open:
            Time to wait in seconds after opening socket connection
        """

        if not ap_address:  # if None or empty
            raise TypeError("Must specify IP Address and Port from the Access Point.")

        self.__ap_address = ap_address
        self.__socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__socket.bind(('0.0.0.0', 3333))
        self.__disable_rx = disable_rx
        self._udp_rx_packet_buf = bytearray()
        self.tx_buffer = queue.Queue()
        self.rx_buffer = queue.Queue()    # TODO: queue or deque(maybe faster?)

        # TODO: set bit rate

        if do_open:
            self.open()
        time.sleep(sleep_after_open)

        if not self.__disable_rx:
            self.__rcv_internal_thread = MyThread(func=self._recv_internal)
            self.__rcv_internal_thread.start()

        self.timer = MyTimer(0.03)
        self.timer.run()

        self.__snd_internal_thread = MyThread(func=self._send_internal)
        self.__snd_internal_thread.start()

        super(CannelloniBus, self).__init__(ap_address, **kwargs)

    def write(self, string):        # TODO: (needed?)
        self.__socket.sendto(binascii.hexlify(string), self.__ap_address)

    def open(self):
        """
        Sends an init Message peer UDP to the Access Point.
        """
        init_message = bytes("Cannelloni", "utf-8")
        self.__socket.sendto(init_message, self.__ap_address)  # send init message to the Access Point

    def close(self):        # TODO: adapt on socket
        pass

    def recv(self, timeout=None):
        """Block waiting for a message from the Bus.

        :type timeout: float or None
        :param timeout:
            seconds to wait for a message or None to wait indefinitely

        :rtype: can.Message or None
        :return:
            None on timeout or a :class:`can.Message` object.
        :raises can.CanError:
            if an error occurred while reading
        """
        start = time.time()
        time_left = timeout

        while True:
            msg, already_filtered = self.rx_buffer.get(block=True, timeout=timeout)

            # return it, if it matches
            if msg and (already_filtered or self._matches_filters(msg)):
                LOG.log(self.RECV_LOGGING_LEVEL, 'Received: %s', msg)
                return msg

            # if not, and timeout is None, try indefinitely
            elif timeout is None:
                continue

            # try next one only if there still is time, and with
            # reduced timeout
            else:

                time_left = timeout - (time.time() - start)

                if time_left > 0:
                    continue
                else:
                    return None

    def _recv_internal(self, timeout=None):
        self.__socket.setblocking(False)

        can_id = None
        remote = False
        extended = False
        error_frame = False
        data = []

        ready = select.select([self.__socket], [], [], timeout)
        if ready[0]:
            try:
                self._udp_rx_packet_buf, server = self.__socket.recvfrom(self.CANNELLONI_UDP_RX_PACKET_BUF_LEN)
            except OSError:
                return None, False
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
            print("Recieved wrong cannelloni frame version", file=sys.stderr)
            return None, False

        if rcv_hdr.op_code != OpCodes.DATA.value:
            print("Received wrong op code", file=sys.stderr)
            return None, False

        received_frames_count = rcv_hdr.count
        if received_frames_count == 0:
            print("No frame received", file=sys.stderr)
            return None, False

        pos_left = 5
        pos_right = 9
        for i in range(0, received_frames_count):
            can_id = struct.unpack("I", self._udp_rx_packet_buf[pos_left:pos_right])
            can_id = socket.ntohl(can_id[0])

            flags = self.CAN_MSG_FLAG_NONE
            if can_id & self.CAN_ERR_FLAG:
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

            pos_left = pos_right
            pos_right = pos_right + 1
            data_length_code = struct.unpack("B", self._udp_rx_packet_buf[pos_left:pos_right])
            data_length_code = data_length_code[0]

            pos_left = pos_right
            pos_right = pos_left + data_length_code
            if (flags & self.CAN_MSG_FLAG_RTR) == 0:
                data = bytearray(self._udp_rx_packet_buf[pos_left:pos_right])

            if can_id is not None:
                message = Message(arbitration_id=can_id,
                                  is_extended_id=extended,
                                  timestamp=time.time(),  # TODO: maybe use timestamp from ESP32
                                  is_remote_frame=remote,
                                  is_error_frame=error_frame,
                                  dlc=data_length_code,
                                  data=data)
                self.rx_buffer.put(item=(message, False))
            else:
                self.rx_buffer.put(item=(None, False))

            pos_left = pos_right
            pos_right = pos_right + 4

    def _send_internal(self):
        self.__socket.setblocking(False)
        can_messages = list()

        queue_size = self.tx_buffer.qsize()
        if queue_size >= 20 or (self.timer.is_present() and queue_size > 0):
            while queue_size > 0:
                can_messages.append(self.tx_buffer.get())
                queue_size = queue_size - 1
            udp_tx_packet_buf, packet_size = self.__cannelloni_build_packet(can_messages, len(can_messages))

            if packet_size < 0:
                print("cannelloni build packet failed", file=sys.stderr)
            ready = select.select([], [self.__socket], [], None)
            if ready[1]:
                send = self.__socket.sendto(udp_tx_packet_buf, self.__ap_address)  # TODO: try catch?
                if send < 0:
                    print("sento error: %s" % send, file=sys.stderr)
            can_messages.clear()
            self.timer.clear()
            self.timer.reset()

    def send(self, msg, timeout=None):
        time.sleep(0.00033)
        self.tx_buffer.put(msg)

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

    def get_socket(self):
        return self.__socket

    def shutdown(self):
        self.__snd_internal_thread.cancel()
        if not self.__disable_rx:
            self.__rcv_internal_thread.cancel()
        #self.__rcv_internal_thread.join()
        #self.__snd_internal_thread.join()

        self.__socket.close()
        self.close()
