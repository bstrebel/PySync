import os, sys, logging

__version__ = '0.7.0'
__license__ = 'GPL2'
__author__ = 'Bernd Strebel'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

from .core import PySync
from .sync import Sync
from .update import ThisFromThat

from ensync import EnClientSync, EvernoteFromOxTask
from oxsync import OxTaskSync, OxTaskFromEvernote
from tdsync import ToodledoSync, ToodledoFromOxTask

__all__ = [

    'PySync', 'Sync', 'ThisFromThat',
    'OxTaskSync', 'OxTaskFromEvernote',
    'EnClientSync', 'EvernoteFromOxTask',
    'ToodledoSync', 'ToodledoFromOxTask'
]
