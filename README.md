# dataAcquisitionServer (and client)

These scripts allow measurement devices to equipped with a simple TCP/IP server using a standard host workstation or a single-board hostcomputer such as a Raspberry Pi having an Ethernet port. The measurement devices may for example communicate with the host using a serial connection or direct GPIO or USB or SPI or I2C. The server host computer reads these inputs and serves them on request to connected guests over TCP/IP. The scripts are 'pure Python' and only use standard libraries (except for those that may be needed to communicate between the host and the measurement device).

The socket server protocol has been kept simple, and just sends out chunks of data upon various requests from the guests. The server script is multithreaded which ensures that the measurement device can be read out as well as possible. The code for reading out the measurement device can be adapted for each specific device. In this case, we use a measurement device that delivers measurement data over a serial connection, for example an Arduino board or an FPGA board. 

This is an initial working version. Use at your own risk. Or just use it as an inspiration for your own program.

## Installation

The package consists of 3 scripts

### Serpy.py
Note that the newer versions of *wserialserv* (>=2.1) and *photCountGUI* (>=2.2) requires the *serpy.py* module which can be found at this adress : 
https://github.com/ArthurLuciani/serpy

### multipletau
multipletau is from https://github.com/FCS-analysis/multipletau
