from __future__	import annotations

from pathlib import Path
import tempfile
from typing import overload, Optional
from dataclasses import dataclass
import subprocess
import time

from .daemon import pause_extension_run


@dataclass
class InkscapeShell:
	"""
	A thin wrapper over a ``inkscape --shell --active-window`` process.

	Note that the extension must not be running while shell command is executing.

	Usage::

		with InkscapeShell() as shell:
			print(shell.send_command("query-all"))
	"""
	shell: Optional[subprocess.Popen]=None
	num_retries_wait_for_inkscape: int=10
	retry_wait_time: float=0.2

	def __enter__(self)->InkscapeShell:
		assert self.shell is None
		with pause_extension_run():
			for _ in range(self.num_retries_wait_for_inkscape):
				self.shell=subprocess.Popen(
						["inkscape", "--shell", "--active-window"],
						stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
						text=True, encoding='u8')
				assert self.shell.stdout is not None
				line=self.shell.stdout.readline()
				stderr_line=None
				if not line.strip():
					stderr_line=self.shell.stderr.readline()
					if stderr_line.startswith(("No active desktop to run",
								#"terminate after throwing an instance of 'Gio::DBus::Error'"
								)):
						self._stop_shell()
						continue
				assert line.startswith("Inkscape interactive shell mode"), repr((line, stderr_line))
				line=self.shell.stdout.readline()
				assert line==" Input of the form:\n", repr(line)
				line=self.shell.stdout.readline()
				prompt=self.shell.stdout.read(2)
				assert prompt=="> ", repr(prompt)
				break
			else:
				raise RuntimeError("No active window found")
		return self

	def _read_until_prompt(self)->str:
		content=""
		while True:
			assert self.shell is not None
			assert self.shell.stdout is not None
			chunk=self.shell.stdout.read(1)
			content+=chunk
			assert chunk, repr(content)
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
				#print(">> sent command", a)
				result.append(self._read_until_prompt())
				#print("<< received ", result[-1])
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
		self.shell.stderr.close()
		self.shell.wait(timeout=1)
		self.shell=None

	def __del__(self)->None:
		self._stop_shell()

