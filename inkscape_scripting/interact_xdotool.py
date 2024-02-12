from __future__	import annotations

from typing import Any
import subprocess
import time

from . import daemon


def _focus_window(win: int)->None:
	subprocess.run(["xdotool", "windowfocus", str(win)], check=True)

def _search_windows(s: str)->list[int]:
	# older versions of xdotool has a bug https://github.com/jordansissel/xdotool/pull/335
	# we no longer need the bug fix now, so the fix is removed
	process=subprocess.run(["xdotool", "search", "--name", s], stdout=subprocess.PIPE, check=True)
	return [int(x) for x in process.stdout.split()]

def _execute_in_window(win: int, cmd: list[str])->None:
	"""
	Send a sequence of keys of a window, by switching focus to that window, send the keys, then switch back.
	win and keys are like python-libxdo's format.
	"""
	old_focused_window=int(subprocess.run(["xdotool", "getwindowfocus"], stdout=subprocess.PIPE, check=True).stdout)
	try:
		_focus_window(win)
		subprocess.run(cmd, check=True)
	finally: # whatever error that might happen, must try to switch to old_focused_window
		_focus_window(old_focused_window)

def _send_to_window(win: int, keys: list[bytes])->None:
	_execute_in_window(win, ["xdotool", "key", "--clearmodifiers", "--window", str(win)]+[key.decode('u8') for key in keys])

def main_inkscape_window_id()->int:
	l=_search_windows(" - Inkscape$")
	if len(l)==0: raise Exception("Inkscape window cannot be found.")
	if len(l)>=2: raise Exception("Multiple Inkscape windows visible, cannot determine which one is focused.")
	return l[0]

def _inkscape_press_keys_raw(keys: str|bytes|list[str]|list[bytes])->None:
	if isinstance(keys, (str, bytes)): keys1=[keys]
	keys=[key.decode('u8') if isinstance(key, bytes) else key for key in keys1]
	win=main_inkscape_window_id()
	# we don't use _send_to_window here because at this point the "extension running" dialog is still visible for a brief moment
	# and for some reason get_focused_window() or get_focused_window_sane() will raise an XError
	# we don't really need to switch focus back to the previous window anyway because later on _pre_run_cell() will do something
	_focus_window(win)
	for key in keys:
		subprocess.run(["xdotool", "key", "--window", str(win)]+keys, check=True)

def inkscape_press_keys(keys: str|bytes|list[str]|list[bytes])->None:
	"""
	Press some keys on the main Inkscape GUI.

	For example::
		inkscape_press_keys("Ctrl+z")

	The format is the same as ``xdotool``.
	Importantly, the string is case-sensitive -- using ``Ctrl+Z`` instead of ``Ctrl+z`` will not work!
	"""
	with daemon.pause_extension_run():
		_inkscape_press_keys_raw(keys)

def click_extension_window_button()->None:
	"""
	Switch to the window with name "Inkscape Scripting" and press "Return" to (hopefully) click the button.
	"""
	l=_search_windows("^Inkscape Scripting$")
	if len(l)==0: raise Exception("Extension window cannot be found. Please read the documentation.")
	if len(l)>=2: raise Exception("Multiple windows found with the extension's name?")
	_execute_in_window(l[0], ["xdotool", "keyup", "--clearmodifiers", "Return", "key", "--clearmodifiers", "Return"])

