ipi.py [![Unlicensed work](https://raw.githubusercontent.com/unlicense/unlicense.org/master/static/favicon.png)](https://unlicense.org/)
======
~~[wheel (GitLab)](https://gitlab.com/KOLANICH-tools/ipi.py/-/jobs/artifacts/master/raw/dist/ipi-0.CI-py3-none-any.whl?job=build)~~
[wheel (GHA via `nightly.link`)](https://nightly.link/KOLANICH-tools/ipi.py/workflows/CI/master/ipi-0.CI-py3-none-any.whl)
~~![GitLab Build Status](https://gitlab.com/KOLANICH-tools/ipi.py/badges/master/pipeline.svg)~~
~~![GitLab Coverage](https://gitlab.com/KOLANICH-tools/ipi.py/badges/master/coverage.svg)~~
[![GitHub Actions](https://github.com/KOLANICH-tools/ipi.py/workflows/CI/badge.svg)](https://github.com/KOLANICH-tools/ipi.py/actions/)
[![Libraries.io Status](https://img.shields.io/librariesio/github/KOLANICH-tools/ipi.py.svg)](https://libraries.io/github/KOLANICH-tools/ipi.py)
[![Code style: antiflash](https://img.shields.io/badge/code%20style-antiflash-FFF.svg)](https://github.com/KOLANICH-tools/antiflash.py)

An intolerant to bullshit package installer for python.

Python software ecosystem is mad, let's fix it.

Disadvantages of installing packages via `pip`.

1. Usage of centralysed repository PyPI by default. Noone reads code in it. One can put clean code into VCS and malicious one into PyPi and noone will notice before it's too late.
2. When using `git` version control system as a source `pip` fetches the full history. It is slow and unneeded.
3. PEP 517 was a mistake resulting in a zoo of package build systems a user has to have on an own machine. Package authors tend to put any shiny bullshit into their package dependencies just because they want.
4. `<=`, `<`, `~=` and `==` conditions exist and are obeyed. Package authors tend to insert `<` conditions just to ensure THEIR package won't break, but as a user I'm more interested in the whole system of packages and programs being secure, bug-free, cheap to operate, operating, newest possible. In this order. If their package breaks - I will tolerate it, I'll just fix it. If their package causes downgrade of other packages from the ones having the needed features to the ones don't, breaking the whole system, I will not tolerate it.
5. The bullshit solution to the problem proposed by python folks is using `virtualenvs`. It is bullshit because it doesn't solves any problem, instead of fixing the packages it just allows software authors to demand installation of dependencies they want in their virtual envs. What if I need 2 packages requiring 2 different versions of deps? I still have to fix them then. What if I need any tool I'm familiar with tool globally, everywhere? They propose to activate the needed venvs. And when I need another tool, activate its venv. So venvs just waste my time, RAM, disk space and CPU cycles. Absolute bullshit solution instead of doing the fucking work and fixing the fucking packages. And they dare to recommend this bullshit to everyone!


Instead we propose the following workflow as a workaround of current python ecosystem issues.

1. a developer publish his source code on a public platform like GitHub.
2. someone publish somewhere a file called `packages_petnames.tsv` 

```tsv
ipi	https://github.com/KOLANICH-tools/ipi.git
```
3. A user of the package manager subscribes to the repo

```bash
ipi repo add https://raw.githubusercontent.com/KOLANICH/packages_petnames/master/packages_petnames.tsv
```
4. The tool downloads the files.
5. The tool matches the package names to repos
6. The tool fetches the default branch from the repo, and builds the package and caches it.
7. The tool installs the package using pip.

Also a tool can generate the list of petnames by taking user's account and using the service API to fetch the list of his repos and build a registry from it.

# Bootstrap sequence
1. bootstrap python packaging

```bash
python3 -m ipi bootstrap packaging
```

2. bootstrap self

```bash
python3 -m ipi bootstrap self
```

# Testing 
1. create a bare virtualenv

```bash
./tests/createTestEnv.sh shit
```

2. activate it

```bash
. ./shit/bin/activate
```

3. run bootstrap sequence

