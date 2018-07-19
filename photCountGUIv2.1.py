#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
This is a GUI for a photon counting instrument

Author: Arthur Luciani
Last edited: 25-05-2018
"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QFrame, 
    QSplitter, QStyleFactory, QApplication, QLineEdit, QPushButton,
    QVBoxLayout, QLabel, QProgressBar, QStatusBar, QMessageBox, 
    QLCDNumber, QSlider)
from PyQt5.QtCore import Qt, QBasicTimer
import sys
import pyqtgraph as pg
import numpy as np
from time import time, sleep
import socket
from datetime import datetime
import queue
import threading
import configparser


# --- parsing parameters from the parameters file ----------------------
config = configparser.ConfigParser()
config.read('parameters.ini')

HOST = config["Network"].get('IP address', 'localhost')
PORT = int(config["Network"].get('port', '8888'))
SERBUF = 8192 # this buffer size will be the same for sttream reads and socket transfer
BUF = 8*SERBUF
#BUF = int(config["Network"].get('packet size', '16000'))

RES = int(config["Display"].get('number of points', '500'))
SPAN = float(config["Display"].get('time span', '10'))
N_tracer = RES
T_timer = SPAN/RES*1000
print(T_timer)
sleep(1)

# --- functions --------------------------------------------------------

def recvPacketSize(conn, size):
    """
    input : conn (a connected socket object), size (int) in bytes
    output : message (string)
        This function retrieves from the connecion (conn) a message of 
    lenght (size) in bytes and returns it.
    """
    data = []
    bytesRecv = 0
    while bytesRecv < size :
        chunk = conn.recv(min(size - bytesRecv, 4096))
        bytesRecv += len(chunk)
        #print(len(chunk))
        if chunk :
            data.append(chunk)
        else :
            print("Connection broken !!")
            return -1
    return b''.join(data)

def comThread(stat_lbl):
    """
    This thread handles the comunication between this GUI and the server.
    It first tries to connect itself with the server and then it 
    collects the data from it and it puts it in the data_q formated as
    a numpy array of ubyte."""
    global BUF
    connected = False
    while exit_q.empty():
        if not connected :
            data_q.put(np.frombuffer(b'\x00'*BUF,dtype=np.ubyte))
            try :
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                print("Attempting connection to ", (HOST, PORT))
                stat_lbl.setText("Status : Attempting connection to\n{}:{}".format(HOST, PORT))
                stat_lbl.adjustSize()
                QApplication.processEvents()
                sock.connect((HOST, PORT))
                print("Successfully connected to ", (HOST, PORT))
                stat_lbl.setText("Status : Successfully connected to\n{}:{}".format(HOST, PORT))
                stat_lbl.adjustSize()
                QApplication.processEvents()
                connected = True
            except :
                print("Failed to connect")
                stat_lbl.setText("Status : Failed to connect")
                stat_lbl.adjustSize()
                QApplication.processEvents()
                sleep(1)
            #retrieves the packet size from the server
            else :
                msg = ""
                while "EOT" not in msg:
                    msg += sock.recv(512).decode(encoding='ascii')
                    if not msg :
                        sock.close()
                        connected = False
                        print("Starting server")
                        stat_lbl.setText("Status : Starting server")
                        stat_lbl.adjustSize()
                        QApplication.processEvents()
                        sleep(1)
                        break
                if connected:
                    BUF = int(msg.split("EOT")[0])
                    print("NEW PACKET SIZE :: ", BUF)
                    stat_lbl.setText("Status : waiting for acquisition")
                    stat_lbl.adjustSize()
                    QApplication.processEvents()

        elif not data_q.full() :
            sock.sendall("GIVEDATA".encode("ascii"))
            data = recvPacketSize(sock, BUF)
            if type(data) == int :
                print("Connection broken !!")
                connected = False
                sock.close()
            else :
                #print('data available:',len(data))
                data_q.put(np.frombuffer(data,dtype=np.ubyte))
    if connected : 
        sock.close()
    exit()

class Gui(QWidget):
    
    def __init__(self):
        super().__init__()
        
        self.initUI()
        
        
    def initUI(self):
        """
        Initialises all the widgets as well as the comThread.
        """
        self.tInit = time() #marks the starting time for the tracer
        hbox = QHBoxLayout(self)
        p1 = pg.PlotWidget(self) #creates the plot widget

        topright = QFrame(self)
        topright.setFrameShape(QFrame.StyledPanel)
        vbox = QVBoxLayout(topright) #adds a Vertical Box Layout for the topright frame
        
        #splits the window in two
        splitter1 = QSplitter(Qt.Horizontal)
        splitter1.addWidget(p1)
        splitter1.addWidget(topright)

        hbox.addWidget(splitter1)
        self.setLayout(hbox)
        # --- initialisation of the topright's widgets ------------------
        lbl0 = QLabel(topright)
        lbl0.setText("Number of photon per seconds")
        lbl0.adjustSize()
        
        self.lcd = QLCDNumber(self)
        self.lcd.setDigitCount(8)
        
        lbl1 = QLabel(topright)
        lbl1.setText("Size of the acquisition (Ncyc)")
        lbl1.adjustSize()
        
        self.qle = QLineEdit(topright)
        self.qle.textChanged[str].connect(self.onChanged)
        
        self.lbl2 = QLabel(topright)
        self.lbl2.setText("Estimated Time : ")
        self.lbl2.adjustSize()
        
        self.lbl3 = QLabel(topright)
        self.lbl3.setText("Size of the acquisition : ")
        self.lbl3.adjustSize()       
        
        btn = QPushButton("Acquisition", topright)
        btn.clicked.connect(self.acquisition)
        
        self.pbar = QProgressBar(topright)
        
        self.stat_lbl = QLabel(topright)
        self.stat_lbl.setText("Status : waiting for acquisition")
        self.stat_lbl.adjustSize()
        
        self.fixedScale = False
        self.btn2 = QPushButton("Fix scale", topright)
        self.btn2.setCheckable(True)
        self.btn2.clicked.connect(self.fixScale)
        
        self.timeSpan = 5
        self.slider = QSlider(Qt.Horizontal, topright)
        self.slider.setRange(1, 100)
        self.slider.setInvertedAppearance(True)
        self.slider.setSingleStep(1)
        self.slider.setSliderPosition(5)
        self.slider.valueChanged[int].connect(self.updateTimeScale)
        
        self.lbl4 = QLabel(topright)
        self.lbl4.setText("Time span : 5 s")
        self.lbl4.adjustSize()
        
        self.paused = False
        btn3 = QPushButton("Pause", topright)
        btn3.setCheckable(True)
        btn3.clicked[bool].connect(self.pause)
        
        # --- adding to the Vertical Box Layout-------------------------
        vbox.addWidget(lbl0)
        vbox.addWidget(self.lcd)
        vbox.addWidget(lbl1)
        vbox.addWidget(self.qle)
        vbox.addWidget(self.lbl2)
        vbox.addWidget(self.lbl3)
        vbox.addWidget(btn)
        vbox.addWidget(self.pbar)
        vbox.addWidget(self.btn2)
        vbox.addWidget(self.slider)
        vbox.addWidget(self.lbl4)
        vbox.addWidget(btn3)
        vbox.addWidget(self.stat_lbl)
        topright.setLayout(vbox)
        
        # starting the com thread
        self.comTh = threading.Thread(target=comThread, args=(self.stat_lbl,))
        self.comTh.start()
        
        # setting the tracer
        self.timer = QBasicTimer()
        self.t = np.linspace(0, 0, N_tracer)
        self.y = np.zeros(N_tracer)
        self.data = np.zeros(N_tracer)
        self.curve = p1.plot(pen='y')
        self.curve.setData(self.t, self.y)
        p1.setLabel('left', text='Number of photons per {} ms'.format(
                        int(4e-3*BUF)))
        p1.setLabel('bottom', text='Time', units='s')
        self.viewBox = p1.getViewBox()
        
        self.setGeometry(0, 0, 1200, 600)
        splitter1.setSizes([1100-150, 150])
        self.setWindowTitle('Photon Counting GUI')
        #self.show()
        self.showMaximized()
        self.timer.start(T_timer, self)


    def onChanged(self, text):
        """
        Provides a guess of the time which the acquisition would 
        take.
        """
        self.lbl2.setText("Estimated Time : "+str(int(eval(text)*BUF*4e-6))+" s")
        self.lbl2.adjustSize()
        self.lbl3.setText("Weight of the acquisition : "+str(int(eval(text)*BUF/1000))+" kB")
        self.lbl3.adjustSize() 
        
    def pause(self, pressed):
        if pressed :
            self.paused = True
        else :
            self.paused = False

    def nbPhoton(self, data, old_data):
        return (data[0] - old_data) + sum(data[1:]-data[:-1])

    def acquisition(self):
        """
        This function handles the acquisition mode.
        It first stops the timer so that no data is lost to it.
        Then it retrieves the data from the data_q as fast as possible
        until it has retrieved Ncyc packets (of size BUF).
        Then it saves it in an .npy file and finally it restarts the 
        timer.
        """
        Ncyc = int(eval(self.qle.text()))
        print(Ncyc)
        self.stat_lbl.setText("Status : acquiring")
        self.stat_lbl.adjustSize()
        self.timer.stop()
        Nstore = BUF*Ncyc
        store = np.zeros(Nstore,dtype=np.ubyte)
        for i in range(Ncyc):
            store[i*BUF:(i+1)*BUF] = data_q.get()
            self.pbar.setValue(int(i/Ncyc*100))
            QApplication.processEvents()
        self.pbar.setValue(100)
        self.stat_lbl.setText("Status : acquisition complete\n data saved")
        self.stat_lbl.adjustSize()
        np.save("data-{}".format(str(datetime.now()).split(".")[0]), store)
        self.timer.start(T_timer, self)
        
    def fixScale(self):
        if self.fixedScale :
            self.btn2.setText("Fix scale")
        else :
            self.btn2.setText("Unfix scale")
        self.fixedScale = not self.fixedScale

    def updateTimeScale(self, value):
        self.timeSpan = value
        self.lbl4.setText("Time span : {} s".format(value))
        self.lbl4.adjustSize()
        
    def timerEvent(self, e):
        """
        Handles the tracer continuous display.
        It shifts the time and y arrays and it retrieves the new data.
        It also updates the LCD dispaly.
        This function is called every T_timer milliseconds.
        """
        self.t[0:-1] = self.t[1:]
        self.t[-1] = time() - self.tInit
        old_data = self.data[-1]
        self.y[0:-1] = self.y[1:]
        if not data_q.empty(): #retrieves the new number of photons
            self.data = data_q.get()
            self.y[-1] = self.nbPhoton(self.data, old_data)
            self.lcd.display(int(self.y[-1]/(4e-6*BUF)))
        else : #makes a constant approximation to ensure fluidity
            self.y[-1] = self.y[-2]
        #print(self.y[-1])
        if not self.paused :
            self.curve.setData(self.t, self.y)
            self.viewBox.setXRange(self.t[-1]-self.timeSpan, self.t[-1])
            if not self.fixedScale:
                i = 0
                while self.t[i] < self.t[-1]-self.timeSpan:
                    i += 1 
                self.viewBox.setYRange(0, max(1,max(self.y[max(0,i-15):])))
        
    def closeEvent(self, event):
        """
        Properly closes the threads and shutting down the server if
        asked.
        """
        reply = QMessageBox.question(self, 'Message',
            "Do you want to shutdown the server ?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.No)

        try :
            exit_q.put(None) #closing threads
            self.comTh.join()
            if reply == QMessageBox.Yes:
                # connects to the server to send the shutdown signal
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((HOST, PORT))
                sock.sendall('KTHXBYE!'.encode('ascii'))
                msg = ""
                while "EOT" not in msg:
                    msg += sock.recv(512).decode(encoding='ascii')
                print('Shuting the server down')
                sock.close()
            print("closing success")
        except :
            pass
        event.accept() #let the process die
        

        
if __name__ == '__main__':
    pg.setConfigOptions(antialias=True)
    app = QApplication(sys.argv)
    data_q = queue.Queue(1)
    exit_q = queue.Queue(2)
    ex = Gui()
    sys.exit(app.exec_())
