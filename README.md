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

4. From any terminal, run `inkscape_scripting_server`.

## Extra features

The additional extra features are listed here.

* Allow getting the information on the currently selected object. Inkscape extension does not allow doing this conveniently however, so pressing a key from Inkscape is needed.
* Vim integration.
* Calling `str()` or `repr()` on an object gives a representation of that object that can be used to reconstruct that object.

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

We use python-libxdo to press Enter to click the Apply button every time some code is executed.
This is a workaround for the fact that Inkscape does not allow extension that continuously runs in the background to interact with Inkscape.

I reported the bug at: https://gitlab.com/inkscape/inbox/-/issues/9741

We use AST transformer in order to keep the line numbers.

By default, IPython only display the value of the last expression in each cell, so we preserve that behavior.

/usr/lib/python3.11/site-packages/IPython/core/interactiveshell.py
has `def run_cell`

