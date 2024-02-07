"""
Handles the daemon half that is related to the Inkscape-side extension.
(This is continuously running, and all code are executed in this side's environment.)
"""
from __future__	import annotations

import sys
from typing import Any, Optional, Generator, Callable
import dataclasses
from dataclasses import dataclass
import tempfile
import typing
import time
import io
from contextlib import contextmanager, ExitStack
from functools import partial
from multiprocessing.connection import Client
from pathlib import Path
import subprocess

from .constants import connection_address, connection_family
from .interact import _init_xdo, _send_to_window

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

@contextmanager
def pause_extension_run()->Generator:
	"""
	While the client is running, the Inkscape window blocks input.

	So, if you want to interact with Inkscape window, you need this context manager.

	This can be nested, but it's not thread-safe.

	Usage::

		with break_extension_run():
			...  # Inkscape main window can be interacted with here
			with break_extension_run():
				...  # this nested layer is no-op

	..seealso:: :func:`inkscape_press_keys`.
	"""
	global extension_run_instance
	if extension_run_instance is None:
		yield
	else:
		extension_run_instance.__exit__(None, None, None)
		time.sleep(0.3)
		try:
			yield
		finally:
			ExtensionRun().__enter__()

@contextmanager
def require_extension_run()->Generator:
	"""
	When the extension is not running, runs it.
	"""
	global extension_run_instance
	if extension_run_instance is None:
		with ExtensionRun().__enter__() as instance:
			yield
			assert instance is extension_run_instance
	else:
		yield

def _click_window_button()->None:
	"""
	Switch to the window with name "Inkscape Scripting" and press "Return" to (hopefully) click the button.
	"""
	xdo=_init_xdo()
	l=xdo.search_windows(winname=b"^Inkscape Scripting$", only_visible=True)
	# xdotool search --name '^Inkscape Scripting$'
	if len(l)==0: raise Exception("Extension window cannot be found. Please read the documentation.")
	if len(l)>=2: raise Exception("Multiple windows found with the extension's name?")
	_send_to_window(l[0], [b"Return"])

@contextmanager
def _connect_to_client()->Generator[tuple[Any, Callable[[Any], None]], None, None]:
	"""
	Connect to the client.

	Example use::

		with _connect_to_client() as argv, f:
			f(content_to_be_sent)

	We allow receiving exactly one value, and send back exactly one value.

	There are two situations which may happen:
	* If the client has not started a (listening) server yet, the __enter__ will fail immediately. In that case, we retry.
	* If we retry too many sometimes, we give up and raise the error.
	"""
	start_attempt_time=time.time()
	with ExitStack() as stack:
		while True:
			try:
				connection=stack.enter_context(Client(address=connection_address, family=connection_family))
				break
			except: # cannot connect
				if time.time()-start_attempt_time>1:
					# waited for too long
					raise Exception("Cannot connect to the extension")
				continue  # retry
		received_value=connection.recv()
		sending_value=b""
		def send(b: bytes):
			nonlocal sending_value
			sending_value=b
		try:
			yield received_value, send
		finally:
			# whatever happens, we must send this to unblock the client
			connection.send(sending_value)

@dataclass
class ExtensionRun:
	"""
	Represents a single run of the Inkscape extension.

	There cannot be more than one extension running at a time, so this object should be singleton.

	Usage::
		with ExtensionRun() as a:
			print(len(a.guides))
			a.guides=[]
	"""

	svg_root: Any=None
	guides: Any=None
	user_args: Any=None
	canvas: Any=None
	metadata: Any=None

	_connection: Any=None
	_stack: ExitStack=dataclasses.field(default_factory=ExitStack)

	def __enter__(self)->ExtensionRun:
		with self._stack:
			assert self._connection is None
			self._stack.enter_context(_register_extension_run_object_globally(self))
			self._stack.enter_context(_cleanup_global_simple_inkscape_scripting_object())
			_click_window_button()
			args, self._connection=self._stack.enter_context(_connect_to_client())
			del args[0]
			self._refresh_global_variables(args)
			self._stack=self._stack.pop_all()
		return self

	def __exit__(self, exc_type, exc_value, traceback)->None:
		with self._stack:
			assert self._connection is not None
			send=self._connection
			self._connection=None
			simple_inkscape_scripting._simple_top.replace_all_guides(self.guides)
			if _simple_inkscape_scripting.has_changed(None):
				with io.BytesIO() as f:
					_simple_inkscape_scripting.save(f)
					send(f.getvalue())

	def _refresh_global_variables(self, args: list[str])->None:
		# taken from /usr/share/inkscape/extensions/inkex/base.py → def run
		global _simple_inkscape_scripting
		_simple_inkscape_scripting.parse_arguments(args)
		assert _simple_inkscape_scripting.options.input_file is not None
		_simple_inkscape_scripting.load_raw()
		# construct the object. copied from  SimpInkScr/simpinkscr/simple_inkscape_scripting.py → def effect
		simple_inkscape_scripting._simple_top=simple_inkscape_scripting.SimpleTopLevel(
				_simple_inkscape_scripting.svg, _simple_inkscape_scripting)
		simple_inkscape_scripting._simple_top.simple_pages=simple_inkscape_scripting._simple_top.get_existing_pages()
		self.svg_root = _simple_inkscape_scripting.svg
		self.guides = simple_inkscape_scripting._simple_top.get_existing_guides()
		self.user_args = _simple_inkscape_scripting.options.user_args
		self.canvas = simple_inkscape_scripting._simple_top.canvas
		self.metadata = simple_inkscape_scripting.SimpleMetadata()

extension_run_instance: Optional[ExtensionRun]=None
"""
The global instance of the running ExtensionRun object.

Code other than :func:`_register_extension_run_object_globally` must not modify this variable.
"""

@contextmanager
def _register_extension_run_object_globally(e: ExtensionRun)->Generator:
	global extension_run_instance
	assert extension_run_instance is None
	extension_run_instance=e
	yield
	assert extension_run_instance is e
	extension_run_instance=None

_simple_inkscape_scripting=SimpleInkscapeScripting()

@contextmanager
def _cleanup_global_simple_inkscape_scripting_object():
	yield
	_simple_inkscape_scripting.clean_up()
