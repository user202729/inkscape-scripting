"""
Handles aspects related to interacting with Inkscape window directly.

Note that the extension must not be running while we interact with the Inkscape window.

It is recommended to use .shell to interact with Inkscape instead, if feasible.
"""
from .interact_xdotool import *
