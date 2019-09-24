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
from can.bus import BusState
from .cannelloni import Cannelloni
from .basic import *

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


class CannelloniDataPacket(object):
    """
    Header for one Cannelloni UDP Packet
    """
    def __init__(self):
        self.version = 0
        self.op_code = 0
        self.seq_no = 0
        self.count = 0


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



cannelloni_bitrates = {
    1000000: CANNELLONI_BAUD_1M,   # 1 MBit/s
    800000: CANNELLONI_BAUD_800K,  # 800 kBit/s
    500000: CANNELLONI_BAUD_500K,  # 500 kBit/s
    250000: CANNELLONI_BAUD_250K,  # 250 kBit/s
    125000: CANNELLONI_BAUD_125K,  # 125 kBit/s
    100000: CANNELLONI_BAUD_100K,  # 100 kBit/s
    50000: CANNELLONI_BAUD_50K,    # 50 kBit/s
    25000: CANNELLONI_BAUD_25K     # 25 kBit/s
}


class CannelloniBus(BusABC):
    """
    cannelloni interface (WiFi)
    """

    _SLEEP_AFTER_SOCKET_OPEN = 1  # in seconds

    CANNELLONI_UDP_RX_PACKET_BUF_LEN = 1600  # Defines the size of the Receiving buffer
    CANNELLONI_DATA_PACKET_BASE_SIZE = 5  # Defines the Base size of an Cannelloni Data Packet
    CANNELLONI_FRAME_VERSION = 2  # Defines the used Cannelloni Frame Version


    ACCEPTANCE_CODE_ALL = 0
    ACCEPTANCE_MASK_ALL = 0xFFFFFFFF

    __SLEEP_AFTER_SOCKET_OPEN = 1  # waiting time in seconds
    __seq_no = 0x0  # first Cannelloni Data Packet sequence number (last sequence number is 0xff)

    __seq_no = 0x0

    def __init__(self, ap_address, state=BusState.ACTIVE, bitrate=500000, can_mode=CANNELLONI_CAN_MODE_NORMAL,
                 filter=False, is_extended=False, start_id=0x0, end_id=0x7FF,
                 sleep_after_open=__SLEEP_AFTER_SOCKET_OPEN, do_open=True, disable_rx=False, **kwargs):
        """
        :param tuple ap_address:
            ip_address and port of the WiFi Access Point
            Must not be empty.
        :param bus.BusState state:
            Bus state of the Controller. Default is ACTIVE
        :param int bitrate:
            Bit rate in bit/s. Default is 500000 bit/s
        :param bool filter:
            Filter CAN Messages (arbitration ID). True := filter messages, False := no Message filtering
        :param bool is_extended:
            Extended arbitration ID.
        :param int start_id:
            Specifies the arbitration ID from which to filter.
            default: 0x0
        :param int end_id:
            Specifies the arbitration ID up to which to filter.
            default: 0x7FF (standard frame format)
        :param float sleep_after_open:
            Time to wait in seconds after opening socket connection to Cannelloni Interface
        """

        if not ap_address:  # if None or empty
            raise TypeError("Must specify IP Address and Port from the Access Point.")

        if not ap_address:  # if None or empty
            raise TypeError("Must specify IP Address and Port of the Access Point.")
        self.__ap_address = ap_address
        self.__local_address = ('0.0.0.0', 3333)  # local IP-Address and local Port

        if state is BusState.ACTIVE or state is BusState.PASSIVE:
            self.__state = state
        else:
            raise ValueError("BusState must be Active or Passive")

        if bitrate in cannelloni_bitrates:
            self.__bitrate = cannelloni_bitrates[bitrate]
        else:
            raise ValueError("Invalid bitrate {}".format(bitrate))

        if filter is True:
            self.__is_extended = is_extended
            self.__start_id = start_id
            self.__end_id = end_id

        self.__config = {
            "ap_address": self.__ap_address,
            "local_address": self.__local_address,
            "bitrate": self.__bitrate,
            "can_mode": can_mode,  # TODO: use state from basic.py or can.py?
            "filter": filter,
            "is_extended": is_extended,
            "start_id": start_id,
            "end_id": end_id
        }

        # get cannelloni device
        self.__cannelloni = Cannelloni(local_address=self.__config["local_address"],
                                       ap_address=self.__config["ap_address"])

        # init buffers
        self._udp_rx_packet_buf = bytearray()
        self.tx_buffer = queue.Queue()
        self.rx_buffer = queue.Queue()  # TODO: queue or deque(maybe faster?)
        self.__disable_rx = disable_rx

        if do_open:
            self.open()
        time.sleep(sleep_after_open)

        if not self.__disable_rx:
            self.__rcv_internal_thread = MyThread(func=self._recv_internal)
            self.__rcv_internal_thread.start()

        # start the send timer
        self.timer = CANNELLONISendTimer(0.03)  # send messages in the given interval
        self.timer.run()

        self.__snd_internal_thread = MyThread(func=self._send_internal)
        self.__snd_internal_thread.start()

        super(CannelloniBus, self).__init__(ap_address, **kwargs)

    def open(self):
        """
                Init the CAN channel on the cannelloni device.
        """
        self.__cannelloni.init_can(bitrate=self.__config["bitrate"],
                                   can_mode=self.__config["can_mode"],
                                   filter=self.__config["filter"],
                                   is_extended=self.__config["is_extended"],
                                   start_id=self.__config["start_id"],
                                   end_id=self.__config["end_id"]
                                   )

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
                logger.log(self.RECV_LOGGING_LEVEL, 'Received: %s', msg)
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
        data = bytearray()

        cannelloni_rcv_hdr, self._udp_rx_packet_buf = self.__cannelloni.recv(timeout=timeout)
        # if not cannelloni_rcv_hdr and self._udp_rx_packet_buf:
        data.clear()
        try:
            received_frames_count = cannelloni_rcv_hdr.count
        except AttributeError:
            received_frames_count = 0

        pos_left = self.CANNELLONI_DATA_PACKET_BASE_SIZE
        pos_right = self.CANNELLONI_DATA_PACKET_BASE_SIZE + 4
        for i in range(0, received_frames_count):
            can_id = struct.unpack("I", self._udp_rx_packet_buf[pos_left:pos_right])
            can_id = socket.ntohl(can_id[0])

            if can_id & CANNELLONI_CAN_ERR_FLAG:
                error_frame = True
            else:
                error_frame = False

            if can_id & CANNELLONI_CAN_EFF_FLAG:
                extended_frame = True
            else:
                extended_frame = False

            if can_id & CANNELLONI_CAN_RTR_FLAG:
                remote_frame = True
            else:
                remote_frame = False

            if extended_frame:
                can_id = can_id & CANNELLONI_CAN_EFF_MASK
            else:
                can_id = can_id & CANNELLONI_CAN_SFF_MASK

            pos_left = pos_right
            pos_right = pos_right + 1
            data_length_code = struct.unpack("B", self._udp_rx_packet_buf[pos_left:pos_right])
            data_length_code = data_length_code[0]  # TODO:redundant try [0]

            pos_left = pos_right
            pos_right = pos_left + data_length_code
            if not remote_frame:
                data = bytearray(self._udp_rx_packet_buf[pos_left:pos_right])

            if can_id is not None:
                message = Message(arbitration_id=can_id,
                                  is_extended_id=extended_frame,
                                  timestamp=time.time(),  # TODO: maybe use timestamp from ESP32
                                  is_remote_frame=remote_frame,
                                  is_error_frame=error_frame,
                                  dlc=data_length_code,
                                  data=data)
                self.rx_buffer.put(item=(message, False))
            else:
                self.rx_buffer.put(item=(None, False))

            pos_left = pos_right
            pos_right = pos_right + 4

    def send(self, msg, timeout=None):
        time.sleep(0.00033)
        self.tx_buffer.put(msg)

    def _send_internal(self):
        can_messages = list()

        queue_size = self.tx_buffer.qsize()
        if queue_size >= 20 or (self.timer.is_present() and queue_size > 0):
            while queue_size > 0:
                can_messages.append(self.tx_buffer.get())
                queue_size = queue_size - 1

            self.__cannelloni.send(can_messages)

            can_messages.clear()
            self.timer.clear()
            self.timer.reset()

    def get_socket(self):
        return self.__cannelloni.get_socket()

    def shutdown(self):
        time.sleep(2)
        if not self.__disable_rx:
            self.__rcv_internal_thread.cancel()
        self.__snd_internal_thread.cancel()
        #self.__rcv_internal_thread.join()
        #self.__snd_internal_thread.join()
        self.__cannelloni.shutdown()
        self.close()

