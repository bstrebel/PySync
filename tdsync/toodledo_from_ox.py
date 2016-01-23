#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, re, logging
from pyutils import LogAdapter, strflocal, get_logger
from pysync import ThisFromThat

class ToodledoFromOxTask(ThisFromThat):

    def __init__(self, engine, other):
        ThisFromThat.__init__(self, engine, other, 'td <- ox')

    @property
    def oxTaskSync(self):
        return self._other

    def update(self, other, that=None,  this=None):

        task, todo = ThisFromThat.update(self, other, that, this)

        toodledo_sync = self._engine
        toodledo = self._engine.client

        ox_task_sync = self._other
        ox = self._other._ox

        todo.title = task.title

        todo = toodledo.update_task(todo)
        self.logger.info(u'%s: Updating completed with timestamp %s' % (self._engine.class_name, strflocal(todo.modified)))
        return todo
