# -*- coding: utf-8 -*-

# IN THIS TEST I DO NOT USE A POWER OF 2 SERBUF, in order to thoroughly test
# buffer cycle around
# the implemented circular buffer only works when
# the total store, the serial buffer and the network buffer are integer multiples
# of each other

import serial
import select
import serpy as sp
import queue
import threading
from time import sleep

PORT = 18888
STIMEOUT = 0.020 # timeout for select  (but also for sstream read!)
SERBUF = 8192 # this buffer size will be the same for sttream reads and socket transfer
BUF = 8*SERBUF
INMSGLEN = 8
NSTORE = 4*BUF

def serialReader():
    """
    This thread handles the connection to the serial port as well as the
    retrieval of data from it. It puts the data insiside de data queue
    (data_q) and if this queue is full it void the first element of the
    queue and then place the new element.
    """
    # SET UP SERIAL READER
    #dev = '/dev/ttyACM0'
    dev = '/dev/ttyUSB0'
    # bps=57600   # On arduino we use prescaler 16 for BPS 57600
    # below is exact
    
    PRESCALER = 2
    #bps = 2*(1000000/(PRESCALER+1)) #double speed 2* TODO do we need integers?
    bps = 3000000
    print('bps exact',bps)
    # Nbuf = BUF # Nbuf = 4096 
    # 2048 seems to work slightly better than 1024 
    # 4096 seems to work better than 2048 (on my system)
    # Tsleep = STIMEOUT # Tsleep = 0.040 # shorter sleep to be safe
    # different successful combinations
    # Nbuf=4096; Tsleep = 0.056 (guess that limit is at 0.060)
    # Nbuf=2048; Tsleep = 0.028 (0.030 is near limit)
    try:
        ser.close()
    except:
        pass
    try :
        ser = serial.Serial(port=dev, baudrate=bps, timeout=3) 
        w=ser.inWaiting()
        rbuf = ser.read(w)
        print('serial port open and cleared')
    except :
        print("Serial connection is not ready !")
        exit_q.put(None)
        exit()
    while exit_q.empty():
        #w=ser.inWaiting()
        #print('waiting:',w)
        lock.acquire()
        try:
            rbuf = ser.read(SERBUF)
        except:
            print("Serial Connection Error")
            exit_q.put(None) #closes the server
            pack_q.put(b'\x00'*SERBUF)
            lock.release()
            print("Lock realeased")
            #ser.close()
            break
        else: 
            lock.release()
        if 0 in rbuf : print("0 detected")
        Nread = len(rbuf)
        if Nread!=SERBUF:
            print("Serial Connection Error")
            exit_q.put(None) #closes the server
            ser.close()
            #server_socket.close()
            #raise RuntimeError('Serial read was not OK')
        #rbuf = b'\x09'*SERBUF
        if data_q.full() : 
            data_q.get()
            print("losing data")
        data_q.put(rbuf)
    print('close serial port')
    ser.close()
    exit()

def packagingThread():
    """
    This thread retrieves the data inside the data queue and assembles
    with it packets of size BUF bytes. Those packets are then put inside
    packet queue (pack_q).
    """
    package = bytes()
    temp = bytes()
    while exit_q.empty():
        try :
            temp = data_q.get(timeout=1)
            remaining_space = BUF-len(package)
            if len(temp) <= remaining_space:
                package += temp
            else :
                package += temp[:remaining_space]
            if len(package) >= BUF :
                pack_q.put(package)
                package = temp[remaining_space:]
        except queue.Empty:
            pass
    exit()
        

def socketCom():
    """
    input : a list containing the binded socket object of the server
        This thread handles the comunication between this server and the
    client which is part of the GUI.
    It handles new connections and then it serves those connections by 
    giving them the data they request.
    """
    s = sp.Server('', PORT, nb_conn=1).start()
    while exit_q.empty():
        for c in s.readableConnections() :
            data = c.getData().decode('ascii')
            if data.startswith('KTHXBYE!'):
                print("CLOSING SERVER")
                exit_q.put(None)
            
            elif data.startswith('GIVEDATA'):
                packet = pack_q.get()
                #packet = b'\x09'*BUF
                print("in buffer", pack_q.qsize()+data_q.qsize())
                c.sendData(packet)
        sleep(0.01)

    s.closeServer()
    exit()

if __name__ == "__main__":
    exit_q = queue.Queue(10)
    data_q = queue.Queue(32)
    pack_q = queue.Queue(16)
    lock = threading.Lock()
    tSer = threading.Thread(target=serialReader)
    tSer.start()
    tSoc = threading.Thread(target=socketCom)
    tSoc.start()
    tPac = threading.Thread(target=packagingThread)
    tPac.start()
    sleep(2)
    tSer.join()
    tSoc.join()
    while not pack_q.empty():
        pack_q.get_nowait()
    print("pack_q emptied")
    tPac.join()
    try :
        server_socket.close()
    except :
        pass
        
    print("Server successfully closed")
