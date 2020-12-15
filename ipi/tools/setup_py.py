from .python import python

setupPy = python.bake("./setup.py", _fg=True)
eggInfoCmd = setupPy.bake("egg_info")
wheelCmd = setupPy.bake("bdist_wheel")
