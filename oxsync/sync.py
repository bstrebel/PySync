#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, re, logging
from pyutils import LogAdapter, strflocal, get_logger, utf8

from pysync import Sync
from oxapi import *

class OxTaskSync(Sync, OxTasks):

    @staticmethod
    def session(options, _logger):
        if options:
            if options.get('secrets'):
                secrets = options['secrets']
                if secrets.get('server'):
                    if secrets.get('user'):
                        if secrets.get('password'):
                            ox = OxHttpAPI.get_session(server=secrets['server'],
                                                       user=secrets['user'],
                                                       password=secrets['password'],
                                                       logger=_logger)
                            if ox.authenticated:
                                return ox
                            else:
                                return None

        LogAdapter(_logger, {'package': 'oxsync'}).error('Missing credentials in Open-Xchange options')
        return None

    def __init__(self, ox, options, logger=None):

        self._key_attribute = options.get('key','title')
        self._maxsize = options.get('maxsize', 2048)
        self._folder = None

        Sync.__init__(self, options, logger, 'oxsync')
        OxTasks.__init__(self, ox)

        if self.signature is None:
            if options.get('folder'):
                folder = options.get('folder')
                self._folder = self._ox.get_folder('tasks', folder)
                if self._folder is not None:
                    signature = {'label': options.get('label')}
                    signature['folder'] = self._folder.title
                    signature['id'] = self._folder.id
                    self.options.update({'signature': signature})
                else:
                    self.logger.error(u'Folder [%s] not found!' % (utf8(folder)))
            else:
                self.logger.error(u'No folder specified in in sync options!')
        else:
            self._folder = self._ox.get_folder('tasks', self.signature['id'])

    def __repr__(self): return self.label

    def __str__(self): return self.label

    @property
    def class_name(self): return self.label

    @property
    def maxsize(self): return self._maxsize

    @maxsize.setter
    def maxsize(self, value): self._maxsize = value

    @property
    def folder(self): return self._folder

    # @property
    # def name(self): return self.signature.get('folder')
    #
    # @property
    # def id(self): return self.signature.get('id')
    #
    # @property
    # def folder(self): return self.id if self.id else self.name

    @property
    def need_last_map(self): return False

    def end_session(self, lr=None, opts=None):
        if self._ox.authenticated:
            self._ox.logout()
        return opts

    def _check_filter(self, item):
        return True

    def map_item(self, ref=None):

        if isinstance(ref, OxTask):
            return {'id': ref.id, 'key': ref[self._key_attribute], 'time': ref.timestamp}
        else:
            return Sync.map_item(self, ref)

    def sync_map(self, last=None):

        #folder = self._ox.get_folder('tasks', self.folder)

        if self.folder:

            self._data = []; self._items = {}

            for task in self._ox.get_tasks(self.folder.id, ['id', 'last_modified', self._key_attribute]):
                if self._check_filter(task):
                    self._data.append(task)
                    item = {'id': task.id, 'time': task.last_modified + self._ox.utc_offset, 'key': task[self._key_attribute]}
                    self._add_item(task.id, item)

            return {'items': self.items}

        return None


    def changed(self, sync):
        return Sync.changed(self, sync)

    def delete(self):

        task = self._ox.get_task(self.folder.id, self._key)

        if task.status and task.status == OxTask.get_status('Done'):
            if self.options.get('tasks_archive_folder'):
                target = self._ox.get_folder('tasks', self.options.get('tasks_archive_folder'))
                if target:
                    self._ox.move_task(self.folder, self.key, target)
                    Sync.delete(self)
                    return

        self._ox.delete_task(self.folder.id, self.key)
        Sync.delete(self)

    def get(self):
        task = self._ox.get_task(self.folder.id, self._key)
        return task

    def create(self, other):
        that = other.get()
        # other must provide 'title'
        if isinstance(that.title, str):
            title = that.title.decode('utf-8')
        else:
            title = that.title
        data = {'folder_id': self.folder.id, 'title': title}
        task = OxTask(data, self._ox)
        self.logger.info('%s: Creating task [%s] from %s' % (self.class_name, title, other.class_name))
        task = task.create()
        return self.update(other, that, task)
