import os

__version__ = '0.3.0'
__license__ = 'GPL2'
__author__ = 'Bernd Strebel'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

from .sync import OxTaskSync

__all__ = [

    'OxTaskSync'
]


