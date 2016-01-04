from setuptools import setup
import re

version = re.search(
    "^__version__\s*=\s*'(.*)'",
    open('pysync/__init__.py').read(),
    re.M).group(1)

setup(
    name='PySync',
    version=version,
    packages=['pysync', 'oxsync', 'ensync'],
    url='https://github.com/bstrebel/PySync',
    license='GPL2',
    author='Bernd Strebel',
    author_email='b.strebel@digitec.de',
    description='Python Sync Engine',
    long_description=open('README.md').read(),
    install_requires=['PyUtils', 'OxAPI', 'EvernoteAPI'],
    entry_points={'console_scripts': ['pysync = pysync.core:main']}
)
