# inkscape-scripting

## What is this?

This is an improvement on top of Scott Pakin's plugin [Simple Inkscape Scripting (SimpInkScr)](https://github.com/spakin/SimpInkScr):

* Instead of the clunky Inkscape text box interface to enter code, we use the IPython shell (thus features such as tab completion is supported)
* In order to speed up the execution, we don't import `inkex` module every time; instead, the extension file is just a tiny Python script that connects to the IPython shell.

Other extra features are listed below.

## How to use?

1. Install the extension. Refer to [documentation](https://inkscape.org/gallery/=extension/) for instruction.
2. Open Inkscape.
3. In the "Extensions" menu of Inkscape (accessible through Alt+N) click "Inkscape Scripting..."

    This should open a window titled "Inkscape Scripting" with a "Cancel" and an "Apply" button. Leave it visible.

4. From any terminal, run `inkscape_scripting_daemon`.
5. An IPython interactive shell should appear.

    Just like in SimpInkScr, as an initial test, try executing
    ```python
    circle((100, 100), 50)
    ```
    This should create a black circle of radius 50 at position (100, 100).

## Shared features

Refer to https://github.com/spakin/SimpInkScr/wiki/Quick-reference for a list of supported features.

Note: Modifying the global variable `guides` will modify the list of guides, as usual.

## Extra features

The additional extra features are listed here.

* **Pretty-print objects:** Try executing `svg_root` in the console, it will pretty-print the SVG structure.
* **Meaningful string representation**: Calling `str()` or `repr()` on an object gives a representation of that object that can be used to reconstruct that object.
* **`inkscape_press_keys()`:** Press buttons on the main Inkscape GUI by e.g. `inkscape_press_keys("Ctrl+z")`.
* Allow getting the information on the currently selected object. Inkscape extension does not allow doing this conveniently however, so pressing a key from Inkscape is needed.

## Note

While any cell is running, Inkscape main window blocks input --- if you want to interact with the main window, or otherwise (e.g. launch a `inkscape --active-window --shell` shell), you need `pause_extension_run` context manager.

Yet another way is to execute `set_connect_to_client(False)` temporarily.

Refer to its source code for details how to use it.

`inkscape_press_keys` function does this automatically under the hood.

## Python API: `ExtensionRun` object

The extension and shell part can be run standalone as well.

Example:
```python
from inkscape_scripting.daemon import ExtensionRun
from simpinkscr.simple_inkscape_scripting import all_shapes
with ExtensionRun() as a:
    print(all_shapes())
    print(len(a.guides))
    a.guides=[]
```

The property `guides` above has the same meaning as that in the `SimpInkScr` plugin.
Nevertheless, you can still run at most one extension at once.

## Python API: Shell mode

This plugin can interact with Inkscape in two different ways: through `inkscape --shell --active-window` feature, or through the extension.

The mode above uses the extension. Using shell mode is also possible.

Example:
```python
with InkscapeShell() as shell:
    print(shell.send_command("query-all"))
```

## Wishlist

* Macro recording.
* Ability to call other extensions programmatically.
* In particular: Import TikZ.
* Run command in shell mode.

* Allow inserting a TikZ figure, and bidirectional communication.

    Well, look at source code of `tex4ht` I suppose...

    `tex4ht` works by using TeX to compile `.tex` to `.dvi`, then `tex4ht` and `t4ht` are used to finish up.

    The `htlatex` executable wraps both steps.

* `dvisvgm --no-fonts` I suppose. Apparently Inkscape doesn't handle fonts well.
* Actually Inkscape itself can also convert.

## Common error messages

> Extension window cannot be found. Please read the documentation.

Refer to step 3 in "How to use" section.

> Cannot accept connection from server!
>
> Note that you must not click "Apply" button manually.

If you accidentally clicked the "Apply" button manually, just click OK in the dialog.

Refer to step 4 in "How to use" section for the proper way how to use the extension.

> Cannot connect to the extension

You probably accidentally focus the "Cancel" button instead of the "Apply" button. Just re-open the extension dialog.

## Development note

Relevant issue (`inkscape --shell` render extension crashes): https://gitlab.com/inkscape/inkscape/-/issues/3653

We use python-libxdo to press Enter to click the Apply button every time some code is executed.
This is a workaround for the fact that Inkscape does not allow extension that continuously runs in the background to interact with Inkscape.

I reported the bug at: https://gitlab.com/inkscape/inbox/-/issues/9741

We use AST transformer in order to keep the line numbers.

By default, IPython only display the value of the last expression in each cell, so we preserve that behavior.

/usr/lib/python3.11/site-packages/IPython/core/interactiveshell.py
has `def run_cell`

