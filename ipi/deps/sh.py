from pathlib import Path

from ..bootstrap.tiers import BootstrapTier

tier = BootstrapTier.bootstrap

try:
	from sh import Command
except ImportError:
	import subprocess
	import sys
	import typing

	from ..utils.WithEnv import WithEnv

	EnvT = typing.Optional[typing.Mapping[str, str]]

	class Command:
		__slots__ = ("args", "env", "cwd")

		def __init__(self, *args: typing.Iterable[typing.Union[str, Path]], _cwd: Path = None, _env: EnvT = None):
			self.args = tuple(args)
			if _env is None:
				_env = {}
			self.env = _env
			self.cwd = _cwd

		def bake(self, *args, _env: EnvT = None, _fg: bool = False, _cwd: Path = None, **kwargs):
			if kwargs:
				raise NotImplementedError("For kwargs you need to bootstrap this tool.")

			return self.__class__(*(self.args + tuple(args)), _env=self.env | _env if _env else self.env, _cwd=_cwd if _cwd is not None else self.cwd)

		def __call__(self, *args, _env: EnvT = None, _fg: bool = False, _in: str = None, _cwd: Path = None, **kwargs):
			o = self.bake(*args, _env=_env, _fg=_fg, _cwd=_cwd, **kwargs)

			# stdout=subprocess.PIPE, stderr=subprocess.PIPE
			input = _in
			if isinstance(input, str):
				input = input.encode("utf-8")

			res = subprocess.run(tuple(str(el) for el in o.args), cwd=o.cwd, env=o.env, input=input, check=False, capture_output=True, shell=False)
			sys.stdout.flush()
			sys.stderr.flush()

			sys.stdout.buffer.write(res.stdout)
			sys.stdout.flush()
			sys.stderr.buffer.write(res.stderr)
			sys.stderr.flush()

			res.check_returncode()

			return res.stdout.decode("utf-8")

else:
	tier = BootstrapTier.full
