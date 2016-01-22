import os

__version__ = '0.4.0'
__license__ = 'GPL2'
__author__ = 'Bernd Strebel'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

from .sync import OxTaskSync
from .oxtask_from_evernote import OxTaskFromEvernote

__all__ = [

    'OxTaskSync',
    'OxTaskFromEvernote'
]


