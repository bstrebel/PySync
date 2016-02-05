import os, sys, logging

__version__ = '0.9.4'
__license__ = 'GPL2'
__author__ = 'Bernd Strebel'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

from .core import PySync
from .sync import Sync
from .update import ThisFromThat

from ensync import EnClientSync, EvernoteFromOxTask, EvernoteFromToodledo
from oxsync import OxTaskSync, OxTaskFromEvernote, OxTaskFromToodldo
from tdsync import ToodledoSync, ToodledoFromOxTask, ToodledoFromEvernote

__all__ = [

    'PySync', 'Sync', 'ThisFromThat',
    'OxTaskSync', 'OxTaskFromEvernote', 'OxTaskFromToodldo',
    'EnClientSync', 'EvernoteFromOxTask', 'EvernoteFromToodledo',
    'ToodledoSync', 'ToodledoFromOxTask', 'ToodledoFromEvernote'
]
