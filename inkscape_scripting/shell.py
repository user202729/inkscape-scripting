from pathlib import Path
import tempfile
from typing import overload, Optional
from dataclasses import dataclass
import subprocess

from .daemon import pause_extension_run


@dataclass
class InkscapeShell:
	"""
	A thin wrapper over a ``inkscape --shell --active-window`` process.

	Note that the extension must not be running while shell command is executing.

	Usage::

		with InkscapeShell() as shell:
			shell.send_command("select-all")
	"""
	shell: Optional[subprocess.Popen]=None

	def __enter__(self)->InkscapeShell:
		with pause_extension_run():
			self.shell=subprocess.Popen(
					["inkscape", "--shell", "--active-window"],
					stdin=subprocess.PIPE, stdout=subprocess.PIPE,
					text=True, encoding='u8')
			assert self.shell.stdout is not None
			line=self.shell.stdout.readline()
			assert line.startswith("Inkscape interactive shell mode")
			line=self.shell.stdout.readline()
			assert line==" Input of the form:\n"
			line=self.shell.stdout.readline()
			prompt=self.shell.stdout.read(2)
			assert prompt=="> "
		return self

	def _read_until_prompt(self)->str:
		content=""
		while True:
			assert self.shell is not None
			assert self.shell.stdout is not None
			chunk=self.shell.stdout.read(1)
			content+=chunk
			assert chunk, content
			if content.endswith("\n> "): break
		content=content.removesuffix("\n> ")
		return content

	@overload
	def send_command(self, s: str)->str: ...
	@overload
	def send_command(self, s: list[str])->list[str]: ...

	def send_command(self, s: str|list[str])->str|list[str]:
		# https://gitlab.com/inkscape/inbox/-/issues/9922
		t=s if isinstance(s, list) else [s]
		for a in t:
			assert "\n" not in a, (a, t)
		assert self.shell is not None
		assert self.shell.stdin is not None
		with pause_extension_run():
			result=[]
			for a in t:
				assert "\n" not in a
				(Path(tempfile.gettempdir())/"active_desktop_commands.xml").unlink(missing_ok=True)
				self.shell.stdin.write(a+"\n")
				self.shell.stdin.flush()
				result.append(self._read_until_prompt())
			if isinstance(s, str): return result[0]
			return result

	def __exit__(self, value, type, traceback)->None:
		self._stop_shell()

	def _stop_shell(self)->None:
		if self.shell is None:
			return
		assert self.shell.stdin is not None
		assert self.shell.stdout is not None
		self.shell.stdin.close()
		self.shell.stdout.close()
		self.shell.wait(timeout=1)

	def __del__(self)->None:
		self._stop_shell()

