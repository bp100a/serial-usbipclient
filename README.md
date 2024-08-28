USBIP Serial client ![workflow](https://github.com/bp100a/serial-usbipclient/actions/workflows/python-app.yml/badge.svg?branch=develop) ![Python](https://img.shields.io/badge/python-3.11%20%7C%20%203.12-blue) ![PyPI - Implementation](https://img.shields.io/pypi/implementation/cython) ![coverage](https://raw.githubusercontent.com/bp100a/serial-usbipclient/master/coverage.svg)
========================================================================================================
<div>

![](https://github.com/bp100a/serial-usbipclient/blob/mypy/logo.png?raw=true)

</div>

___
Overview
--------------------------------------------------------------------------
___
This package supports connecting to a CDC (serial) USB device exposed by a USBIPD server. USBIP is a protocol that allows sharing USB devices over a TCP/IP connection.
The protocol specification can be found [here](https://docs.kernel.org/usb/usbip_protocol.html). This package should be capable of running on any system that supports Python.

There are some issues sharing USB devices to docker containers, a major one being if the USB connection is lost
it is difficult to recover the connection between the docker container and the hosting server.

Here's a [link](https://marc.merlins.org/perso/linux/post_2018-12-20_Accessing-USB-Devices-In-Docker-_ttyUSB0_-dev-bus-usb-_-for-fastboot_-adb_-without-using-privileged.html) that discusses this issue and another solution.

The USBIP client implementation will only address USB devices that implemented the CDC protocol, basically simple
serial devices. This allows for a direct connection to the USBIP server without the need for mapping USB devices into
the container.

* Project Homepage: https://github.com/bp100a/serial-usbipclient

Installation
--------------------------------------------------------------------------
___
`pip install serial-usbipclient` should work for most users.

Usage
--------------------------------------------------------------------------
___
```python
from serial_usbipclient.usbip_client import USBIPClient, HardwareID, USBIP_Connection

host: str = 'localhost'
port: int = 3240  # commonly used port for USBIPD servers
target: HardwareID = HardwareID(vid=1234, pid=5678)  # USB devices are identified by VID/PID
client: USBIPClient = USBIPClient(remote=(host, port))
client.connect_server()
client.attach(devices=[target])
connections: list[USBIP_Connection] = client.get_connection(device=target)

# using the established connection, data can be written to the USB device
# using the sendall() method
connections[0].sendall(data=b'\01\02\03\04')

# response data can be read either explicitly by specifying the size of the expected
# response, or if 0 size is specified, up to a delimiter. The delimiter is a property of
# the connection and can be set, default=b'\r\n'
connections[0].delimiter = b'\n'
response: bytes = connections[0].response_data(size=0)  # reads until delimiter
```

SOUP
--------------------------------------------------------------------------
___
| Module          | Version    | comments                                    |
|-----------------|------------|---------------------------------------------|
| Python          | 3.11, 3.12 | Python interpreter                          |
| py-datastruct   | 1.0.0      | Serialization of binary to/from dataclasses |


Useful Resources
--------------------------------------------------------------------------
___
For a Windows version of the usbipd server, look [here](https://github.com/dorssel/usbipd-win). You can run this to share USB devices across a network,
there are usbipd-clients for Linux & [Windows](https://github.com/cezanne/usbip-win).

Here's a USBIP server for testing written in RUST, https://github.com/jiegec/usbip.

Testing
--------------------------------------------------------------------------
___
A `MockUSBIP` service reads configuration information from the output of `lsusb` (e.g `lsusb -d 1f46:1b01 -v`). **MockUSBIP** will then play back this configuration.
Just capture the output of the `lsusb` command and save with the `.lsusb` suffix in the test folder. The file name should be the `busnum`/`devnum` number.

```text
1-1.lsusb
1-2.lsusb
1-3.lsusb
99-99.lsusb
```
Would result in 4 devices with busid values of `1-1`, `1-2`, `1-3` and `99-99`. Please note the file `99-99.lsusb` is reserved to provide a device to generate
failing USBIPD attachments, and `1-2` & `1-3` have the same VID/PID (for testing multiple identical device connections).

During testing, the `MockUSBIP` service acts as a stand-in for an actual USBIP server. Since the tests are run in parallel, 
the port on which the service listens must be unique for each unit test. This is accomplished by the `conftest.py::pytest_sessionstart` which is run
when the pytest session is started and collects all tests being run into a file called `lists_of_tests.json`. The unit test's index into this array
is used to determine the offset to be added to the port base (typically **3240**).


Tooling
--------------------------------------------------------------------------
___
This package was created using JetBrains PyCharm Professional IDE, the repository does not contain any IDE specific files. 
Development work was done using Windows 11 & Python 3.12.5, with final verification on an Ubuntu 20.04 system.

### Packages required to run tests
___
| Module         | Version | comments                                           |
|----------------|---------|----------------------------------------------------|
| pytest         | 8.3.2   | unit testing framework                             |
| pytest-xdist   | 3.6.1   | distributes testing across multiple cpu/cores      |
| coverage       | 7.6.1   | coverage of unit tests                             |
| pylint         | 3.2.6   | linter, ensures adherence to PEP-8 standards       |
| pip-tools      | 7.4.1   | provides `pip-compile` to create requirement files |
| pytest-cov     | 5.0.0   | integrates coverage with pytest                    |
| pytest-timeout | 2.3.1   | provides ability to timeout pytest unit tests      |
| mypy           | 1.11.2  | type checking                                      |

### Packages required publish to PyPi
___
| Module      | Version  | comments                       |
|-------------|----------|--------------------------------|
| poetry-core | 1.9.0    | build system                   |

All tooling is defined in the `tool_requirements.txt` and should be installed on the build system as follows:
```shell
pip install -r tool_requirements.txt
```

Tooling is not needed to run the package but is required for testing & packaging.

Build Process
--------------------------------------------------------------------------
___
Using `pip-compile` from the [pip-tools](https://pypi.org/project/pip-tools/) package, read the docs [here](https://pip-tools.readthedocs.io/en/latest/)

```bash
pip-compile requirements.in
```

Release to PyPi (_now using Poetry!_)
----------------------------------------------------------------------------
Store the PyPi API token
```bash
keyring set https://upload.pypi.org/legacy/ __token__
```
when prompted enter the API token you created using PyPi.

To build the distribution and upload to PyPi
```cmd
poetry build
poetry publish
```
