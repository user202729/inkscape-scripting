#!/bin/python3
import sys
from typing import Any
import tempfile
import time
from multiprocessing.connection import Client
from pathlib import Path

import IPython
from traitlets.config import Config

from inkscape_scripting.constants import connection_address, connection_family

try:
	import inkex
except ImportError:
	import sys
	sys.path.append("/usr/share/inkscape/extensions/")
	sys.path.append(str(Path("~/.config/inkscape/extensions/SimpInkScr/").expanduser()))
	import inkex

_connection: Any=None

def _pre_run_cell(info):
	"""
	https://ipython.readthedocs.io/en/stable/config/callbacks.html#pre-run-cell

	First, we click the Apply button of the extension for the client to send the data to us
	Then after getting the data, we send the data to the code in the cell
	After the code in the cell is done, we return the result to the client to print it on client's stdout
	"""
	_click_window_button()
	global _connection
	assert _connection is None
	start_attempt_time=time.time()
	while True:
		try:
			_connection=Client(address=connection_address, family=connection_family).__enter__()
		except:
			if time.time()-start_attempt_time>1:
				raise Exception("Cannot connect to the extension")
			continue
		break
	sys.argv=_connection.recv()

_xdo: Any=None


def _click_window_button():
	"""
	Switch to the window with name "Inkscape Scripting" and press "Return" to (hopefully) click the button.
	"""
	global _xdo
	if _xdo is None:
		from xdo import Xdo
		_xdo = Xdo()
	l=_xdo.search_windows(winname=b"Inkscape Scripting", only_visible=True)
	if len(l)==0: raise Exception("Extension window cannot be found. Please read the documentation.")
	if len(l)>=2: raise Exception("Multiple windows found with the extension's name?")
	old_focused_window=_xdo.get_focused_window()
	try:
		_xdo.focus_window(l[0])
		#for key in [b"Tab", b"1", b"Shift+Tab", b"Return"]:
		for key in [b"Return"]:
			_xdo.send_keysequence_window(window=l[0], keysequence=key)
	finally:
		_xdo.focus_window(old_focused_window)

_first_time_post_run_cell=True

def _post_run_cell(result):
	"""
	https://ipython.readthedocs.io/en/stable/config/callbacks.html#post-run-cell
	"""
	global _first_time_post_run_cell
	if _first_time_post_run_cell:
		_first_time_post_run_cell=False
		return
	global _connection
	if _connection is None:
		# probably some error happened in the pre-hook, ignore
		return
	assert _connection is not None
	_connection.send("")
	_connection.__exit__(None, None, None)
	_connection=None

def setup(ip)->None:
	"""
	This function is called at the beginning to setup necessary things.
	ip is the result of get_ipython().
	"""
	ip.events.register("pre_run_cell", _pre_run_cell)
	ip.events.register("post_run_cell", _post_run_cell)

def main()->None:
	c = Config()
	c.InteractiveShellApp.exec_lines = [
		'import inkscape_scripting.server',
		'inkscape_scripting.server.setup(get_ipython())',
	]
	IPython.start_ipython(config=c)

if __name__=="__main__":
	main()
