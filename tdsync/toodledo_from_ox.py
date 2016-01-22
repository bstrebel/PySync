#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, re, logging
from pyutils import LogAdapter, strflocal, get_logger
from pysync import ThisFromThat

class ToodledoFromOxTask(ThisFromThat):

    def __init__(self, engine):
        ThisFromThat.__init__(self, engine, 'td <- ox')

    def update(self, oxTaskSync,  todo=None):
        """
        Update Toodledo task from other module
        :param oxTaskSync:    OtherClassSync (if called from sync)
                        OtherClassObject (if called from create)
        :param note:    None (if called from sync)
                        or just created EnNote
        :return:        current timestamp of updated EnNote
        """

        update = True if todo is None else False
        if update:
            todo = self._engine.get().load()
            # TODO: check todo, raise exception (?)
            self.logger.info('%s: Updating note [%s] from %s' % (self.class_name, todo.title.decode('utf-8'),
                                                                 oxTaskSync.class_name))

        task = oxTaskSync.get().load()
        # TODO: check task and raise exception (?)

        todo.title = task.title
        todo = self._engine._client.update_task(todo)
        self.logger.info('%s: Updating completed with timestamp %s' % (self._engine.class_name, strflocal(todo.modified)))
        return todo
