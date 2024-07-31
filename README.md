# USBIP CDC client
![workflow](https://github.com/bp100a/usbip/actions/workflows/python-app.yml/badge.svg?branch=develop)</br>
![coverage badge](./coverage.svg)</br>
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-312/)</br>
This package supports connecting to a CDC (serial) USB device exposed by a USBIPD server. USBIP is a protocol that allows sharing USB devices over a TCP/IP connection.

There are some issues sharing USB devices to docker containers, a major one being if the USB connection is lost
it is difficult to recover the connection between the docker container and the hosting server.

Here's a [link](https://marc.merlins.org/perso/linux/post_2018-12-20_Accessing-USB-Devices-In-Docker-_ttyUSB0_-dev-bus-usb-_-for-fastboot_-adb_-without-using-privileged.html
) that discusses this issue and another solution.

The USBIP client implementation will only address USB devices that implemented the CDC protocol, basically simple
serial devices. This allows for a simple connection to the USBIP server without the need for mapping USB devices into
the container.

## SOUP
| Module          | Version | comments                                    |
|-----------------|---------|---------------------------------------------|
| Python          | 3.12    | Python interpreter                          |
| py-datastruct   | 1.0.0   | Serialization of binary to/from dataclasses |


## Build Process
Using `pip-compile` from the [pip-tools](https://pypi.org/project/pip-tools/) package, read the docs [here](https://pip-tools.readthedocs.io/en/latest/)

```bash
pip-compile requirements.in
```

## Useful Resources
For a Windows version of the usbipd server, look [here](https://github.com/dorssel/usbipd-win). You can run this to share USB devices across a network,
there are usbipd-clients for Linux & [Windows](https://github.com/cezanne/usbip-win).
