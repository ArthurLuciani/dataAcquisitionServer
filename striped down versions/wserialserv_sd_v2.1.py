# -*- coding: utf-8 -*-

# IN THIS TEST I DO NOT USE A POWER OF 2 SERBUF, in order to thoroughly test
# buffer cycle around
# the implemented circular buffer only works when
# the total store, the serial buffer and the network buffer are integer multiples
# of each other

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

def instrumentReader():
    """
    Put your own instrument reader script here. To send data, put it 
    in the data_q queue.
    """
    
    data_q.put(data)
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
    tSer = threading.Thread(target=instrumentReader)
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
