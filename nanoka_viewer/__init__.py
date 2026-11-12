"""NanokaLeaks application package."""

try:
    from ._version import __version__
except ImportError:  # not built yet (e.g. running from a bare checkout)
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("nanokaleaks")
    except PackageNotFoundError:
        __version__ = "0.0.0+unknown"

__all__ = ["__version__"]