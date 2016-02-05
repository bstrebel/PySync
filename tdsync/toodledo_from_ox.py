#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, re, logging
from pyutils import LogAdapter, strflocal, get_logger, import_code, utf8
from pysync import ThisFromThat

from tdapi import ToodledoTask, ToodledoContext, ToodledoFolder, ToodledoLocation, ToodledoGoal
from oxapi import OxTask

class ToodledoFromOxTask(ThisFromThat):

    status_map = {
        OxTask.get_status('unknown'): ToodledoTask.STATUS.index('None'),
        OxTask.get_status('Not started'): ToodledoTask.STATUS.index('Next'),
        OxTask.get_status('In progress'): ToodledoTask.STATUS.index('Active'),
        OxTask.get_status('Done'): ToodledoTask.STATUS.index('None'),
        OxTask.get_status('Waiting'): ToodledoTask.STATUS.index('Waiting'),
        OxTask.get_status('Deferred'): ToodledoTask.STATUS.index('Hold')
    }

    priority_map = {
        OxTask.get_priority('None'): None,
        OxTask.get_priority('Low'): ToodledoTask.PRIORITY['Low'],
        OxTask.get_priority('Medium'): ToodledoTask.PRIORITY['Medium'],
        OxTask.get_priority('High'): ToodledoTask.PRIORITY['High']
    }

    def __init__(self, engine, other):
        ThisFromThat.__init__(self, engine, other, 'td <- ox')

    @property
    def oxTaskSync(self):
        return self._other

    def update(self, other, that=None, this=None, sid=None):

        task, todo = ThisFromThat.update(self, other, that, this, sid)

        tdsync = self._engine
        tdapi = self._engine.client

        oxsync = self._other
        ox = self._other._ox

        update = self._update

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

# region Open-Xchange task attributes
        # modified_by, last_modified, folder_id, categories, private_flag, color_label
        # number_of_attachments, lastModifiedOfNewestAttachmentUTC,
        # title, start_date, end_date, note, alarm, date_completed
        # priority,status, percent_completed
        # actual_costs, actual_duration, billing_information, target_costs, target_duration, currency, trip_meter, companies
        # new columns available only since Rev. 7.6.1
        # but: works not for default folder Tasks
        # start_time,end_time, full_time
# endregion

        # todo.title = utf8(task.title)[:250]
        # todo.note = utf8(task.note)[:32000]

        title = task.title
        if title != todo.title:
            todo.title = title
            self.logger.info('Title changed to [%s]' % (title))

        note = task.note or u''
        if note != todo.note:
            todo.note = note

        DAY = 60*60 * 24
        OX_UTC_TIME = 0
        TD_UTC_TIME = 60*60 * 12

        # if time is not used for UTC start/due date OX uses 00:00 and
        # Toodledo defaults to 12:00 TD_UTC_TIME changes OX timestamps
        # to the Toodledo default

        startdate = task._start_date or 0
        if startdate:
            startdate = startdate - (startdate % DAY) + TD_UTC_TIME
        if startdate != todo.startdate:
            self.logger.info('Start date changed to [%s]' % (strflocal(startdate, None)))
        todo.startdate = startdate

        starttime = 0
        if task.full_time is not None and task.full_time == False:
            starttime = task._start_time_utc or 0
        if starttime != todo.starttime:
            self.logger.info('Start time changed to [%s]' % (strflocal(starttime,None)))
        todo.starttime = starttime

        duedate = task._end_date or 0
        if duedate:
            duedate = duedate - (duedate % DAY) + TD_UTC_TIME
        if duedate != todo.duedate:
            self.logger.info('Due date changed to [%s]' % (strflocal(duedate, None)))
        todo.duedate = duedate

        duetime = 0
        if task.full_time is not None and task.full_time == False:
            duetime = task._end_time_utc or 0
        if duetime != todo.duetime:
            self.logger.info('Due time changed to [%s]' % (strflocal(duetime, None)))
        todo.duetime = duetime

        remind = 0
        if task._end_date and task._alarm_date:
            seconds = task._end_date - task._alarm_date
            if seconds > 0:
                remind = seconds/60
            if remind != todo.remind:
                self.logger.info('Set reminder to %d minutes [%s]' % (remind, strflocal(task._alarm_date, None)))
        todo.remind = remind

        if task.status:
            status = self.status_map[task.status]
            if status != todo.status:
                todo.status = status
                #self.logger.info('Status changed to [%s]' % (ToodledoTask.STATUS[todo.status]))
                self.logger.info('Status changed to [%s]' % (todo.status))
        else:
            todo.status = 0

        if task.priority:
            priority = self.priority_map[int(task.priority)]
            if priority != todo.priority:
                todo.priority = priority
                #self.logger.info('Priority changed to [%s]' % (ToodledoTask.PRIORITY[todo.priority]))
                self.logger.info('Priority changed to [%s]' % (todo.priority))
        else:
            todo.priority = 0

        # todo.folder = tdsync._folder.id

        tags = []
        for tag in task.tag_names():
            if tag == tdsync.options.get('ox_tag_star', ','):
                todo.star = True
                self.logger.info('Set toodledo star from [%s]' % (tag))
            elif tag.startswith(tdsync.options.get('ox_tag_context', ',')):
                todo.context = tag[1:]
                self.logger.info('Set toodledo context from [%s]' % (tag))
            elif tag.startswith(tdsync.options.get('ox_tag_goal', ',')):
                todo.goal = tag[1:]
                self.logger.info('Set toodledo goal from [%s]' % (tag))
            elif tag.startswith(tdsync.options.get('ox_tag_location', ',')):
                todo.location = tag[1:]
                self.logger.info('Set toodledo location from [%s]' % (tag))
            elif tag.startswith(tdsync.options.get('ox_tag_status', ',')):
                todo.status = ToodledoTask.STATUS.index(tag[1:])
                self.logger.info('Set toodledo status from [%s]' % (tag))
            elif tag.startswith(tdsync.options.get('ox_tag_priority', ',')):
                todo.prority = ToodledoTask.PRIORITY[tag[1:]]
                self.logger.info('Set toodledo priority from [%s]' % (tag))
            else:
                tags.append(tag)
                self.logger.info('Set toodledo tag from [%s]' % (tag))

        if len(tags) > 0:
            todo.tag = ','.join(tags)[:250]

        # check completed status and time stamp
        completed = 0
        if OxTask.get_status(task.status) == 'Done':
            if task.date_completed is not None:
                # returned only once if status changes to 'Done'
                completed = task.date_completed/1000
            else:
                if todo.completed:
                    # stay with previous completd date
                    completed = todo.completed
                else:
                    # set a new one
                    completed = int(time.time())

        if completed != todo.completed:
            if completed:
                self.logger.info('Set task completed at [%s]' % (strflocal(completed)))
            else:
                self.logger.info('Reset completed date according to status [%s]' % (OxTask.get_status(task.status)))

        todo.completed = completed
        return todo
