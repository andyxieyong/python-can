import unittest
import can
import time
import socket
import select
import threading
from multiprocessing import pool


class ReceiveThread(threading.Thread):
    """
    Thread for the internal send and receive of messages
    """
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


class TestCannelloni(unittest.TestCase):

    def setUp(self):
        self.bus = can.Bus(bustype='cannelloni', ap_address=('192.168.4.1', 3333))
        self.socket = socket.socket
        self.socket = self.bus.get_socket()
        time.sleep(1)

    def tearDown(self):
        self.socket = None
        self.bus.shutdown()

    def test_recv_standard(self):
        frame = b'\x02\x00\xff\x00\x01\x00\x00\x03\xc0\x05\x04\x00\x00 \x00'
        self.socket.sendto(frame, ('192.168.4.2', 3333))

        msg = self.bus.recv()

        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, 0x3C0)
        self.assertEqual(msg.is_extended_id, False)
        self.assertEqual(msg.is_remote_frame, False)
        self.assertEqual(msg.dlc, 5)
        self.assertSequenceEqual(msg.data, [0x04, 0x00, 0x00, 0x20, 0x00])

    def test_send_standard(self):
        msg = can.Message(arbitration_id=0x3c0,
                          is_extended_id=False,
                          is_remote_frame=False,
                          dlc=5,
                          data=[0x04, 0x00, 0x00, 0x20, 0x00])
        self.bus.send(msg)
        data = 0
        self.socket.recvfrom(self.bus.CANNELLONI_UDP_RX_PACKET_BUF_LEN)
        self.assertEqual(data, b'\x02\x00\xff\x00\x01\x00\x00\x03\xc0\x05\x04\x00\x00 \x00')  # TODO: try can frame

    def test_recv_extended(self):
        frame = b'\x02\x00\xff\x00\x01\x97\xfe\x00\xba\x05\x04\x00\x00 \x00'
        self.socket.sendto(frame, ('192.168.4.2', 3333))

        msg = self.bus.recv()

        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, 0x17FE00BA)
        self.assertEqual(msg.is_extended_id, True)
        self.assertEqual(msg.is_remote_frame, False)
        self.assertEqual(msg.dlc, 5)
        self.assertSequenceEqual(msg.data, [0x04, 0x00, 0x00, 0x20, 0x00])

    def test_send_extended(self):
        def rcv():
            self.socket.setblocking(False)
            ready = select.select([self.socket], [], [], None)
            if ready[0]:
                return self.socket.recvfrom(self.bus.CANNELLONI_UDP_RX_PACKET_BUF_LEN)

        rcv_thread = threading.Thread(target=rcv)
        rcv_thread.start()
        thread_pool = pool.ThreadPool(processes=1)

        msg = can.Message(arbitration_id=0x17FE00BA,
                          is_extended_id=True,
                          is_remote_frame=False,
                          dlc=5,
                          data=[0x04, 0x00, 0x00, 0x20, 0x00])
        self.bus.send(msg)

        async_result = thread_pool.apply_async(func=rcv)
        data = async_result.get()
        # data = self.socket.recvfrom(self.bus.CANNELLONI_UDP_RX_PACKET_BUF_LEN)
        self.assertEqual(data, b'\x02\x00\xff\x00\x01\x97\xfe\x00\xba\x05\x04\x00\x00 \x00')  # TODO: try can frame


if __name__ == '__main__':
    unittest.main()
