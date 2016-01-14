#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, re, logging
from pyutils import LogAdapter, strflocal, get_logger

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

    @staticmethod
    def enlink_add(note, link):
        if note is None: note = ''
        note += "\nEVERNOTE: %s\n" % link
        return note

    @staticmethod
    def enlink_remove(note):
        if note:
            return re.sub('\nEVERNOTE: .*\n', '', note, re.MULTILINE)
        else:
            return ''

    def __init__(self, ox, options, logger=None):

        #self._name = options.get('folder')
        #self._id = options.get('id')
        self._key_attribute = options.get('key','title')
        self._maxsize = options.get('maxsize', 2048)
        self._folder = None

        Sync.__init__(self, options, logger, 'oxsync')
        OxTasks.__init__(self, ox)

        if options.get('signature') is None:
            self._folder = self._ox.get_folder('tasks', options.get('folder'))
            signature = {'label': options.get('label')}
            self._folder = self._ox.get_folder('tasks', options.get('folder'))
            signature['folder'] = self._folder.title
            signature['id'] = self._folder.id
            self.options.update({'signature': signature})

    def __repr__(self): return self.label

    def __str__(self): return self.label

    @property
    def class_name(self): return self.label

    @property
    def maxsize(self): return self._maxsize

    @maxsize.setter
    def maxsize(self, value): self._maxsize = value

    @property
    def name(self): return self.signature.get('folder')

    @property
    def id(self): return self.signature.get('id')

    @property
    def folder(self): return self.id if self.id else self.name

    def end_session(self):
        return self._ox.logout()

    def _check_filter(self, item):
        return True

    def sync_map(self):

        folder = self._ox.get_folder('tasks', self.folder)

        if folder:

            self._data = [];
            self._items = {}

            for task in self._ox.get_tasks(folder.id, ['id', 'last_modified', self._key_attribute]):
                if self._check_filter(task):
                    self._data.append(task)
                    item = {'id': task.id, 'time': task.last_modified + self._ox.utc_offset, 'key': task[self._key_attribute]}
                    self._add_item(task.id, item)

            return {'items': self.items, 'name': self.name, 'id': self.id}

        return None

    def map_item(self, ref=None):

        if isinstance(ref, OxTask):
            return {'id': ref.id, 'key': ref[self._key_attribute], 'time': ref.timestamp}
        else:
            return Sync.map_item(self, ref)

    def changed(self, sync):
        return Sync.changed(self, sync)

    def delete(self):

        task = self._ox.get_task(self.folder, self._key)

        if task.status and task.status == OxTask.get_status('Done'):
            if self.options.get('tasks_archive_folder'):
                target = self._ox.get_folder('tasks', self.options.get('tasks_archive_folder'))
                if target:
                    self._ox.move_task(self.folder, self.key, target)
                    Sync.delete(self)
                    return

        self._ox.delete_task(self.folder, self.key)
        Sync.delete(self)

    def get(self):
        task = self._ox.get_task(self.folder, self._key)
        return task

    def create(self, that):
        other = that.get()
        # other must provide 'title'
        if isinstance(other.title, str):
            title = other.title.decode('utf-8')
        else:
            title = other.title
        data = {'folder_id': self.id, 'title': title}
        task = OxTask(data, self._ox)
        self.logger.info('%s: Creating task [%s] from %s' % (self.class_name, title, other.__class__.__name__))
        task = task.create()
        return self.update(other, task)

    def update(self, that, task=None):
        """
        Update OxTask from other module
        :param that:    OtherClassSync (if called from sync)
                        OtherClassObject (if called from create)
        :param task:    None (if called from sync)
                        OxTask (just created)
        :return:        current timestamp of updated OxTask
        """
        from ensync import EnClientSync
        from enapi import EnNote
        other = that; update = False
        if task is None:
            update = True
            task = self.get().load()
            self.logger.info('%s: Updating task [%s] from %s' % (self.class_name, task.title, that.class_name))

        # check sync module type
        if isinstance(that, EnClientSync):
            other = that.get()

        # check sync object type
        if isinstance(other, EnNote):
            # create/update task from Evernote
            note = other.load(self.maxsize)
            # TODO: copy evernote attachments
            # TODO: create evernote html from content
            task._data['title'] = note.title

            if update:
                # update task from
                if task.number_of_attachments > 0:
                    for attachment in self._ox.get_attachments(task):
                        if attachment.filename.startswith(note.guid):
                            attachment.detach()

            # optional store evernote content as attachment
            if self.options.get('evernote_html', False):
                task.upload([{'content': note.html, 'mimetype': 'text/html', 'name': note.guid + '.html'}])
            if self.options.get('evernote_enml', False):
                task.upload([{'content': note.content, 'mimetype': 'text/xml', 'name': note.guid + '.enml'}])

            # reload and update timestamp
            task = task.load()

            # check content
            content = ''
            if self.options.get('evernote_sourceURL', True):
                if note.attributes.sourceURL:
                    if not note.attributes.sourceURL.startswith(self._ox.server):
                        self.logger.info('%s: Updating content with source URL %s' % (self.class_name, note.attributes.sourceURL))
                        content += "SOURCE: %s\n" % (note.attributes.sourceURL)

            if note.contentLength > self.maxsize:
                self.logger.info('%s: Evernote content exceeds limit of %d KB!' % (self.class_name, self.maxsize/1024))
                content += "Evernote content exceeds limit of %d KB!" % (self.maxsize/1024)
            else:
                content += note.plain

            if self.options.get('evernote_link', True):
                task._data['note'] = OxTaskSync.enlink_add(content, note.edit_url)

            # process other attributes

            # always update reminderTime from Evernote
            newtime = strflocal(note.attributes.reminderTime) if note.attributes.reminderTime is not None else 'None'
            attribute = self.options.get('evernote_reminderTime', 'end_date')
            task._data[attribute] = note.attributes.reminderTime
            self.logger.info('%s: Updating %s from note reminderTime [%s]' %
                             (self.class_name, attribute, newtime))

            # always update reminderDoneTime and task status
            oldstatus = int(task._data.get('status', 0))
            if note.attributes.reminderDoneTime is not None:
                newtime = strflocal(note.attributes.reminderTime)
                newstatus = OxTask.get_status('done')
            else:
                newtime = None
                if task._data.get('status') and OxTask.get_status(int(task._data['status'])) == 'Done':
                    # reset task status
                    newstatus = int(OxTask.get_status('In progress'))
                else:
                    # don't change
                    newstatus = int(task._data.get('status', 0))

            attribute = self.options.get('evernote_reminderDoneTime', 'date_completed')
            task._data[attribute] = note.attributes.reminderDoneTime
            self.logger.info('%s: Updating task %s from note reminderDoneTime [%s]' %
                             (self.class_name, attribute, newtime))

            task._data['status'] = newstatus

            if newstatus != oldstatus:
                self.logger.info('%s: Updating task status from [%s] to [%s]' %
                                 (self.class_name, OxTask.get_status(oldstatus), OxTask.get_status(newstatus)))

            # process categories
            self.logger.info('%s: Updating categories from tags %s' % (self.class_name, note.categories))

            status_prefix = None
            status_now = task.status
            status_new = status_now
            if self.options.get('evernote_tag_status'):
                status_prefix = unicode(self.options['evernote_tag_status'])
                status_new = OxTask.get_status('Not started')

            priority_prefix = None
            priority_now = int(task.priority) if task.priority is not None else None
            priority_new = priority_now
            if self.options.get('evernote_tag_priority'):
                priority_prefix = unicode(self.options['evernote_tag_priority'])
                priority_new = OxTask.get_priority('None')

            private_tag = None
            private_new = task.private_flag
            private_now = task.private_flag
            if self.options.get('evernote_tag_private'):
                private_tag = unicode(self.options['evernote_tag_private'])
                private_new = False

            categories = []
            for tag in note.categories.split(','):

                if status_prefix and tag.startswith(status_prefix):

                    status_new = OxTask.get_status(tag[1:].lower())
                    if status_now != status_new:
                        self.logger.info('%s: Updating task status to [%s]' % (self.class_name, OxTask.get_status(status_new)))

                elif priority_prefix and tag.startswith(priority_prefix):

                    priority_new = OxTask.get_priority(tag[1:].lower())
                    if priority_now != priority_new:
                        self.logger.info('%s: Updating task priority to [%s]' % (self.class_name, OxTask.get_priority(priority_new)))

                elif private_tag and tag == private_tag:

                        private_new = True
                        if private_now != private_new:
                            self.logger.info('%s: Updating private flag to [%s]' % (self.class_name, private_new))
                else:
                    categories.append(tag)

            task._data['status'] = status_new

            if priority_new == 0:
                # undocumented OX magic
                task._data['priority'] = 'null'
            else:
                task._data['priority'] = str(priority_new)

            task._data['private_flag'] = private_new

            # OxTask @categories.setter
            task.categories = categories

        else:
            # unknown sync object
            return None

        task._data['title'] = note.title
        task._data['full_time'] = False
        task = task.update()
        # task.load()
        # timestamp from api request is UTC: don't add self._utc_offset
        self.logger.info('%s: Updating completed with timestamp %s' % (self.class_name, strflocal(task.timestamp)))
        return self.map_item(task)
