"""
Handles the parts related to IPython interactive shell.
"""
from __future__	import annotations

import IPython
from traitlets.config import Config
import typing
from typing import Any, Optional
import ast

# global get_ipython() instance
_ip=typing.cast(IPython.core.interactiveshell.InteractiveShell, None)
from . import daemon

class _ASTTransformerDeleteEverything:
	def visit(self, node)->Any:
		assert isinstance(node, ast.Module), node
		global _ip
		_ip.ast_transformers.remove(self)
		node.body.clear()
		return node

_enable_connect_to_client: bool=True

def set_connect_to_client(enable_connect_to_client: bool)->None:
	"""
	The user can execute `set_connect_to_client(False)` so that it will run as an independent IPython shell.
	"""
	global _enable_connect_to_client
	_enable_connect_to_client=enable_connect_to_client

_units_are_setup: bool=False

_ipython_extension_run_instance: Optional[daemon.ExtensionRun]=None
"""
Stores the instance of ExtensionRun that is started by IPython implicit extension run.

Note that if the user runs an extension manually (with ExtensionRun().__enter__() for example)
and it sets global variable daemon.extension_run_instance, we must not stop it
"""

def _pre_run_cell(info)->None:
	"""
	https://ipython.readthedocs.io/en/stable/config/callbacks.html#pre-run-cell

	First, we click the Apply button of the extension for the client to send the data to us
	Then after getting the data, we send the data to the code in the cell
	After the code in the cell is done, we return the result to the client to print it on client's stdout
	"""
	if not _enable_connect_to_client: return
	global _ip, _units_are_setup, _ipython_extension_run_instance
	try:
		assert _ipython_extension_run_instance is None
		extension_run=_ipython_extension_run_instance=daemon.ExtensionRun().__enter__()
		_ip.user_ns['svg_root'] =extension_run.svg_root
		_ip.user_ns['guides']   =extension_run.guides
		_ip.user_ns['user_args']=extension_run.user_args
		_ip.user_ns['canvas']   =extension_run.canvas
		_ip.user_ns['metadata'] =extension_run.metadata

		if not _units_are_setup:
			_units_are_setup=True
			try:
				# Inkscape 1.2+
				convert_unit = extension_run.svg_root.viewport_to_unit
			except AttributeError:
				# Inkscape 1.0 and 1.1
				convert_unit = extension_run.svg_root.unittouu
			for unit in ['mm', 'cm', 'pt', 'px']:
				_ip.user_ns[unit] = convert_unit('1' + unit)
			_ip.user_ns['inch'] = convert_unit('1in')  # "in" is a keyword.

	except:
		# if an error happen, the cell will still be executed.
		# As such, we do this in order to *not* actually execute the cell
		# but we can't return an empty cell either, otherwise the error message from the pre-hook will be suppressed
		_ip.ast_transformers.append(_ASTTransformerDeleteEverything())
		raise

def _post_run_cell(result)->None:
	"""
	https://ipython.readthedocs.io/en/stable/config/callbacks.html#post-run-cell
	"""
	global _ipython_extension_run_instance
	extension_run=_ipython_extension_run_instance
	if extension_run is None:
		return
	_ipython_extension_run_instance=None
	global _ip
	try:
		extension_run.svg_root =_ip.user_ns['svg_root']
		extension_run.guides   =_ip.user_ns['guides']
		extension_run.user_args=_ip.user_ns['user_args']
		extension_run.canvas   =_ip.user_ns['canvas']
		extension_run.metadata =_ip.user_ns['metadata']
	finally:
		extension_run.__exit__(None, None, None)

def setup(ip)->None:
	"""
	This function is called at the beginning to setup necessary things.
	ip is the result of get_ipython().
	"""
	global _ip
	if _ip is ip: return
	assert _ip is None
	_ip=ip
	ip.events.register("pre_run_cell", _pre_run_cell)
	ip.events.register("post_run_cell", _post_run_cell)

	from inkscape_scripting.object_repr import formatter_setup
	formatter_setup(ip)

def main()->None:
	c = Config()
	c.InteractiveShellApp.exec_lines = [
		'import inkscape_scripting.ipython;' +
		'inkscape_scripting.ipython.setup(get_ipython());' +
		'from simpinkscr import *;' +
		'from inkscape_scripting.ipython_export import *;'
	]  # for some reason this must be kept ≤ 2 lines otherwise _pre_run_cell will be triggered at the start
	IPython.start_ipython(config=c)

if __name__=="__main__":
	main()

