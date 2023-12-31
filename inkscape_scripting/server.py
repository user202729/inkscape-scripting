#!/bin/python3
import sys
from typing import Any, Optional
import tempfile
import typing
import time
import io
from functools import partial
from multiprocessing.connection import Client, Connection
from pathlib import Path

import IPython
from traitlets.config import Config

from inkscape_scripting.constants import connection_address, connection_family

__all__=["inkscape_press_keys"]  # list of everything in this module that should be visible in user's terminal

try:
	import inkex  # type: ignore
except ImportError:
	import sys
	sys.path.append("/usr/share/inkscape/extensions/")
	import inkex  # type: ignore

try:
	import simpinkscr  # type: ignore
except ImportError:
	sys.path.append(str(Path("~/.config/inkscape/extensions/SimpInkScr/").expanduser()))

from simpinkscr import simple_inkscape_scripting  # type: ignore
from simpinkscr.simple_inkscape_scripting import SimpleInkscapeScripting  # type: ignore

_connection: Optional[Connection]=None

_inkscape_scripting=SimpleInkscapeScripting()

# global get_ipython() instance
_ip=typing.cast(IPython.core.interactiveshell.InteractiveShell, None)

def _refresh_global_variables(args: list[str])->None:
	# taken from /usr/share/inkscape/extensions/inkex/base.py → def run
	global _inkscape_scripting
	_inkscape_scripting.parse_arguments(args)
	assert _inkscape_scripting.options.input_file is not None
	_inkscape_scripting.load_raw()
	simple_inkscape_scripting._simple_top=simple_inkscape_scripting.SimpleTopLevel(
			_inkscape_scripting.svg, _inkscape_scripting)
	global _ip
	_ip.user_ns['svg_root'] = _inkscape_scripting.svg
	_ip.user_ns['guides'] = simple_inkscape_scripting._simple_top.get_existing_guides()
	_ip.user_ns['user_args'] = _inkscape_scripting.options.user_args
	_ip.user_ns['canvas'] = simple_inkscape_scripting._simple_top.canvas
	_ip.user_ns['metadata'] = simple_inkscape_scripting.SimpleMetadata()
	try:
		# Inkscape 1.2+
		convert_unit = _inkscape_scripting.svg.viewport_to_unit
	except AttributeError:
		# Inkscape 1.0 and 1.1
		convert_unit = _inkscape_scripting.svg.unittouu
	for unit in ['mm', 'cm', 'pt', 'px']:
		_ip.user_ns[unit] = convert_unit('1' + unit)
	_ip.user_ns['inch'] = convert_unit('1in')  # "in" is a keyword.

def _connect_to_client()->list[str]:
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
	return _connection.recv()[1:]

def _pre_run_cell(info)->None:
	"""
	https://ipython.readthedocs.io/en/stable/config/callbacks.html#pre-run-cell

	First, we click the Apply button of the extension for the client to send the data to us
	Then after getting the data, we send the data to the code in the cell
	After the code in the cell is done, we return the result to the client to print it on client's stdout
	"""
	_click_window_button()
	args=_connect_to_client()
	_refresh_global_variables(args)

_xdo: Any=None

def _init_xdo()->Any:
	global _xdo
	if _xdo is None:
		from xdo import Xdo  # type: ignore
		_xdo=Xdo()
	return _xdo

def _send_to_window(win: int, keys: list[bytes])->None:
	"""
	Send a sequence of keys of a window, by switching focus to that window, send the keys, then switch back.
	win and keys are like python-libxdo's format.
	"""
	xdo=_init_xdo()
	old_focused_window=xdo.get_focused_window()
	try:
		xdo.focus_window(win)
		for key in keys:
			xdo.send_keysequence_window(window=win, keysequence=key)
	finally: # whatever error that might happen, must try to switch to old_focused_window
		xdo.focus_window(old_focused_window)

def _click_window_button()->None:
	"""
	Switch to the window with name "Inkscape Scripting" and press "Return" to (hopefully) click the button.
	"""
	xdo=_init_xdo()
	l=xdo.search_windows(winname=b"^Inkscape Scripting$", only_visible=True)
	if len(l)==0: raise Exception("Extension window cannot be found. Please read the documentation.")
	if len(l)>=2: raise Exception("Multiple windows found with the extension's name?")
	_send_to_window(l[0], [b"Return"])

def _post_run_cell(result)->None:
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

def _inkscape_press_keys_raw(keys: str|bytes|list[str]|list[bytes])->None:
	if isinstance(keys, (str, bytes)): keys1=[keys]
	keys=[key if isinstance(key, bytes) else key.encode("u8") for key in keys1]
	xdo=_init_xdo()
	l=xdo.search_windows(winname=b" - Inkscape$", only_visible=True)
	if len(l)==0: raise Exception("Inkscape window cannot be found.")
	if len(l)>=2: raise Exception("Multiple Inkscape windows visible, cannot determine which one is focused.")
	# we don't use _send_to_window here because at this point the "extension running" dialog is still visible for a brief moment
	# and for some reason get_focused_window() or get_focused_window_sane() will raise an XError
	# we don't really need to switch focus back to the previous window anyway because later on _pre_run_cell() will do something
	xdo.focus_window(l[0])
	for key in keys:
		xdo.send_keysequence_window(window=l[0], keysequence=key)

def inkscape_press_keys(keys: str|bytes|list[str]|list[bytes])->None:
	"""
	Press some keys on the main Inkscape GUI.

	For example::
		inkscape_press_keys("Ctrl+z")

	The format is the same as ``libxdo``.
	Importantly, the string is case-sensitive -- using ``Ctrl+Z`` instead of ``Ctrl+z`` will not work!
	"""
	# We need to do this because, while the client is running, the Inkscape window blocks input.
	_post_run_cell(None)
	time.sleep(0.3)
	_inkscape_press_keys_raw(keys)
	_pre_run_cell(None)

def setup(ip)->None:
	"""
	This function is called at the beginning to setup necessary things.
	ip is the result of get_ipython().
	"""
	global _ip
	_ip=ip
	ip.events.register("pre_run_cell", _pre_run_cell)
	ip.events.register("post_run_cell", _post_run_cell)
	from inkscape_scripting.object_repr import formatter_setup
	formatter_setup(ip)

def main()->None:
	c = Config()
	c.InteractiveShellApp.exec_lines = [
		'import inkscape_scripting.server;' +
		'inkscape_scripting.server.setup(get_ipython());' +
		'from inkscape_scripting.server import *;'
	]  # for some reason this must be kept ≤ 2 lines otherwise _pre_run_cell will be triggered at the start
	IPython.start_ipython(config=c)

if __name__=="__main__":
	main()
