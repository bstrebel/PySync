#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, re, logging
from pyutils import LogAdapter, strflocal, get_logger, utf8

from pysync import Sync, SyncSessionError, SyncInitError, SyncError
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
                            if ox and ox.authenticated:
                                return ox
                            else:
                                raise SyncSessionError('Login for [%s] at [%s] failed!' % (secrets['user'], secrets['server']))
                                return None

        LogAdapter(_logger, {'package': 'oxsync'}).error('Missing credentials in Open-Xchange options')
        raise SyncSessionError('Missing credentials in Open-Xchange options')
        return None

    def __init__(self, ox, options, logger=None):

        self._key_attribute = options.get('key','title')
        self._maxsize = options.get('maxsize', 2048)
        self._folder = None
        self._archive = None

        Sync.__init__(self, options, logger, 'oxsync')
        OxTasks.__init__(self, ox)

        if self.signature is None:
            signature = {'label': options.get('label')}
            if options.get('folder') is not None:
                self._folder = self._ox.get_folder('tasks', utf8(options['folder']))
                self.logger.debug(u'Using folder [%s]: %s' % (self._folder.id, utf8(self._folder.title)))
                if self._folder is not None:
                    signature['folder'] = self._folder.title
                    signature['id'] = self._folder.id
                    if options.get('archive'):
                        self._archive = self._ox.get_folder('tasks', utf8(options['archive']))
                        self.logger.debug(u'Using archive folder [%s]: %s' % (self._archive.id, utf8(self._archive.title)))
                        if self._archive is not None:
                            signature['archive'] = self._archive.id
                        else:
                            error = u'Archive folder [%s] not found!' % (utf8(options['archive']))
                            # self.logger.error(error)
                            raise SyncInitError(error)
                    self.options.update({'signature': signature})
                else:
                    error = u'Folder [%s] not found!' % (utf8(options['folder']))
                    # self.logger.error(error)
                    raise SyncInitError(error)
            else:
                error = u'No folder specified in in sync options!'
                # self.logger.error(error)
                raise SyncInitError(error)
        else:
            if self.signature.get('id'):
                self._folder = self._ox.get_folder('tasks', self.signature['id'])
                if self._folder is not None:
                    self.logger.debug(u'Using folder [%s]: %s' % (self._folder.id, utf8(self._folder.title)))
                else:
                    error = u'Folder [%s] from map file not found!' % (self.signature['id'])
                    # self.logger.error(error)
                    raise SyncInitError(error)

            if self.signature.get('archive'):
                self._archive = self._ox.get_folder('tasks', self.signature['archive'])
                if self._folder is not None:
                    self.logger.debug(u'Using folder [%s]: %s' % (self._archive.id, utf8(self._archive.title)))
                else:
                    error = u'Archive folder [%s] from map file not found!' % (self.signature['archive'])
                    # self.logger.error()
                    raise SyncInitError(error)

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

    @classmethod
    def end_session(cls, logger, **kwargs):
        logger.debug(u'End session called for %s' % (cls))
        try:
            ox = OxHttpAPI.get_session()
            if ox and ox.authenticated:
                ox.logout()
        except Exception as e:
            logger.exception('Unknown error in end_session!')
        OxHttpAPI.set_session(None)

    def _check_filter(self, item):
        return True

    def map_item(self, ref=None):
        if isinstance(ref, OxTask):
            return {'id': ref.id, 'key': ref[self._key_attribute], 'time': ref.timestamp}
        else:
            return Sync.map_item(self, ref)

    def sync_map(self, last=None):

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

    def delete(self, sid=None):

        try:
            task = self._ox.get_task(self.folder.id, self.key)
        except Exception as e:
            self.logger.exception('Error loading task details for task [%s]: %s' % (self.key, self.title))
            return None

        if task.status and task.status == OxTask.get_status('Done'):
            if self._archive is not None:
                self.logger.debug(u'Moving completed task [%s] to archive [%s]' % (task.title, self._archive.title))
                try:
                    self._ox.move_task(self.folder.id, self.key, self._archive)
                except Exception as e:
                    self.logger.exception('Error moving completed task to archive [%s]: %s' % (self._archive.id, self._archive.title))
                    return None
                Sync.delete(self, sid)
                return

        self.logger.debug(u'Deleting task [%s]: %s' % (task.id, task.title))
        try:
            self._ox.delete_task(self.folder.id, self.key)
        except Exception as e:
            self.logger.exception('Error deleting task [%s]: %s' % (self.key, self.title))
            return None
        self._deleted[sid] = self._items[self.key]
        Sync.delete(self, sid)

    def get(self):
        try:
            task = self._ox.get_task(self.folder.id, self._key)
        except Exception as e:
            self.logger.exception('Error loading task details fro [%s]: %s' % (self.key, self.title))
            return None
        return task

    def create(self, other, sid=None):
        that = other.get()
        # other must provide 'title'
        if that:
            title = utf8(that.title)
            data = {'folder_id': self.folder.id, 'title': title}
            task = OxTask(data, self._ox)
            self.logger.debug(u'%s: Creating task [%s] from %s' % (self.class_name, title, other.class_name))
            try:
                task = task.create()
            except Exception as e:
                self.logger.exception('Error creating task [%s]' % (title))
                return None
            if sid is not None:
                self._created[sid] = task
            return self.update(other, that, task, sid=sid)
        return None
