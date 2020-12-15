import argparse

from ..bootstrap.tiers import BootstrapTier

__all__ = ("main", "tier")

cli = argparse.ArgumentParser(description="A basic CLI. `bootstrap self` to get `ipi` fully functional.")
sp = cli.add_subparsers(dest="cmd")

instl = sp.add_parser("install", description="Installs packages.")
instl.add_argument("packages", nargs="+")
instl.add_argument("--upgrade", action="store_true", help="Upgrade all installed packages")
instl.add_argument("--force-reinstall", action="store_true", help="Always rebuild and reinstall")

boo = sp.add_parser("bootstrap", description="Bootstraps the stuff.")

booSp = boo.add_subparsers(dest="booCmd")

booPackaging = booSp.add_parser("packaging", description="Installs the packages neeeded for python packaging ecosystem to operate.")
booSelf = booSp.add_parser("self", description="Installs the packages neeeded for this tool to operate.")
booItSelf = booSp.add_parser("itself", description="An alias for self.")


def indexArgparseParserOpts(parserCls):
	return {a.dest: a for a in parserCls._actions}


instlIndex = indexArgparseParserOpts(instl)


def _installImpl(packageNames, upgrade, forceReinstall):
	from ..registries import initRegistries

	regs = initRegistries()

	from ..pipelines import PackagesInstaller, ResolutionPrefs, buildAndInstallWheelFromGitURI

	i = PackagesInstaller(regs)
	i(ResolutionPrefs(upgrade=upgrade, forceReinstall=forceReinstall), packageNames)


def main():
	args = cli.parse_args()
	if args.cmd == "bootstrap":
		if args.booCmd in {"self", "itself"}:
			from ..bootstrap.itself import bootstrapItself

			bootstrapItself()

		elif args.booCmd == "packaging":
			from ..bootstrap.setuptools import bootstrapPythonPackaging

			bootstrapPythonPackaging()
		else:
			boo.print_help()
			exit(1)
	elif args.cmd == "install":
		_installImpl(packageNames=args.packages, upgrade=args.upgrade, forceReinstall=args.force_reinstall)
	else:
		cli.print_help()
		exit(1)


tier = BootstrapTier.bootstrap

if __name__ == "__main__":
	main()
