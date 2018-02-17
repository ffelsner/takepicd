#!/usr/bin/env python2

import argparse
import cv2
import logging
import os
import random
import signal
import socket
import string
import sys
from daemon import DaemonContext
from threading import Event

SCRATCHPAD_DIR = '/tmp/takepicd/'


def open_tcp_socket(address='0.0.0.0', port=10000):
    """
    open/return a TCP socket
    """
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_socket.bind((address, port))
    tcp_socket.listen(1)

    log.info("TCP socket opened on (%s, %s)" % (address, port))
    return tcp_socket


def get_random_string(length=6):
    """
    Return a random string 'length' characters long
    """
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(length))


class TakePicDaemon(object):

    def __init__(self, ip, port):
        self.shutdown_event = Event()
        self.ip = ip
        self.port = port

    def __str__(self):
        return 'TakePicDaemon'

    def signal_handler(self, signal, frame):
        log.info("received SIGINT or SIGTERM")
        self.shutdown_event.set()

    def main(self):
        caught_exception = False

        # Log the process ID upon start-up.
        pid = os.getpid()
        log.info('takepicd started with PID %s.' % pid)

        tcp_socket = open_tcp_socket(self.ip, self.port)
        camera = cv2.VideoCapture(0)

        while True:

            # Wrap everything else in try/except so that we can log errors
            # and exit cleanly
            try:
                if self.shutdown_event.is_set():
                    log.info("Shutdown signal RXed.  Breaking out of the loop.")
                    break

                try:
                    (connection, _) = tcp_socket.accept()
                except socket.error as e:
                    if isinstance(e.args, tuple) and e[0] == 4:
                        # 4 is 'Interrupted system call', a.k.a. SIGINT.
                        # The user wants to stop takepicd.
                        log.info("socket.accept() caught signal, starting shutdown")
                        self.shutdown_event.set()
                        continue
                    else:
                        log.info("takepicd socket %s hit an error\n%s" % (server_address, e))
                        tcp_socket.close()
                        tcp_socket = open_tcp_socket()
                        continue

                # RX the request from the client
                data = connection.recv(4096)

                # If the client is using python2 data will be a str but if they
                # are using python3 data will be encoded and must be decoded to
                # a str
                if not isinstance(data, str):
                    data = data.decode()

                if data == 'TAKE_PICTURE':
                    log.info("RXed %s" % data)
                    (retval, img) = camera.read()
                    # dwalton
                    png_filename = os.path.join(SCRATCHPAD_DIR, get_random_string() + '.png')
                    cv2.imwrite(png_filename, img)

                    with open(png_filename, 'rb') as fh:
                        line = fh.read(4096)

                        while line:
                            connection.send(line)
                            line = fh.read(4096)

                    connection.close()
                    os.unlink(png_filename)
                    log.info("TXed %s" % png_filename)
                else:
                    log.warning("RXed %s (not supported)" % data)

            except Exception as e:
                log.exception(e)
                caught_exception = True
                break

        log.info('takepicd is stopping with PID %s' % pid)
        del(camera)

        if tcp_socket:
            tcp_socket.close()
            tcp_socket = None

        if caught_exception:
            sys.exit(1)
        else:
            sys.exit(0)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="takepidc: daemon that takes webcam pics via OpenCV")
    parser.add_argument('-d', '--daemon', help='run as a daemon', action='store_true', default=False)
    parser.add_argument('--ip', type=str, default='0.0.0.0')
    parser.add_argument('--port', type=int, default=10000)
    parser_args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s: %(message)s')
    log = logging.getLogger(__name__)
    logging.addLevelName(logging.ERROR, "\033[91m  %s\033[0m" % logging.getLevelName(logging.ERROR))
    logging.addLevelName(logging.WARNING, "\033[91m%s\033[0m" % logging.getLevelName(logging.WARNING))

    if not os.path.exists(SCRATCHPAD_DIR):
        os.makedirs(SCRATCHPAD_DIR, mode=0755)

    tpd = TakePicDaemon(parser_args.ip, parser_args.port)

    if parser_args.daemon:
        context = DaemonContext(
            working_directory=SCRATCHPAD_DIR,
            signal_map={
                signal.SIGTERM: tpd.signal_handler,
                signal.SIGINT: tpd.signal_handler,
            }
        )

        context.open()
        with context:
            tpd.main()

    else:
        signal.signal(signal.SIGINT, tpd.signal_handler)
        signal.signal(signal.SIGTERM, tpd.signal_handler)
        tpd.main()
