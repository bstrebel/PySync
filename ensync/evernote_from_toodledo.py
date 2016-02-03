#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, re, logging
from pyutils import LogAdapter, strflocal, get_logger, utf8, string
from pysync import ThisFromThat
from ensync import EnClientSync
from tdapi import ToodledoTask


class EvernoteFromToodledo(ThisFromThat):

    priority_map = { -1: 'None', 0: 'Low', 1: 'Medium', 2: 'High', 3: 'High'}

    def __init__(self, engine, other):
        ThisFromThat.__init__(self, engine, other, 'en <- td')
        
    # def remove_evernote_link(self, content, tag):
    #     content = utf8(content + '\n')
    #     if content:
    #         pattern = '\n%s:.*https://www.evernote.com/.*\n' % (tag)
    #         return re.sub(pattern, '', content, re.MULTILINE)
    #     else:
    #         return ''

    def update(self, other, that=None, this=None, sid=None):

        from enapi import ENMLOfPlainText, PlainTextOfENML
        from oxapi import OxTask

        todo, note = ThisFromThat.update(self, other, that, this, sid)
        ensync = self._engine ;  enapi = self._engine.client
        tdsync = self._other; tdapi = self._other.client
        update = self._update
        maxsize = self.options.get('maxsize', 2048)

        note = note.load()
        note.title = string(todo.title)

        ###############################################
        # set evernote content for new or empty notes #
        ###############################################
        if not update:
            self.logger.info('%s: Updating note content' % (self.class_name))
            note.content = ENMLOfPlainText(todo.note.rstrip())
            if self.options.get('toodledo_sourceURL', True):
                if note.attributes.sourceURL is None:
                    note.attributes.sourceURL = todo.get_url(tdsync.options.get('permalink_id'))
            if self.options.get('toodledo_sourceApplication'):
                if note.attributes.sourceApplication is None:
                    note.attributes.sourceApplication = self.options.get('toodledo_sourceApplication', 'PySync')
            if self.options.get('toodledo_author'):
                note.attributes.author = self.options.get('toodledo_author')
        else:
            preserve = None
            if note.resources:
                preserve = "resources"
            else:
                if note.attributes.sourceURL:
                    url = tdsync.options.get('server_url','www.toodledo.com')
                    if not re.search(url, note.attributes.sourceURL, re.IGNORECASE):
                        preserve = "source URL"
                else:
                    if re.sub('\s', '', PlainTextOfENML(note.content), re.MULTILINE):
                        preserve = "content"
            if preserve:
                self.logger.info('%s: Found %s - preserving existing note content' % (self.class_name, preserve))
            else:
                content = todo.note
                if tdsync.options.get('evernote_iframe', 'False'):
                    content = ensync.remove_evernote_link(content, tdsync.options.get('evernote_iframe_tag', 'IFRAME'))
                if tdsync.options.get('evernote_link', 'False'):
                    content = ensync.remove_evernote_link(content, tdsync.options.get('evernote_link_tag', 'EVERNOTE'))
                note.content = ENMLOfPlainText(content.rstrip())
                self.logger.info('%s: Updating note content' % (self.class_name))

        ##############################
        # always update reminderTime #
        ##############################
        
        attribute = self.options.get('toodledo_reminderTime','duedate')
        if todo[attribute]:
            note.attributes.reminderTime = todo[attribute] * 1000
        else:
            note.attributes.reminderTime = None
            note.attributes.reminderOrder = None
        self.logger.info('%s: Updating note reminderTime from %s [%s]' % (self.class_name, attribute,
                                                                          strflocal(note.attributes.reminderTime, None)))        
        ###########################
        # update reminderDoneTime #
        ###########################
        
        if todo.completed:
            note.attributes.reminderDoneTime = todo.completed * 1000
            note.attributes.reminderTime = None
            note.attributes.reminderOrder = None
        else:
            note.attributes.reminderDoneTime = None
            
        self.logger.info('Update reminderDoneTime from [%s]' % (strflocal(todo.completed, None)))
        
        ##########################
        # process lists and tags #
        ##########################

        note.tagGuids = []
        note.tagNames = []

        if tdsync.options.get('evernote_tag_status'):
            tag = tdsync.options.get('evernote_tag_status') + ToodledoTask.STATUS[todo.status]
            note.tagNames.append(tag)
            self.logger.info('Create status tag [%s]' % (tag))
        
        if tdsync.options.get('evernote_tag_priority'):
            tag = tdsync.options.get('evernote_tag_priority') + self.priority_map[todo.priority]
            note.tagNames.append(tag)
            self.logger.info('Create priority tag [%s]' % (tag))
                
        if tdsync.options.get('evernote_tag_star'):
            if todo.star:
                tag = tdsync.options.get('evernote_tag_star')
                note.tagNames.append(tag)
                self.logger.info('Create star tag [%s]' % (tag))

        if tdsync.options.get('evernote_tag_context'):
            if todo.context:
                tag = tdsync.options.get('evernote_tag_context') + tdapi.contexts[todo.context]['name']
                note.tagNames.append(tag)
                self.logger.info('Create context tag [%s]' % (tag))

        if tdsync.options.get('evernote_tag_goal'):
            if todo.goal:
                tag = tdsync.options.get('evernote_tag_goal') + tdapi.goals[todo.goal]['name']
                note.tagNames.append(tag)
                self.logger.info('Create goal tag [%s]' % (tag))

        if tdsync.options.get('evernote_tag_location'):
            if todo.location:
                tag = tdsync.options.get('evernote_tag_location') + tdapi.locations[todo.location]['name']
                note.tagNames.append(tag)
                self.logger.info('Create location tag [%s]' % (tag))
            
        for tag in todo.tag_names():
            note.tagNames.append(tag)
            self.logger.info('Create category tag [%s]' % (tag))

        # perform the update (including the necessary encoding)
        note = self._engine._book.update_note(note)
        self.logger.info('%s: Updating completed with timestamp %s' % (self.class_name, strflocal(note.updated)))
        return note
