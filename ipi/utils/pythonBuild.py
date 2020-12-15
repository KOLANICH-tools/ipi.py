import sys
from pathlib import Path

from .CLICookie import CLICookie
from .json import json
from .WithPythonPath import WithPythonPath


def buildWheelUsingPEP517(packageDir: Path, outDir: Path, pythonPath=()):
	print("buildWheelUsingPEP517 pythonPath", pythonPath)
	with WithPythonPath(*pythonPath):
		from pyproject_hooks import BuildBackendHookCaller

	tomlFile = packageDir / "pyproject.toml"
	if tomlFile.is_file():
		try:
			import tomllib
		except ImportError:
			print("pythonPath", pythonPath)
			with WithPythonPath(*pythonPath):
				import tomli as tomllib

		ppt = tomllib.loads(tomlFile.read_text())
		bs = ppt.get("build-system", {})
		try:
			build_backend = bs["build-backend"]
		except KeyError:
			if (packageDir / "setup.py").is_file():
				build_backend = "setuptools.build_meta"
				print("build-backend was not specified in " + str(tomlFile) + " using `" + build_backend + "`, since `setup.py` is present")
			else:
				raise

		backend_path = bs.get("backend-path")
	else:
		build_backend = "setuptools.build_meta"
		backend_path = None

	hooks = BuildBackendHookCaller(packageDir, build_backend=build_backend, backend_path=backend_path)

	with WithPythonPath(packageDir, *pythonPath):
		return outDir / hooks.build_wheel(outDir, {})


class RemotePep517:
	__slots__ = ("cookie",)

	def __init__(self):
		self.cookie = CLICookie()

	def serializeArgs(self, packageDir: Path, outDir: Path):
		return json.dumps({"pkg": str(packageDir.absolute().resolve()), "outDir": str(outDir.absolute().resolve()), "cookie": self.cookie.toSerializeable()})

	def processOutput(self, stdOutContents: str):
		data, preCookie, postCookie = self.cookie.unwrap(stdOutContents)
		res = json.loads(data)

		sys.stdout.write(preCookie)
		sys.stdout.write(postCookie)

		try:
			return Path(res["wheel"])
		except KeyError:
			raise RuntimeError("Error building wheel", res["error"])


def _deserializeArgs(jStr: str):
	j = json.loads(jStr)
	packageDir = Path(j["pkg"]).absolute().resolve()
	outDir = Path(j["outDir"]).absolute().resolve()
	cookies = CLICookie.deserialize(j["cookie"])
	return packageDir, outDir, cookies


def main() -> int:
	jStr = sys.stdin.read()
	resCode = 1
	packageDir, outDir, cookies = _deserializeArgs(jStr)
	print(packageDir, outDir, cookies)

	try:
		outDir.mkdir(exist_ok=True, parents=True)
		res = buildWheelUsingPEP517(packageDir, outDir)
		resDict = {"wheel": str(res)}
		resCode = 0
	except BaseException as ex:
		resDict = {"error": {"__class": ex.__class__.__name__, "args": list(ex.args)}}

	sys.stdout.write(cookies.wrap(json.dumps(resDict)))
	return resCode


if __name__ == "__main__":
	exit(main())
