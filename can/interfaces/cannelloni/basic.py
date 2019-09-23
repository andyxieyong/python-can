import enum
import threading


# ===========================#
#       TYPEDEFINITIONS      #
# ===========================#
TCANNELLONImode = int  # Represents a Cannelloni can mode
TCANNELLONIgpio = int  # Represents a Cannelloni GPIO
TCANNELLONIBaudrate = int  # Represents a Cannelloni Baud rate
TCANNELLONIfrequency = int  # Represents a Cannelloni clock frequency
TCANNELLONIflag = int  # Represents a Cannelloni frame format flag
TCANNELLONImask = int  # Represents a Cannelloni frame format mask

# ===========================#
#       VALUEDEFINITIONS     #
# ===========================#
# Cannelloni can modes
CANNELLONI_CAN_MODE_NORMAL = TCANNELLONImode(0)  # Normal operating mode (CAN controller can send/receive/acknowledge)
CANNELLONI_CAN_MODE_NO_ACK = TCANNELLONImode(1)  # Transmission does not require acknowledgment (self testing)
CANNELLONI_CAN_MODE_LISTEN_ONLY = TCANNELLONImode(2)  # CAN controller will not influence the bus (No transmissions or acknowledgments)

# Cannelloni GPIO numbers
CANNELLONI_GPIO_NUM_0 = TCANNELLONIgpio(0)  # GPIO0, input and output
CANNELLONI_GPIO_NUM_1 = TCANNELLONIgpio(1)  # GPIO1, input and output
CANNELLONI_GPIO_NUM_2 = TCANNELLONIgpio(2)  # GPIO2, input and output
CANNELLONI_GPIO_NUM_3 = TCANNELLONIgpio(3)  # GPIO3, input and output
CANNELLONI_GPIO_NUM_4 = TCANNELLONIgpio(4)  # GPIO4, input and output
CANNELLONI_GPIO_NUM_5 = TCANNELLONIgpio(5)  # GPIO5, input and output
CANNELLONI_GPIO_NUM_6 = TCANNELLONIgpio(6)  # GPIO6, input and output
CANNELLONI_GPIO_NUM_7 = TCANNELLONIgpio(7)  # GPIO7, input and output
CANNELLONI_GPIO_NUM_8 = TCANNELLONIgpio(8)  # GPIO8, input and output
CANNELLONI_GPIO_NUM_9 = TCANNELLONIgpio(9)  # GPIO9, input and output
CANNELLONI_GPIO_NUM_10 = TCANNELLONIgpio(10)  # GPIO10, input and output
CANNELLONI_GPIO_NUM_11 = TCANNELLONIgpio(11)  # GPIO11, input and output
CANNELLONI_GPIO_NUM_12 = TCANNELLONIgpio(12)  # GPIO12, input and output
CANNELLONI_GPIO_NUM_13 = TCANNELLONIgpio(13)  # GPIO13, input and output
CANNELLONI_GPIO_NUM_14 = TCANNELLONIgpio(14)  # GPIO14, input and output
CANNELLONI_GPIO_NUM_15 = TCANNELLONIgpio(15)  # GPIO15, input and output
CANNELLONI_GPIO_NUM_16 = TCANNELLONIgpio(16)  # GPIO16, input and output
CANNELLONI_GPIO_NUM_17 = TCANNELLONIgpio(17)  # GPIO17, input and output
CANNELLONI_GPIO_NUM_18 = TCANNELLONIgpio(18)  # GPIO18, input and output
CANNELLONI_GPIO_NUM_19 = TCANNELLONIgpio(19)  # GPIO19, input and output
CANNELLONI_GPIO_NUM_21 = TCANNELLONIgpio(21)  # GPIO21, input and output
CANNELLONI_GPIO_NUM_22 = TCANNELLONIgpio(22)  # GPIO22, input and output
CANNELLONI_GPIO_NUM_23 = TCANNELLONIgpio(23)  # GPIO23, input and output
CANNELLONI_GPIO_NUM_25 = TCANNELLONIgpio(25)  # GPIO25, input and output
CANNELLONI_GPIO_NUM_26 = TCANNELLONIgpio(26)  # GPIO26, input and output
CANNELLONI_GPIO_NUM_27 = TCANNELLONIgpio(27)  # GPIO27, input and output
CANNELLONI_GPIO_NUM_32 = TCANNELLONIgpio(32)  # GPIO32, input and output
CANNELLONI_GPIO_NUM_33 = TCANNELLONIgpio(33)  # GPIO33, input and output
CANNELLONI_GPIO_NUM_34 = TCANNELLONIgpio(34)  # GPIO34, input mode only
CANNELLONI_GPIO_NUM_35 = TCANNELLONIgpio(35)  # GPIO35, input mode only
CANNELLONI_GPIO_NUM_36 = TCANNELLONIgpio(36)  # GPIO36, input mode only
CANNELLONI_GPIO_NUM_37 = TCANNELLONIgpio(37)  # GPIO37, input mode only
CANNELLONI_GPIO_NUM_38 = TCANNELLONIgpio(38)  # GPIO38, input mode only
CANNELLONI_GPIO_NUM_39 = TCANNELLONIgpio(39)  # GPIO39, input mode only
CANNELLONI_GPIO_NUM_MAX = TCANNELLONIgpio(40)  # GPIO40, max number

# Cannelloni Baud rate define values
CANNELLONI_BAUD_1M = TCANNELLONIBaudrate(1000)  # 1 MBit/s
CANNELLONI_BAUD_800K = TCANNELLONIBaudrate(800)  # 800 kBit/s
CANNELLONI_BAUD_500K = TCANNELLONIBaudrate(500)  # 500 kBit/s
CANNELLONI_BAUD_250K = TCANNELLONIBaudrate(250)  # 250 kBit/s
CANNELLONI_BAUD_125K = TCANNELLONIBaudrate(125)  # 125 kBit/s
CANNELLONI_BAUD_100K = TCANNELLONIBaudrate(100)  # 100 kBit/s
CANNELLONI_BAUD_50K = TCANNELLONIBaudrate(50)  # 50 kBit/s
CANNELLONI_BAUD_25K = TCANNELLONIBaudrate(25)  # 25 kBit/s

# Cannelloni clock frequencies
CANNELLONI_CLK_FREQ_80M = TCANNELLONIfrequency(80)  # 80 MHz
CANNELLONI_CLK_FREQ_60M = TCANNELLONIfrequency(60)  # 60 MHz
CANNELLONI_CLK_FREQ_40M = TCANNELLONIfrequency(40)  # 40 MHz
CANNELLONI_CLK_FREQ_30M = TCANNELLONIfrequency(30)  # 30 MHz
CANNELLONI_CLK_FREQ_24M = TCANNELLONIfrequency(24)  # 24 MHz
CANNELLONI_CLK_FREQ_20M = TCANNELLONIfrequency(20)  # 20 MHz

# Cannelloni frame format flags
CANNELLONI_CAN_EFF_FLAG = TCANNELLONIflag(0x80000000)  # Flag for Extended Frame Format (29bit arbitration-ID)
CANNELLONI_CAN_RTR_FLAG = TCANNELLONIflag(0x40000000)  # Flag for Remote Transmit Request frame
CANNELLONI_CAN_ERR_FLAG = TCANNELLONIflag(0x20000000)  # Flag for Error Frame

# Cannelloni frame format masks
CANNELLONI_CAN_SFF_MASK = TCANNELLONImask(0x000007FF)  # Mask for the Standard Frame Format
CANNELLONI_CAN_EFF_MASK = TCANNELLONImask(0x1FFFFFFF)  # Mask for the Extended Frame Format
CANNELLONI_CAN_ERR_MASK = TCANNELLONImask(0x1FFFFFFF)  # Mask for the Error Frame

# TODO: ESP32 file
# ESP32 CAN Message Flags
CAN_MSG_FLAG_NONE = 0x00  # No message flags (Standard Frame Format)
CAN_MSG_FLAG_EXTD = 0x01  # Extended Frame Format (29bit arbitration-ID)
CAN_MSG_FLAG_RTR = 0x02  # Message is a Remote Transmit Request
CAN_MSG_FLAG_SS = 0x04  # Transmit as a Single Shot Transmission
CAN_MSG_FLAG_SELF = 0x08  # Transmit as a Self Reception Request
CAN_MSG_FLAG_DLC_NON_COMP = 0x10  # Message's Data length code is larger than 8. Will break compliance with CAN2.0B


class CANNELLONIOpCodes(enum.Enum):
    """
    Op Codes for the Cannelloni Data Packet.
    """
    DATA = 0
    ACK = 1
    NACK = 2


class CANNELLONIDataPacket(object):
    """
    Header for one Cannelloni UDP Packet
    """
    def __init__(self):
        self.version = 0
        self.op_code = 0
        self.seq_no = 0
        self.count = 0


class CANNELLONISendTimer(object):
    """
    Timer for the message send interval
    """
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


class CANNELLONIInternalThread(threading.Thread):
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
