import tempfile
from pathlib import Path

connection_address=str(Path(tempfile.gettempdir())/".inkscape_scripting_plugin_socket")
connection_family="AF_UNIX"
