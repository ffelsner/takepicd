#!/usr/bin/env python3

import argparse
import logging
import os
import socket
import sys
from select import select


def request_picture(ip, port, filename):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (ip, port)

    try:
        sock.connect(server_address)
    except socket.error:
        print("Could not connect to %s" % str(server_address))
        sys.exit(1)

    sock.sendall('TAKE_PICTURE'.encode()) # python3
    #sock.sendall('TAKE_PICTURE') # python2
    log.info("TXed TAKE_PICTURE to takepicd")

    sock.setblocking(0)
    timeout = 30

    with open(filename, 'wb') as fh:
        while True:
            ready = select([sock], [], [], timeout)

            if ready[0]:
                data = sock.recv(4096)

                if data:
                    fh.write(data)
                else:
                    break
            else:
                log.warning("did not receive a response within %s seconds" % timeout)
                break

    log.info("RXed %s from takepicd" % filename)
    sock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="takepicclient: connect to takepicd to grab a picture")
    parser.add_argument('--ip', type=str, default='0.0.0.0')
    parser.add_argument('--port', type=int, default=10000)
    parser.add_argument('--filename', type=str, default='image.png')
    parser_args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')
    log = logging.getLogger(__name__)

    if not parser_args.filename.endswith('.png'):
        print("ERROR: --filename must end with .png")
        sys.exit(1)

    request_picture(parser_args.ip, parser_args.port, parser_args.filename)
