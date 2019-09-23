import threading
import sys
import enum
import socket
import struct
import can
import time


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


SLEEP_AFTER_SOCKET_OPEN = 1  # in seconds

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

seq_no = 0x0

tx_buffer = list()
frame_count = 0


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


def send_internal():
    global tx_buffer, frame_count
    udp_tx_packet_buf, packet_size = cannelloni_build_packet(tx_buffer, frame_count)  # TODO: multiple frames
    tx_buffer.clear()
    print(udp_tx_packet_buf, packet_size)


def send(msg, timer):
    global frame_count
    tx_buffer.append(msg)
    frame_count = frame_count + 1
    if timer.is_present() or len(tx_buffer) > 35:
        send_internal()
        frame_count = 0
        timer.clear()


def cannelloni_build_packet(can_msg, frame_count):
    global seq_no

    snd_hdr = CannelloniDataPacket()
    snd_hdr.version = CANNELLONI_FRAME_VERSION
    snd_hdr.op_code = OpCodes.DATA.value
    snd_hdr.seq_no = seq_no
    snd_hdr.count = 0
    snd_hdr.count = socket.htons(frame_count)

    seq_no = seq_no + 1
    if seq_no > 0xFF:
        seq_no = 0

    udp_tx_packet_buf = struct.pack("BBB", snd_hdr.version, snd_hdr.op_code, snd_hdr.seq_no)
    udp_tx_packet_buf = udp_tx_packet_buf + struct.pack("H", snd_hdr.count)

    for i in range(0, frame_count):
        can_id = can_msg[i].arbitration_id
        if can_msg[i].is_extended_id:
            can_id = can_msg[i].arbitration_id | CAN_EFF_FLAG
        if can_msg[i].is_remote_frame:
            can_id = can_msg[i].arbitration_id | CAN_RTR_FLAG

        can_id = socket.htonl(can_id)

        udp_tx_packet_buf = udp_tx_packet_buf + struct.pack("I", can_id)
        udp_tx_packet_buf = udp_tx_packet_buf + struct.pack("B", can_msg[i].dlc)

        if not can_msg[i].is_remote_frame:
            for n in range(0, can_msg[i].dlc):
                udp_tx_packet_buf = udp_tx_packet_buf + struct.pack("B", can_msg[i].data[n])

    packet_size = len(udp_tx_packet_buf)
    return udp_tx_packet_buf, packet_size


message = can.Message(arbitration_id=0x17FE009C,
                      is_extended_id=True,
                      timestamp=time.time(),  # Better than nothing... TODO: maybe use timestamp from ESP32
                      is_remote_frame=False,
                      is_error_frame=False,
                      dlc=8,
                      data=bytearray([0x02, 0x3E, 0x00, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA]))


timer = MyTimer(0.001)
timer.start()

i = 0
while i < 15000:
    send(message, timer)
    i = i + 1
timer.cancel()
timer.join()
