from .basic import *
import socket
import websocket
import json
import select
import struct
import sys


class Cannelloni:
    CANNELLONI_UDP_RX_PACKET_BUF_LEN = 1600  # Defines the size of the Receiving buffer
    CANNELLONI_DATA_PACKET_BASE_SIZE = 5  # Defines the Base size of an Cannelloni Data Packet
    CANNELLONI_FRAME_VERSION = 2  # Defines the used Cannelloni Frame Version

    ACCEPTANCE_CODE_ALL = 0
    ACCEPTANCE_MASK_ALL = 0xFFFFFFFF

    __seq_no = 0x0  # first Cannelloni Data Packet sequence number (last sequence number is 0xff)

    def __init__(self, local_address, ap_address):
        self.__ap_address = ap_address
        self.__local_address = local_address

        # init socket with the local IP-Address and Port
        self.__socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.__socket.bind(self.__local_address)

        # init Websocket with the Access Point address and the Websocket port
        self.__WEBSERVER_PORT = 81
        self.__websocket = websocket.WebSocket()

        #self.__websocket.connect("ws://" + str(self.__ap_address[0]) + ":" + str(self.__WEBSERVER_PORT) + "/")
        self.__websocket = None
        self._udp_rx_packet_buf = bytearray()

        self.__can_is_initialized = False

    def init_can(self, bitrate=CANNELLONI_BAUD_500K, can_mode=CANNELLONI_CAN_MODE_NORMAL,
                 filter=False, is_extended=False, start_id=0x0, end_id=0x7FF):
        """
        Initializes the CAN channel of the cannelloni device.

        :param int bitrate:
            Baud rate define for the CAN driver
        :param int can_mode:
            Transmission mode of the CAN controller
        :param bool filter:
            Filter CAN Messages. True := filter messages, False := no Message filtering
        :param bool is_extended:
            Extended arbitration ID.
        :param int start_id:
            Specifies the arbitration ID from which to filter.
            default: 0x0
        :param int end_id:
            Specifies the arbitration ID up to which to filter.
            default: 0x7FF (standard frame format)
        :return:
        """
        if not self.__can_is_initialized:
            can_config = {
                "bitrate": bitrate,
                "can_mode": can_mode,
                "filter": filter,
                "is_extended": is_extended,
                "start_id": start_id,
                "end_id": end_id
             }

            self.__websocket.send(json.dumps(can_config))
            self.__can_is_initialized = True
            init_message = bytes("Cannelloni", "utf-8")
            self.__socket.sendto(init_message, self.__ap_address)  # send init message to the Access Point

    def recv(self, timeout=None):
        self.__socket.setblocking(False)

        ready = select.select([self.__socket], [], [], timeout)
        if ready[0]:
            try:
                self._udp_rx_packet_buf, server = self.__socket.recvfrom(self.CANNELLONI_UDP_RX_PACKET_BUF_LEN)  # TODO: try
            except OSError:
                return None, None
        else:
            return None, None

        rcv_hdr = CANNELLONIDataPacket()
        (rcv_hdr.version, rcv_hdr.op_code, rcv_hdr.seq_no) = struct.unpack("BBB", self._udp_rx_packet_buf[0:3])
        rcv_hdr.count = struct.unpack("H", self._udp_rx_packet_buf[3:5])

        rcv_hdr.count = socket.ntohs(rcv_hdr.count[0])

        rcv_len = len(self._udp_rx_packet_buf)
        if rcv_len < self.CANNELLONI_DATA_PACKET_BASE_SIZE:
            print("Did not receive enough data", file=sys.stderr)
            return None, None

        if rcv_hdr.version != self.CANNELLONI_FRAME_VERSION:
            print("Recieved wrong cannelloni frame verion", file=sys.stderr)
            return None, None

        if rcv_hdr.op_code != CANNELLONIOpCodes.DATA.value:
            print("Received wrong op code", file=sys.stderr)
            return None, None

        if rcv_hdr.count == 0:
            print("No frame received", file=sys.stderr)
            return None, None

        return rcv_hdr, self._udp_rx_packet_buf

    def send(self, can_messages):
        self.__socket.setblocking(False)
        udp_tx_packet_buf, packet_size = self.__cannelloni_build_packet(can_messages, len(can_messages))

        if packet_size < 0:
            print("cannelloni build packet failed", file=sys.stderr)
        ready = select.select([], [self.__socket], [], None)
        if ready[1]:
            send = self.__socket.sendto(udp_tx_packet_buf, self.__ap_address)  # TODO: try catch?
            if send < 0:
                print("sento error: %s" % send, file=sys.stderr)

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

        snd_hdr = CANNELLONIDataPacket()
        snd_hdr.version = self.CANNELLONI_FRAME_VERSION
        snd_hdr.op_code = CANNELLONIOpCodes.DATA.value
        snd_hdr.seq_no = self.__seq_no
        snd_hdr.count = 0
        snd_hdr.count = socket.htons(frame_count)

        self.__seq_no = self.__seq_no + 1
        if self.__seq_no > 0xFF:
            self.__seq_no = 0

        udp_tx_packet_buf = struct.pack('BBB', snd_hdr.version, snd_hdr.op_code, snd_hdr.seq_no)
        udp_tx_packet_buf = udp_tx_packet_buf + struct.pack('H', snd_hdr.count)

        for i in range(0, frame_count):
            can_id = can_msg[i].arbitration_id
            if can_msg[i].is_extended_id:
                can_id = can_id | CANNELLONI_CAN_EFF_FLAG
            if can_msg[i].is_remote_frame:
                can_id = can_id | CANNELLONI_CAN_RTR_FLAG

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
        self.__socket.close()
        if self.__websocket is not None:
            self.__websocket.close()
