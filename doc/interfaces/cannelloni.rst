.. _slcan:

CAN over Ethernet tunnel / Cannelloni
=====================================

A UDP based interface: compatible to cannelloni (https://github.com/mguentner/cannelloni).
This driver packs/unpacks CAN Frames in UDP packets compatible to cannelloni.

Usage: use bus like this:
can.Bus(bustype='cannelloni', ip_address_ap=('192.168.4.1', 3333))

.. note:
    An ESP32-Interface could easily be build with this:
    https://github.com/PhilippFux/ESP32_CAN_Interface


Supported devices
-----------------

.. todo:: Document this.


Bus
---

.. autoclass:: can.interfaces.canelloni.Cannelloni
    :members:


Internals
---------

.. todo:: Document the internals of cannelloni interface.
