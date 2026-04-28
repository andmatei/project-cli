from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("project-cli")
except PackageNotFoundError:  # not installed (running from source without install)
    __version__ = "0+unknown"
