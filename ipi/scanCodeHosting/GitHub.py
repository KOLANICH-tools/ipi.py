import typing
from collections import defaultdict
from enum import IntEnum
from pathlib import PurePosixPath

import httpx
import miniGHAPI.GitHubAPI

from ..registries import Package, Registry, derivePackageNameFromURI
from ..utils.metadataExtractor import tryExtractPEP517AndPEP621Metadata


def getAllReposByUser(u: "miniGHAPI.GitHubAPI.User"):
	yield from u.getRepos()
	for o in u.getOrgs():
		yield from o.getRepos()


class PackageUrlCandidate:
	__slots__ = ("package", "pyprojectURL")

	def __init__(self, package, pyprojectURL):
		self.package = package
		self.pyprojectURL = pyprojectURL


def filterGitHubRepos(repos, forks: bool = False, priv: bool = False, templates: bool = False, langs: set = {"Python", "Jupyter Notebook"}):
	if not forks:
		repos = [r for r in repos if not r.info["fork"]]

	if priv is not None:
		repos = [r for r in repos if (not r.info["visibility"] == "public") == priv]

	if not templates:
		repos = [r for r in repos if not r.info["is_template"]]

	if langs is not None:
		repos = [r for r in repos if r.info["language"] in langs]

	return [PackageUrlCandidate(Package(name=None, repo=r.info["clone_url"], fetcher="git"), r.getFileRawURL("pyproject.toml")) for r in repos]


class RejectCode(IntEnum):
	ok = 0
	noPyprojectToml = 1
	tomlParsingError = 2
	pep517ParsingError = 3
	noPep621 = 4
	noName = 5
	nameConflict = 6


RejectCode.noPyprojectToml.__doc__ = "No pyproject.toml for {repoUrl} : {httpStatus}, {pptU}"
RejectCode.tomlParsingError.__doc__ = "Error parsing TOML for `pyproject.toml` {pptU}"
RejectCode.pep517ParsingError.__doc__ = "Error parsing PEP 517 metadata from package int the repo {pptU} : {exception}"
RejectCode.noPep621.__doc__ = "{repoUrl} doesn't use PEP 621, skipping"
RejectCode.noName.__doc__ = "Error parsing name from package in repo {repoUrl} : {exception}"
RejectCode.nameConflict.__doc__ = "Name conflict with {conflictingPackage} for {repoUrl}"


class Rejection:
	__slots__ = ("code", "repoUrl", "httpStatus", "pptU", "conflictingPackage", "exception")

	def __init__(self, code: RejectCode, repoUrl: str, httpStatus: int, pptU: str, conflictingPackage: typing.Optional[Package] = None, exception: Exception = None):
		self.code = code
		self.repoUrl = repoUrl
		self.httpStatus = httpStatus
		self.pptU = pptU
		self.conflictingPackage = conflictingPackage
		self.exception = exception

	def __str__(self):
		return self.code.__doc__.format(repoUrl=self.repoUrl, httpStatus=self.httpStatus, pptU=self.pptU, conflictingPackage=self.conflictingPackage, exception=self.exception)


def filterPyprojectRepos(packageUrlsCandidates: typing.Iterable[PackageUrlCandidate], timeout: float) -> typing.Iterable[Package]:
	try:
		import tomllib
	except ImportError:
		import tomli as tomllib

	packages = {}
	rejections = []

	for rc in packageUrlsCandidates:
		pptU = rc.pyprojectURL
		p = rc.package
		repoUrl = p.repo

		pptRes = httpx.get(pptU, timeout=timeout)
		if pptRes.status_code // 100 == 4:
			rejections.append(Rejection(RejectCode.noPyprojectToml, repoUrl, pptRes.status_code, pptU))
			continue

		ppt = pptRes.text

		try:
			ppt = tomllib.loads(ppt)
		except BaseException as ex:
			rejections.append(Rejection(RejectCode.tomlParsingError, repoUrl, pptRes.status_code, pptU, exception=ex))
			continue

		try:
			pep517 = tryExtractPEP517AndPEP621Metadata(ppt)
		except BaseException as ex:
			rejections.append(Rejection(RejectCode.pep517ParsingError, repoUrl, pptRes.status_code, pptU, exception=ex))
			continue

		if pep517.child is None:
			rejections.append(Rejection(RejectCode.noPep621, repoUrl, pptRes.status_code, pptU))
			continue

		try:
			p.name = pep517.child.name
		except BaseException as ex:
			rejections.append(Rejection(RejectCode.noName, repoUrl, pptRes.status_code, pptU))
			continue

		if p.name in packages:
			rejections.append(Rejection(RejectCode.nameConflict, repoUrl, pptRes.status_code, pptU, conflictingPackage=packages[p.name]))
			continue

		packages[p.name] = p

	return packages, rejections


def groupRejections(rejections):
	rejsGroups = defaultdict(list)
	for rej in rejections:
		rejsGroups[rej.code].append(rej)

	return rejsGroups


def printRejections(rejections):
	rejsGroups = groupRejections(rejections)
	for code, rejs in rejsGroups.items():
		for rej in rejs:
			print(rej)


def generateRegistryForUser(u: "miniGHAPI.GitHubAPI.User", timeout: float = 5):
	repos = getAllReposByUser(u)
	repos = filterGitHubRepos(repos)
	pkgs, rejections = filterPyprojectRepos(repos, timeout)
	pkgs = dict(sorted(pkgs.items(), key=lambda x: x[0]))
	return Registry(u.name + "@GitHub", pkgs), rejections
