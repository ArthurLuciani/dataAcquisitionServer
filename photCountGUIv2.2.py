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
import serpy as sp
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
        self.conn = sp.Connection(auto_restart=True).connect(HOST, PORT)
        self.conn.sendData(b'GIVEDATA') #asks the server to give to chunks of data in advance
        self.conn.sendData(b'GIVEDATA')
        
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
        self.lbl2.setText("Estimated Time : "+str(int(int(text)*BUF*4e-6))+" s")
        self.lbl2.adjustSize()
        self.lbl3.setText("Weight of the acquisition : "+str(int(int(text)*BUF/1000))+" kB")
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
            self.conn.sendData(b'GIVEDATA')
            store[i*BUF:(i+1)*BUF] = np.frombuffer(self.conn.getData(),dtype=np.ubyte)
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
        if self.conn.isDataAvailable(): #retrieves the new number of photons
            self.data = np.frombuffer(self.conn.getData(),dtype=np.ubyte)
            self.y[-1] = self.nbPhoton(self.data, old_data)
            self.lcd.display(int(self.y[-1]/(4e-6*BUF)))
            self.conn.sendData(b'GIVEDATA') #asks for more data
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
        self.timer.stop()
        try :
            if reply == QMessageBox.Yes:
                # connects to the server to send the shutdown signal
                self.conn.sendData('KTHXBYE!'.encode('ascii'))
                self.conn.disableRestart()
                sleep(0.2)
            self.conn.close()
            print("closing success")
        except :
            pass
        event.accept() #let the process die
        

        
if __name__ == '__main__':
    pg.setConfigOptions(antialias=True)
    app = QApplication(sys.argv)
    ex = Gui()
    sys.exit(app.exec_())
