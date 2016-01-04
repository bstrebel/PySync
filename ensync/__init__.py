import os

__version__ = '1.0.0'
__license__ = 'GPL2'
__author__ = 'Bernd Strebel'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

from .sync import EnClientSync

__all__ = [
   'EnClientSync'
]
