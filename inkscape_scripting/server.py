#!/bin/python3
import sys
from typing import Any
import tempfile
import time
import io
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
	import inkex
	sys.path.append(str(Path("~/.config/inkscape/extensions/SimpInkScr/").expanduser()))
	from simpinkscr import simple_inkscape_scripting
	from simpinkscr.simple_inkscape_scripting import SimpleInkscapeScripting

_connection: Any=None

class InkscapeScripting(SimpleInkscapeScripting):
	pass

_inkscape_scripting=InkscapeScripting()

def _refresh_global_variables():
	global _ip
	_ip.user_ns['svg_root'] = _inkscape_scripting.svg
	_ip.user_ns['guides'] = simple_inkscape_scripting._simple_top.get_existing_guides()
	_ip.user_ns['user_args'] = _inkscape_scripting.options.user_args
	_ip.user_ns['canvas'] = simple_inkscape_scripting._simple_top.canvas
	_ip.user_ns['metadata'] = simple_inkscape_scripting.SimpleMetadata()

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
	args=_connection.recv()[1:]
	_inkscape_scripting.parse_arguments(args)
	assert _inkscape_scripting.options.input_file is not None
	_inkscape_scripting.load_raw()
	simple_inkscape_scripting._simple_top=simple_inkscape_scripting.SimpleTopLevel(
			_inkscape_scripting.svg, _inkscape_scripting)
	_refresh_global_variables()
	# /usr/share/inkscape/extensions/inkex/base.py → def run(

_xdo: Any=None


def _click_window_button():
	"""
	Switch to the window with name "Inkscape Scripting" and press "Return" to (hopefully) click the button.
	"""
	#import traceback
	#traceback.print_stack()
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

def _post_run_cell(result):
	"""
	https://ipython.readthedocs.io/en/stable/config/callbacks.html#post-run-cell
	"""
	global _connection
	if _connection is None:
		# probably some error happened in the pre-hook, ignore
		# alternatively, at the very beginning this post-hook is called exactly once (after the cell containing exec_lines is executed)
		return
	content: bytes=b""
	try:
		if _inkscape_scripting.has_changed(None):
			with io.BytesIO() as f:
				_inkscape_scripting.save(f)
				content=f.getvalue()
	finally:  # whatever error happens, must send to unblock the client
		_connection.send(content)
		_connection.__exit__(None, None, None)
		_connection=None
		_inkscape_scripting.clean_up()

_ip=None  # global get_ipython() instance

def setup(ip)->None:
	"""
	This function is called at the beginning to setup necessary things.
	ip is the result of get_ipython().
	"""
	global _ip
	_ip=ip
	ip.events.register("pre_run_cell", _pre_run_cell)
	ip.events.register("post_run_cell", _post_run_cell)

def main()->None:
	c = Config()
	c.InteractiveShellApp.exec_lines = [
		'import inkscape_scripting.server;' +
		'inkscape_scripting.server.setup(get_ipython());' +
		'from simpinkscr import *'
	]  # for some reason this must be kept ≤ 2 lines otherwise _pre_run_cell will be triggered at the start
	IPython.start_ipython(config=c)

if __name__=="__main__":
	main()
