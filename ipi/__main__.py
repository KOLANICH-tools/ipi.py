try:
	from .cli.plumbum import main
except ImportError:
	from .cli.argparse import main

if __name__ == "__main__":
	main()
