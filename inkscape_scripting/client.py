#!/bin/python3
"""
Handles the client half that is related to the Inkscape extension.
This part does not execute any code (it must not even import inkex in order to save time).
Its only role is to send the code over to the daemon.
"""
#import time
#start_time=time.time()

import sys
import os
from multiprocessing.connection import Listener
from pathlib import Path
import threading

from inkscape_scripting.constants import connection_address, connection_family

def _timeout_error()->None:
	sys.stderr.write(
			'Cannot accept connection from server!\n'
			'Note that you must not click "Apply" button manually.\n')
	sys.stderr.flush()  # mostly redundant
	os._exit(1)  # need this to kill all threads

def _connect(retries: int)->None:
	if retries==2:
		raise RuntimeError("Retried too many times unsuccessfully")
	timer=threading.Timer(1, _timeout_error)
	timer.start()
	try:
		with Listener(address=connection_address, family=connection_family) as listener:
			with listener.accept() as conn:
				timer.cancel()
				conn.send(sys.argv)
				data=conn.recv()
				sys.stdout.buffer.write(data)
				return
	except OSError:
		Path(connection_address).unlink()
	timer.cancel()
	_connect(retries=retries+1)


def main()->None:
	_connect(retries=0)

if __name__=="__main__":
	main()
	#sys.stderr.write(f"Time taken: {time.time()-start_time:.3f}\n")
