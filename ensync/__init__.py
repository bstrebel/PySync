import os

__version__ = '0.4.0'
__license__ = 'GPL2'
__author__ = 'Bernd Strebel'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

from .sync import EnClientSync
from .evernote_from_oxtask import EvernoteFromOxTask

__all__ = [
    'EnClientSync',
    'EvernoteFromOxTask'
]
