#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  photonServerDeamon.py
#  
#  Copyright 2018 Arthur Luciani <arthur@arthur-X550JD>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  
import sys
import select
import socket
from os import system
from time import sleep

PORT = 18888
STIMEOUT = 0.020

def main(args):
    """
    p
    """
    exitSig = False
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('', PORT))
    server_socket.listen(1)
    print(">> Listening on port {0}".format(PORT), " : waiting for server startup")
    read_list = [server_socket]
    while not exitSig:
        readable, writable, errored = select.select(read_list, [], [], STIMEOUT)
        for s in readable :
            if s is read_list[0] :
                conn, addr = s.accept()
                print(">> Connected to ", addr, " accepted")
                sleep(1)
                conn.close()
                server_socket.close()
                print(">> Connections closed. Starting server.")
                sleep(1)
                system("/usr/bin/python3 /home/arthur/Documents/Stage\ 2018/service/wserialserv_v2.py")
                sleep(2)
                print(">> Server closed. Resuming startup signal listening.")
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('', PORT))
                server_socket.listen(1)
                read_list = [server_socket]
                print(">> Listening on port {0}".format(PORT), " : waiting for server startup")
                
    for s in read_list:
        s.close()
        print(">> Connection", s, "closed")
        read_list.remove(s)   
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
