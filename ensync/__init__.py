import os

__version__ = '0.3.1'
__license__ = 'GPL2'
__author__ = 'Bernd Strebel'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

from .sync import EnClientSync

__all__ = [
   'EnClientSync'
]
