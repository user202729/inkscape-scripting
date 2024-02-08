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
from .interact import click_extension_window_button

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
		with _global_extension_run_instance:
			assert extension_run_instance is not None
			yield extension_run_instance
			# note that if pause_extension_run() is nested inside require_extension_run then the instance may be modified halfway
	else:
		yield extension_run_instance

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

			click_extension_window_button()
			args, self._connection=self._stack.enter_context(_connect_to_client())
			del args[0]

			# taken from /usr/share/inkscape/extensions/inkex/base.py → def run
			self._sis_instance=_sis_instance=SimpleInkscapeScripting()
			self._stack.push(lambda exc_type, exc_value, traceback: _sis_instance.clean_up())
			_sis_instance.parse_arguments(args)
			assert _sis_instance.options.input_file is not None
			_sis_instance.load_raw()

			# construct the object. Copied from SimpInkScr/simpinkscr/simple_inkscape_scripting.py → def effect
			self._stack.enter_context(_setup_global_simple_top(
				simple_inkscape_scripting.SimpleTopLevel(_sis_instance.svg, _sis_instance)
				))
			simple_inkscape_scripting._simple_top.simple_pages=simple_inkscape_scripting._simple_top.get_existing_pages()

			self._stack.enter_context(self._set_properties_to_none())
			self.svg_root = _sis_instance.svg
			self.guides = simple_inkscape_scripting._simple_top.get_existing_guides()
			self.user_args = _sis_instance.options.user_args
			self.canvas = simple_inkscape_scripting._simple_top.canvas
			self.metadata = simple_inkscape_scripting.SimpleMetadata()

			self._stack=self._stack.pop_all()
		return self

	@contextmanager
	def _set_properties_to_none(self)->Generator:
		yield
		self.svg_root=None
		self.guides=None
		self.user_args=None
		self.canvas=None
		self.metadata=None

	def __exit__(self, exc_type, exc_value, traceback)->None:
		with self._stack:
			assert self._connection is not None
			send=self._connection
			self._connection=None
			simple_inkscape_scripting._simple_top.replace_all_guides(self.guides)
			if self._sis_instance.has_changed(None):
				with io.BytesIO() as f:
					self._sis_instance.save(f)
					send(f.getvalue())


extension_run_instance: Optional[ExtensionRun]=None
"""
The global instance of the running ExtensionRun object.

Code other than :func:`_register_extension_run_object_globally` must not modify this variable.
"""

class _GlobalExtensionRun:
	"""
	A class that is a thin wrapper over the current extension_run_instance object.
	"""
	def __enter__(self)->ExtensionRun:
		assert extension_run_instance is None
		return ExtensionRun().__enter__()
	def __exit__(self, exc_type, exc_value, traceback)->None:
		assert extension_run_instance is not None
		extension_run_instance.__exit__(exc_type, exc_value, traceback)
	# note that extension_run_instance may have changed between __enter__ and __exit__

_global_extension_run_instance=_GlobalExtensionRun()

@contextmanager
def _register_extension_run_object_globally(e: ExtensionRun)->Generator:
	global extension_run_instance
	assert extension_run_instance is None
	extension_run_instance=e
	try: yield
	finally:
		assert extension_run_instance is e
		extension_run_instance=None

@contextmanager
def _setup_global_simple_top(simple_top)->Generator:
	assert simple_inkscape_scripting._simple_top is None
	simple_inkscape_scripting._simple_top=simple_top
	try: yield
	finally: simple_inkscape_scripting._simple_top=None

