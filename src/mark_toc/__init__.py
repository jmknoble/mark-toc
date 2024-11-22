import logging

logger = logging.getLogger(__name__)

__version__ = "0.5.0"


def get_version(thing=None):
    if thing is None:
        return __version__
    return "{thing} v{version}".format(thing=thing, version=__version__)
