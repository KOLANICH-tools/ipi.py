import typing
from datetime import datetime
from pathlib import Path, PurePosixPath
from pprint import pformat
from urllib.parse import ParseResult, unquote_plus, urljoin, urlparse, urlunparse
from warnings import warn

from plumbum import cli

from ..bootstrap.tiers import BootstrapTier
from ..utils.styles import styles
from .argparse import _installImpl
from .argparse import instlIndex as argparseInstallSubParserIndex

__all__ = ("main", "tier")


class CLI(cli.Application):
	"""Anti-bullshit package manager"""

	verbose = cli.Flag(["-v", "--verbose"])
	proxy = cli.SwitchAttr(["--proxy"])
	retries = cli.SwitchAttr(["--retries"])
	noColor = cli.Flag(["--no-color"])


@CLI.subcommand("install")
class CLIInstall(cli.Application):
	upgrade = cli.Flag(argparseInstallSubParserIndex["upgrade"].option_strings, help=argparseInstallSubParserIndex["upgrade"].help)
	forceReinstall = cli.Flag(argparseInstallSubParserIndex["force_reinstall"].option_strings, help=argparseInstallSubParserIndex["force_reinstall"].help)
	noDeps = cli.Flag(["--no-deps"])
	dryRun = cli.Flag(["--dry-run"])
	user = cli.Flag(["--user"])
	root = cli.SwitchAttr(["--root"])
	prefix = cli.SwitchAttr(["--prefix"])

	def main(self, *packageNames: str):
		_installImpl(packageNames=packageNames, upgrade=self.upgrade, forceReinstall=self.forceReinstall)


@CLI.subcommand("update")
class CLIUpdate(cli.Application):
	"""Updates the configured repos"""

	def main(self):
		raise NotImplementedError


@CLI.subcommand("upgrade")
class CLIUpgrade(cli.Application):
	"""Upgrades the packages from the configured repos"""

	def main(self):
		raise NotImplementedError


@CLI.subcommand("repo")
class CLIRepo(cli.Application):
	"""Manages repos"""


@CLIRepo.subcommand("list")
class CLIRepoList(cli.Application):
	"""Shows a list of set up repos"""

	simpleList = cli.Flag(["-1"], help="Show only names, one per line")

	def main(self):
		from ..repos.tuf.RepoManager import RepoManager

		m = RepoManager()
		if self.simpleList:
			print("\n".join(m.petNames))
		else:
			# YAML serialization, JSON is a subset of YAML
			import json

			for pn in m.petNames:
				r = m[pn]
				resDict = {
					"localMetadata": r.localMetadata,
				}
				print(pn + ":", json.dumps(resDict, indent="\t"))


canonicalRootFileName = "root.json"

URIPreTransformerInternalUriReprT = typing.Any


class URIPreTransformer:
	NAME = None  # type: str

	@classmethod
	def detect(cls, uri: ParseResult) -> typing.Optional[URIPreTransformerInternalUriReprT]:
		raise NotImplementedError

	@classmethod
	def transform(cls, uri: URIPreTransformerInternalUriReprT, parent: "CLIRepoAdd") -> str:
		raise NotImplementedError


class GitHubURIPreTransformer(URIPreTransformer):
	NAME = "GitHub"

	@classmethod
	def detect(cls, uri: ParseResult) -> typing.Optional[URIPreTransformerInternalUriReprT]:
		nl = uri.netloc.lower()
		if nl in {"github.com", "raw.githubusercontent.com"}:
			parts = PurePosixPath(uri.path)._parts
			if parts[0] == "/":
				namespace, repoName = parts[1:3]
				branch = None
				path = None

				def genDict():
					return {
						"namespace": namespace,
						"repoName": repoName,
						"branch": branch,
						"path": PurePosixPath._from_parts(path) if path else None,
					}

				if len(parts) == 3:
					return genDict()
				else:
					if nl == "github.com":
						if parts[3] in {"blob", "tree"}:
							branch = parts[4]

							if parts[3] == "blob":
								path = parts[5:]
							return genDict()
					else:  # raw.githubusercontent.com
						branch = parts[3]
						path = parts[4:]
						return genDict()

	@classmethod
	def transform(cls, uri: URIPreTransformerInternalUriReprT, parent: "CLIRepoAdd") -> str:
		from miniGHAPI.GitHubAPI import CT, GHAPI

		gha = GHAPI("")
		r = gha.repo(uri["namespace"], uri["repoName"])

		repoInfo = r.getInfo()

		u = r.ownerObj()

		userInfo = u.getInfo()
		if userInfo["type"] != "User":
			raise RuntimeError("The namespace in repo name belongs to an organization, not to a user. So we cannot determine signing key")

		try:
			import GitHubRepoSummary
		except ImportError as e:
			warn("Install GitHubRepoSummary to see the repo summary")
		else:
			print("\n".join(GitHubRepoSummary.formatRepoInfo(r, printReadMe=None)))

		if parent.publicKey is None:

			def filterIpiKeys(keys):
				for k in keys:
					t = k["title"]
					if t == "ipi" or t.startswith("ipi-"):
						yield k

			keys = list(filterIpiKeys(u.keys.ssh.getSigning()))

			def parseKeysInKeys(keys):
				for k in keys:
					try:
						k["key"] = importSSHKeyData(k["key"])
					except (ValueError, NotImplementedError, KeyIsPrivateWherePublicIsExpectedError) as ex:
						warn("Key " + repr(k) + " has unsupported format, ignoring it: " + repr(ex))
					else:
						yield k

			keys = list(parseKeysInKeys(keys))

			for k in keys:
				k["created_at"] = datetime.fromisoformat(k["created_at"][:-1])

			keys = sorted(keys, key=lambda k: k["created_at"], reverse=True)

			if not keys:
				raise RuntimeError("There are no keys in the owner's account and no key is specified using CLI")

			selectedKey = keys[0]

			if len(keys) > 1:
				print(styles.operationName("Selecting") + " the latest one of the multiple " + styles.entity("keys") + " (sorted from latest to oldest): ")
				print(pformat(keys))
			else:  # len(keys) == 1
				print(styles.success("selected") + " the " + styles.entity("key") + ":\n" + pformat(selectedKey))

			parent.publicKey = selectedKey["key"]

		path = uri["path"]

		if path is None:
			path = PurePosixPath(canonicalRootFileName)

		return r.getFileRawURL(path, uri["branch"])


codeHostingsURIPostProcessors = (GitHubURIPreTransformer,)

privateKeyInsteadOfPublicKeyErrMsg = "contains a private key, that must not be publicly available!!!"


class KeyIsPrivateWherePublicIsExpectedError(ValueError):
	__slots__ = ()


def importSSHKeyData(keyData: bytes):
	from securesystemslib_KOLANICH.convert.ssh import import_ssh_key

	pk = import_ssh_key(key=keyData)
	if pk.get("keyval", {}).get("private", None):
		raise KeyIsPrivateWherePublicIsExpectedError("The provided key is private", keyData)
	return pk


def importSSHKeyCLI(cliKeyStr: str):
	keyData = None

	isFile = False
	if cliKeyStr.startswith("@"):
		keyData = Path(cliKeyStr[1:]).read_bytes()
		isFile = True
	else:
		keyData = cliKeyStr

	try:
		key = importSshKeyData(pk)
	except KeyIsPrivateWherePublicIsExpectedError as ex:
		if isFile:
			raise KeyIsPrivateWherePublicIsExpectedError("The file " + privateKeyInsteadOfPublicKeyErrMsg, cliKeyStr) from ex
		else:
			raise KeyIsPrivateWherePublicIsExpectedError("The provided string " + privateKeyInsteadOfPublicKeyErrMsg, cliKeyStr) from ex

	return key


@CLIRepo.subcommand("add")
class CLIRepoAdd(cli.Application):
	"""Adds a repo. Only adds a root file. It doesn't fetch any info by default."""

	update = cli.Flag(["-u", "--update"], help="Not only add a repo, but also upgrade it")
	fetch = cli.Flag(["-f", "--fetch"], help="Not only update a repo, but also download its files")
	publicKey = cli.SwitchAttr(["--pk"], argtype=str, default=None, help="Expect the certain public key, abort otherwise")
	publicKeyFingerprint = cli.SwitchAttr(["--fp"], argtype=str, default=None, help="Expect the certain public key fingerprint, abort otherwise")
	yes = cli.Flag(["-y", "--yes"], help="Answer positively to the prompts.")

	def main(self, repoPetName: str, repoURI: str):
		if self.publicKey is not None:
			self.publicKey = importSSHKeyCLI(self.publicKey)

		if isinstance(repoURI, str) and not repoURI.startswith("https://") and not repoURI.startswith("file:"):
			repoDictPath = Path(repoURI)
			if repoDictPath.is_dir():
				repoDictPath = repoDictPath / canonicalRootFileName

			if repoDictPath.is_file():
				from ..utils import toFileURI
				from ..utils.json import json

				repoDict = json.loads(repoDictPath.read_text())
				repoURI = repoDictPath.parent.as_uri()
			else:
				raise FileNotFoundError("Must be a file", repoDictPath)
		else:
			repoURI = unquote_plus(repoURI)
			parsedURI = urlparse(repoURI)
			for pt in codeHostingsURIPostProcessors:
				detected = pt.detect(parsedURI)
				if detected is not None:
					print(styles.entity("URI"), styles.varContent(repoURI), styles.operationName("matches") + " the " + styles.entity("pretransformer"), styles.varContent(pt.NAME))
					repoURI = pt.transform(detected, self)
					print(styles.success("Transformed") + " the " + styles.entity("URI") + ": ", styles.varContent(repoURI))
					break

			splitted = repoURI.rsplit("/", 1)
			repoDictURI = repoURI

			if len(splitted) == 1:
				repoDictURI += urljoin(repoURI, canonicalRootFileName)
			else:
				base, ending = splitted
				if not ending:
					repoDictURI += urljoin(repoURI, canonicalRootFileName)
				else:
					repoURI = base

			import httpx

			repoDict = httpx.get(repoDictURI).json()

		print(styles.entity("Repo dict"), pformat(repoDict))

		if self.publicKey is not None:
			s = repoDict["signed"]
			ki = s["roles"]["root"]["keyids"]
			if len(ki) != 1:
				raise RuntimeError("Zero/multiple keyids in `root` role", ki)

			metaKi = ki[0]

			pformat(s["keys"])
			metaKey = s["keys"][metaKi]

			anotherKeyErrorMessage = "Another key binds root role"

			pformat(metaKey)
			pformat(self.publicKey)

			for k in ("keytype", "scheme"):
				if metaKey[k] != self.publicKey[k]:
					raise ValueError(anotherKeyErrorMessage)

			if metaKey["keyval"]["public"] != self.publicKey["keyval"]["public"]:
				raise ValueError(anotherKeyErrorMessage + " It may be because of key serialization issues in `securesystemslib`", metaKey["keyval"]["public"], self.publicKey["keyval"]["public"])

		from ..repos.tuf.RepoManager import RepoManager

		m = RepoManager()

		if self.yes or cli.terminal.ask(str("Do you want to " + styles.operationName("add") + " this " + styles.entity("repo") + "?"), default=False):
			localMetaDict = m.add(repoPetName, repoDict, [repoURI])

			print(styles.entity("Repo") + " `" + styles.varContent(repoPetName) + "` " + styles.success("added"))

			if self.update or self.fetch:
				print(styles.operationName("Updating..."))
				r = m.repoByPetName(repoPetName)
				repoDict
				r.update()

			# if self.fetch:
			#
		else:
			print(styles.error("Operation is cancelled"))
			return 1


@CLIRepo.subcommand("update")
class CLIRepoUpdate(cli.Application):
	"""Updates the repo"""

	def main(self, repoPetName: str):
		from ..repos.tuf.RepoManager import RepoManager

		m = RepoManager()
		m.repoByPetName(repoPetName).update()


@CLIRepo.subcommand("remove")
class CLIRepoRemove(cli.Application):
	"""Removes a repo"""

	def main(self, petname: str):
		from ..repos.tuf.RepoManager import RepoManager

		m = RepoManager()
		del m[petname]


@CLI.subcommand("download")
class CLIDownload(cli.Application):
	pass


@CLI.subcommand("bootstrap")
class CLIBootstrap(cli.Application):
	"""Allows to bootstrap various things"""


@CLIBootstrap.subcommand("packaging")
class CLIBootstrapPackaging(cli.Application):
	"""Bootstraps python packaging infrastructure"""

	def main(self):
		from ..bootstrap.setuptools import bootstrapPythonPackaging

		bootstrapPythonPackaging()


@CLIBootstrap.subcommand("self")
class CLIBootstrapSelf(cli.Application):
	"""Bootstraps `ipi` itself"""

	def main(self):
		from ..bootstrap.itself import bootstrapItself

		bootstrapItself()


@CLIBootstrap.subcommand("itself")
class CLIBootstrapItself(CLIBootstrapSelf):
	"""An alias to `self`"""


@CLI.subcommand("resolve")
class CLIResolve(cli.Application):
	"""Resolves the names of package into its repo"""

	def main(self, *names: str):
		from ..registries import initRegistries

		regs = initRegistries()

		for el in names:
			try:
				res = regs.lookup(el)
				print(el, ":", res)
			except KeyError:
				print(el, ":", "Not found")


@CLI.subcommand("debug")
class CLIDebug(cli.Application):
	"""Utilities needed for debugging `ipi`"""


@CLIDebug.subcommand("show")
class CLIDebugShow(cli.Application):
	"""Shows something"""


@CLIDebugShow.subcommand("config-dir")
class CLIDebugShowConfigDir(cli.Application):
	"""Shows config dir"""

	def main(self):
		from ..settings import settingsDir

		print(settingsDir)


@CLIDebugShow.subcommand("self")
class CLIDebugShowSelf(cli.Application):
	"""Shows info about this ipi instance"""


@CLIDebugShowSelf.subcommand("code-dir")
class CLIDebugShowSelfCodeDir(cli.Application):
	"""Shows the dir from which ipi code is used"""

	def main(self):
		print(Path(__file__).absolute().resolve().parent.parent)


@CLIDebugShowSelf.subcommand("executable")
class CLIDebugShowSelfCodeDir(cli.Application):
	"""Shows the executable being used"""

	def main(self):
		import traceback

		traceback.print_stack()


@CLIDebugShow.subcommand("package-version")
class CLIDebugShowPackageVersion(cli.Application):
	"""Shows version of a package using the same mechanisms ipi gets it"""

	def main(self, packageName: str):
		from ..tools.install import getInstalledPackageVersion

		print(getInstalledPackageVersion(packageName))


@CLIDebugShow.subcommand("install-scheme")
class CLIDebugShowInstallerScheme(cli.Application):
	"""Prints installer scheme"""

	def main(self):
		from pprint import pprint

		from ..tools.install import getScheme

		pprint(getScheme())


@CLI.subcommand("author")
class CLIAuthor(cli.Application):
	"""Authoring of repos"""


@CLIAuthor.subcommand("gen")
class CLIAuthorGen(cli.Application):
	"""Scans source code hostings and generates repos"""


def loadRepoAndKey(keyPath: cli.ExistingFile, repoPath: cli.ExistingDirectory, roles: typing.Iterable[str]):
	from pathlib import Path

	from ipi.repos.tuf.Repo import Repo
	from ipi.repos.tuf.RepoBuilder import RepoBuilder, RepoSeed
	from ipi.settings import reposRoot as defaultReposRoot
	from securesystemslib_KOLANICH.convert.ssh import import_ssh_key

	repoPath = Path(repoPath)
	keyPath = Path(keyPath)

	myKey = import_ssh_key(keyPath.read_bytes(), None)

	seed = RepoSeed.load(repoPath)
	b = RepoBuilder(seed, {r: myKey for r in roles}, repoPath)

	return b, repoPath


@CLIAuthorGen.subcommand("github")
class CLIAuthorGenGitHub(cli.Application):
	"""Scans GitHub and generates repo for all the stuff created by particular user/org"""

	def main(self, keyPath: cli.ExistingFile, repoPath: cli.ExistingDirectory, userName: str):
		from pprint import pprint

		import miniGHAPI.GitHubAPI

		from ..scanCodeHosting.GitHub import generateRegistryForUser

		b, repoPath = loadRepoAndKey(keyPath, repoPath, ["snapshot", "targets", "timestamp"])

		a = miniGHAPI.GitHubAPI.GHAPI("", timeout=None)
		u = a.user(userName)
		reg, rejections = generateRegistryForUser(u)

		if rejections:
			print(styles.error("Rejections") + ":")
			for r in rejections:
				print(r)

		b.addRegistry(reg)
		b.makeSnapshot()
		b.save(repoPath)


@CLIAuthor.subcommand("init")
class CLIAuthorInit(cli.Application):
	"""Used to initialize repos using TUF"""

	def main(self, keyPath: cli.ExistingFile, repoPath: cli.ExistingDirectory):
		from pathlib import Path

		from ipi.repos.tuf.RepoBuilder import RepoSeed
		from ipi.settings import reposRoot as defaultReposRoot
		from securesystemslib_KOLANICH.convert.ssh import import_ssh_key

		repoPath = Path(repoPath)
		keyPath = Path(keyPath)

		myKey = import_ssh_key(keyPath.read_bytes(), None)
		keyManager = RepoSeed.keyManagerFromSingleKey(myKey)

		seed = RepoSeed.make(keyManager)
		seed.sign()
		seed.save(repoPath)


@CLIAuthor.subcommand("seal")
class CLIAuthorSeal(cli.Application):
	"""Used to seal repos using TUF"""

	def main(self, keyPath: cli.ExistingFile, repoPath: cli.ExistingDirectory):
		b, repoPath = loadRepoAndKey(keyPath, repoPath, ["snapshot", "targets", "timestamp"])

		tsvFiles = sorted(repoPath.glob("*.tsv"))  # for now in the root only

		for f in tsvFiles:
			b.userFiles[f.name] = f.read_bytes()

		b.makeSnapshot()
		b.save(repoPath)


@CLIAuthor.subcommand("stamp")
class CLIAuthorTiestamp(cli.Application):
	"""Used to certify freshness of the repo"""

	def main(self, keyPath: cli.ExistingFile, repoPath: cli.ExistingDirectory):
		b, repoPath = loadRepoAndKey(keyPath, repoPath, ["timestamp"])

		b.stamp()
		b.save(repoPath)


def main():
	return CLI.run()


tier = BootstrapTier.full

if __name__ == "__main__":
	main()
