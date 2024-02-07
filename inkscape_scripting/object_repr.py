"""
Implements logic to pretty-print objects.
"""
from __future__	import annotations

from typing import Any

from lxml import etree

import inkex  # type: ignore

from simpinkscr.simple_inkscape_scripting import SimpleObject  # type: ignore
from simpinkscr.svg_to_simp_ink_script import SvgToPythonScript  # type: ignore

_svg_to_python_script=SvgToPythonScript()

def _unregister_gettext():
	"""
	This is needed so `_` can be used for last-output in interactive shell.

	It must be called after the `SvgToPythonScript` object above is created.
	"""
	import builtins
	try:
		del builtins._
	except AttributeError:
		pass

_unregister_gettext()

_for_type_registers=[]

def _for_type(t):
	def _(g):
		_for_type_registers.append((t, g))
		return g
	return _

@_for_type(etree.ElementBase)
def format_element_base(o, p, cycle)->None:
	"""
	Used to pretty-print `svg_root` etc. in IPython.
	"""
	try:
		content=etree.tostring(o, pretty_print=True)
	except:
		p.text(repr(o))
		return
	p.text(content.decode("u8", errors="replace"))
	if o.TAG=="svg":
		p.text("\n[\n")
		pretty_print_svg_root(o, p)
		p.text("]")

def pretty_print_svg_root(svg_root, p)->None:
	_svg_to_python_script.svg=svg_root
	code=_svg_to_python_script.convert_all_shapes()
	_svg_to_python_script.find_dependencies(code)
	code=_svg_to_python_script.sort_statement_forest(code)
	for stmt in code:
		if stmt.delete_if_unused and not stmt.need_var_name:
			continue
		p.text(str(stmt))
		p.breakable(";")

def _repr_inkscape_object(node)->Any:
	"""
	node is of type inkex.elements._base.BaseElement (e.g. inkex.Rectangle)
	return a SvgToPythonScript.Statement object.
	"""
	# copied from SimpInkScr/simpinkscr/svg_to_simp_ink_script.py → convert_all_shapes
	if isinstance(node, inkex.Circle):
		return _svg_to_python_script.convert_circle(node)
	elif isinstance(node, inkex.Ellipse):
		return _svg_to_python_script.convert_ellipse(node)
	elif isinstance(node, inkex.Rectangle):
		return _svg_to_python_script.convert_rectangle(node)
	elif isinstance(node, inkex.Line):
		return _svg_to_python_script.convert_line(node)
	elif isinstance(node, inkex.Polyline):
		return _svg_to_python_script.convert_poly(node, 'polyline')
	elif isinstance(node, inkex.Polygon):
		return _svg_to_python_script.convert_poly(node, 'polygon')
	elif isinstance(node, inkex.PathElement):
		return _svg_to_python_script.convert_path(node)
	elif isinstance(node, inkex.TextElement):
		return _svg_to_python_script.convert_text(node)
	elif isinstance(node, inkex.Image):
		return _svg_to_python_script.convert_image(node)
	elif isinstance(node, inkex.ForeignObject):
		return _svg_to_python_script.convert_foreign(node)
	elif isinstance(node, inkex.Use):
		return _svg_to_python_script.convert_clone(node)
	elif isinstance(node, inkex.Group):
		return _svg_to_python_script.convert_group(node)
	elif isinstance(node, inkex.Filter):
		return _svg_to_python_script.convert_filter(node)
	elif isinstance(node, inkex.LinearGradient):
		return _svg_to_python_script.convert_linear_gradient(node)
	elif isinstance(node, inkex.RadialGradient):
		return _svg_to_python_script.convert_radial_gradient(node)
	elif isinstance(node, inkex.ClipPath):
		return _svg_to_python_script.convert_clip_path(node)
	elif hasattr(inkex, 'Mask') and isinstance(node, inkex.Mask):
		return _svg_to_python_script.convert_mask(node)  # Inkscape 1.2+
	elif isinstance(node, inkex.Marker):
		return _svg_to_python_script.convert_marker(node)
	elif isinstance(node, inkex.Anchor):
		return _svg_to_python_script.convert_hyperlink(node)
	elif isinstance(node, inkex.PathEffect):
		return _svg_to_python_script.convert_path_effect(node)
	elif isinstance(node, inkex.Guide):
		return _svg_to_python_script.convert_guide(node)
	else:
		raise RuntimeError('Internal error converting %s' % repr(node))

@_for_type(SimpleObject)
def format_simple_object(o, p, cycle)->None:
	for i, stmt in enumerate(_repr_inkscape_object(o.get_inkex_object()).code):
		if i!=0: p.breakable(";")
		p.text(str(stmt))

def formatter_setup(ip):
	formatter=ip.display_formatter.formatters['text/plain']
	for t, g in _for_type_registers:
		formatter.for_type(t, g)
