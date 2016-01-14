import os, sys, logging

__version__ = '0.5.2'
__license__ = 'GPL2'
__author__ = 'Bernd Strebel'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

from .core import PySync
from .sync import Sync

__all__ = [

    'PySync',
    'Sync'
]
