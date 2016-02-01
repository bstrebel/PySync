#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, re, logging
from pyutils import LogAdapter, strflocal, get_logger, import_code, utf8
from pysync import ThisFromThat

from tdapi import ToodledoTask, ToodledoContext, ToodledoFolder, ToodledoLocation, ToodledoGoal
from enapi import EnNote
from ensync import EnClientSync

class ToodledoFromEvernote(ThisFromThat):

# region Status map
    status_map = {
        'Unknown': ToodledoTask.STATUS.index('None'),
        'Not started': ToodledoTask.STATUS.index('Next'),
        'In progress': ToodledoTask.STATUS.index('Active'),
        'Done': ToodledoTask.STATUS.index('None'),
        'Waiting': ToodledoTask.STATUS.index('Waiting'),
        'Deferred': ToodledoTask.STATUS.index('Hold')
    }
# endregion

#region Priority map
    priority_map = {
        'None': None,
        'Low': ToodledoTask.PRIORITY['Low'],
        'Medium': ToodledoTask.PRIORITY['Medium'],
        'High': ToodledoTask.PRIORITY['High']
    }
#endregion

    def __init__(self, engine, other):
        ThisFromThat.__init__(self, engine, other, 'td <- en')

    def update(self, other, that=None,  this=None):

        note, todo = ThisFromThat.update(self, other, that, this)

        tdsync = self._engine; tdapi = self._engine.client
        ensync = self._other ;  enapi = self._other.client
        update = self._update
        maxsize = self.options.get('maxsize', 2048)
        server_url = self.options.get('server_url')

# region Toodledo task attributes
        # id, title, note, modified, completed, added
        # folder, context, goal, location, tag,
        # startdate, duedate, duedatemod, starttime, duetime,
        # remind, repeat,
        # status, star, priority,
        # length, timer
        # parent, children, order,
        # meta, previous, attachment,
        # shared, addedby, via, attachments
# endregion

# region Evernote note attributes
        # title, content, contentLength, plain, html
        # attributes.sourceURL
# endregion

        note = note.load()
        title = utf8(note.title)
        if title != todo.title:
            todo.title = title
            self.logger.info('Title changed to [%s]' % (title))

        ########################
        # process task content #
        ########################

        content = ''
        if note.contentLength > maxsize:
            self.logger.info('%s: Evernote content exceeds limit of %d KB!' % (self.class_name, maxsize/1024))
            content += "Evernote content exceeds limit of %d KB!\n" % (maxsize/1024)
        else:
            content += note.plain.strip() + '\n\n'

        if self.options.get('evernote_sourceURL', True):
            if note.attributes.sourceURL:
                if not note.attributes.sourceURL.startswith(server_url):
                    self.logger.info('%s: Updating content with source URL %s' % (self.class_name, note.attributes.sourceURL))
                    content += 'SOURCE: %s\n\n' % (note.attributes.sourceURL)

        if self.options.get('evernote_link', True):
            tag = self.options.get('evernote_link_tag', 'EVERNOTE')
            content = ensync.add_evernote_link(content, note.edit_url, tag)

        if self.options.get('evernote_iframe', True):
            tag = self.options.get('evernote_iframe_tag', 'IFRAME')
            content = ensync.add_evernote_link(content, note.view_url, tag)

        content = utf8(content) or u''
        if content != todo.note:
            todo.note = content
            # self.logger.info('Note changed to [%s]' % (content[:16]))

        ############################
        # process other attributes #
        ############################

        # always update reminderTime from Evernote
        attribute = self.options.get('evernote_reminderTime')
        if attribute:
            if note.attributes.reminderTime:
                reminderTime = note.attributes.reminderTime/1000
                todo[attribute] = reminderTime
                if attribute == 'duetime':
                    todo['duedate'] = todo['duetime']
                if attribute == 'starttime':
                    todo['startdate'] = todo['starttime']
            else:
                todo[attribute] = 0
            if attribute == 'duetime':
                todo['duedate'] = todo['duetime']
            if attribute == 'starttime':
                todo['startdate'] = todo['starttime']
            self.logger.info('%s: Updating [%s] from note reminderTime [%s]' %
                             (self.class_name, attribute, strflocal(note.attributes.reminderTime, None)))

        # always update reminderDoneTime and task status
        completed = note.attributes.reminderDoneTime/1000 if note.attributes.reminderDoneTime else 0
        todo.completed = completed

        ######################
        # process categories #
        ######################

        tags = []

        self.logger.info('%s: Updating categories from tags %s' % (self.class_name, note.categories))

        for tag in note.tags:
            if tag == tdsync.options.get('evernote_tag_star', ','):
                todo.star = True
                self.logger.info('Set toodledo star from [%s]' % (tag))
            elif tag.startswith(tdsync.options.get('evernote_tag_context', ',')):
                todo.context = tag[1:]
                self.logger.info('Set toodledo context from [%s]' % (tag))
            elif tag.startswith(tdsync.options.get('evernote_tag_goal', ',')):
                todo.goal = tag[1:]
                self.logger.info('Set toodledo goal from [%s]' % (tag))
            elif tag.startswith(tdsync.options.get('evernote_tag_location', ',')):
                todo.location = tag[1:]
                self.logger.info('Set toodledo location from [%s]' % (tag))
            elif tag.startswith(tdsync.options.get('evernote_tag_status', ',')):
                if tag[1:] not in ToodledoTask.STATUS:
                    if self.status_map.get(tag[1:]) is None:
                        self.logger.warning('Ignoring unknown status tag [%s]' % (tag))
                        status = ToodledoTask.STATUS.index('None')
                    else:
                        status = self.status_map.get(tag[1:])
                else:
                    status = ToodledoTask.STATUS.index(tag[1:])
                    self.logger.info('Set toodledo status from [%s]' % (tag))
                todo.status = status
            elif tag.startswith(tdsync.options.get('evernote_tag_priority', ',')):
                priority = ToodledoTask.PRIORITY.get(tag[1:])
                if priority is None:
                    self.logger.warning('Change unknown priority tag [%s] to [Low]' % (tag))
                    priority = ToodledoTask.PRIORITY.get(tag[1:], 'Low')
                else:
                    self.logger.info('Set toodledo priority [%s] from [%s]' % (priority, tag))
                todo.priority = priority
            else:
                tags.append(utf8(tag))
                self.logger.info(u'Set toodledo tag from [%s]' % (tag))

        todo.tag = u''
        if len(tags) > 0:
            todo.tag = u','.join(tags)

        return todo

