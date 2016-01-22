import os

__version__ = '0.1.0'
__license__ = 'GPL2'
__author__ = 'Bernd Strebel'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

from .sync import ToodledoSync
from .toodledo_from_ox import ToodledoFromOxTask

__all__ = [
    'ToodledoSync',
    'ToodledoFromOxTask'
]
