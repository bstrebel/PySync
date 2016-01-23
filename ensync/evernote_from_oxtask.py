#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, re, logging
from pyutils import LogAdapter, strflocal, get_logger
from pysync import ThisFromThat


class EvernoteFromOxTask(ThisFromThat):

    def __init__(self, engine, other):
        ThisFromThat.__init__(self, engine, other, 'en <- ox')

    def update(self, other, that=None, this=None):

        from enapi import ENMLOfPlainText, PlainTextOfENML
        from oxapi import OxTask

        task, note = ThisFromThat.update(self, other, that, this)

        update = self._update
        ox_task_sync = self._other

        note = note.load()
        note.title = task.title

        # set evernote content for new or empty notes
        if not update:
            self.logger.info('%s: Updating note content' % (self.class_name))
            note.content = ENMLOfPlainText(ox_task_sync.enlink_remove(task.note))
            if self.options.get('ox_sourceURL', True):
                if note.attributes.sourceURL is None:
                    note.attributes.sourceURL = task.get_url()
            if self.options.get('ox_sourceApplication'):
                if note.attributes.sourceApplication is None:
                    note.attributes.sourceApplication = self.options.get('ox_sourceApplication', 'OxPySync')
            if self.options.get('ox_author'):
                note.attributes.author = self.options.get('ox_author')
        else:
            preserve = None
            if note.resources:
                preserve = "resources"
            else:
                if note.attributes.sourceURL:
                    if not re.search(task.ox.server, note.attributes.sourceURL, re.IGNORECASE):
                        preserve = "source URL"
                else:
                    if re.sub('\s', '', PlainTextOfENML(note.content), re.MULTILINE):
                        preserve = "content"
            if preserve:
                self.logger.info('%s: Found %s - preserving existing note content' % (self.class_name, preserve))
            else:
                note.content = ENMLOfPlainText(ox_task_sync.enlink_remove(task.note))
                self.logger.info('%s: Updating note content' % (self.class_name))

        # always update reminderTime
        attribute = self.options.get('ox_reminderTime','end_time')
        if task._data.get(attribute):
            note.attributes.reminderTime = task._data.get(attribute)
            reminderTime = strflocal(task._data.get(attribute))
        else:
            note.attributes.reminderTime = None
            note.attributes.reminderOrder = None
            reminderTime = 'None'
        self.logger.info('%s: Updating note reminderTime from %s [%s]' % (self.class_name, attribute, reminderTime))

        # update note reminder status from task status
        if OxTask.get_status(task.status) == 'Done':

            if task._data.get('date_completed') is None:
                local = time.time()
                completed = long(local * 1000)
            else:
                completed = task.date_completed

            note.attributes.reminderDoneTime = completed
            note.attributes.reminderTime = None
            note.attributes.reminderOrder = None

            self.logger.info('%s: Updating reminder status from done task [%s]' %
                             (self.class_name, strflocal(completed)))

        # process categories and tags
        if task.categories:
            self.logger.info('%s: Updating tags from categories %s' % (self.class_name, task.categories))
            note.tagGuids = []
            note.tagNames = task.tagNames
        else:
            self.logger.info('%s: Removing tags from note' % (self.class_name))
            note.tagGuids = []
            note.tagNames = []

        if self.options.get('ox_status_tag'):
            if task.status:
                tag = self.options['ox_status_tag'] + OxTask.get_status(int(task.status))
                self.logger.info('%s: Add status tag %s to note' % (self.class_name, tag))
                note.tagNames.append(tag)

        if self.options.get('ox_priority_tag'):
            if task.priority:
                tag = self.options['ox_priority_tag'] + OxTask.get_priority(int(task.priority))
                self.logger.info('%s: Add priority tag %s to note' % (self.class_name, tag))
                note.tagNames.append(tag)

        if self.options.get('ox_private_tag'):
            private_tag = self.options['ox_private_tag']
            note_private_tag = False
            if private_tag in note.tagNames:
                note_private_tag = True
                note.tagNames.remove(private_tag)
            if task.private_flag:
                note.tagNames.append(private_tag)
                if not note_private_tag:
                    self.logger.info('%s: Add private tag %s to note' % (self.class_name, private_tag))
            else:
                if note_private_tag:
                    self.logger.info('%s: Remove private tag %s from note' % (self.class_name, private_tag))

        # perform the update
        note = self._engine._book.update_note(note)
        self.logger.info('%s: Updating completed with timestamp %s' % (self.class_name, strflocal(note.updated)))
        return note