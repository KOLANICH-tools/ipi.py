from pathlib import Path


def toFileURI(p: Path) -> str:
	return "file://" + str(p.absolute().resolve())
	return "http://127.0.0.1:8000/" + str(p.absolute().resolve().relative_to(Path("./ipi-repo/").absolute().resolve()))


def canonicalizePackageName(pkgName: str) -> str:
	return pkgName.replace("_", "-")


def canonicalizePackageNameMulti(pkgName: str) -> (str, str):
	dashName = canonicalizePackageName(pkgName)
	return dashName, dashName.replace("-", "_")
