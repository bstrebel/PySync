#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, logging, json
from pyutils import LogAdapter, get_logger, strflocal

from abc import ABCMeta, abstractmethod, abstractproperty

class ThisFromThat(object):

    __metaclass__ = ABCMeta

    def __init__(self, engine, package):
        self._engine = engine
        self._adapter = LogAdapter(engine._logger, {'package': package})

    @property
    def logger(self):
        return self._adapter

    @property
    def class_name(self):
        return self._engine.class_name

    @property
    def options(self):
        return self._engine.options

    @abstractmethod
    def update(self, that, this=None):
        return None