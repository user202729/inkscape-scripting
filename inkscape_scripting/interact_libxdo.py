"""
Old implementation of interact() using libxdo. Faster but currently buggy.
"""
from __future__	import annotations

from typing import Any
import subprocess
from . import daemon

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
		#xdo.clear_active_modifiers(window=win)  # not implemented
		#for key in keys:
		#	xdo.send_keysequence_window(window=win, keysequence=key)
		subprocess.run(["xdotool", "key", "--clearmodifiers", "--window", str(win)]+[key.decode('u8') for key in keys], check=True)
	finally: # whatever error that might happen, must try to switch to old_focused_window
		xdo.focus_window(old_focused_window)

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
	with daemon.pause_extension_run():
		_inkscape_press_keys_raw(keys)

def click_extension_window_button()->None:
	"""
	Switch to the window with name "Inkscape Scripting" and press "Return" to (hopefully) click the button.
	"""
	xdo=_init_xdo()
	l=xdo.search_windows(winname=b"^Inkscape Scripting$", only_visible=True)
	# xdotool search --name '^Inkscape Scripting$'
	if len(l)==0: raise Exception("Extension window cannot be found. Please read the documentation.")
	if len(l)>=2: raise Exception("Multiple windows found with the extension's name?")
	#_send_to_window(l[0], [b"Return"]) #TODO
