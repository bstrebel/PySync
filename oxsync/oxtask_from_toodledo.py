#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pyutils import strflocal, utf8
from pysync import ThisFromThat

from tdapi import ToodledoTask, ToodledoContext, ToodledoFolder, ToodledoLocation, ToodledoGoal
from oxapi import OxTask


class OxTaskFromToodldo(ThisFromThat):

    status_map = {
        ToodledoTask.STATUS.index('None'): OxTask.get_status('Not started'),    #0
        ToodledoTask.STATUS.index('Next'): OxTask.get_status('Not started'),    #1
        ToodledoTask.STATUS.index('Active'): OxTask.get_status('In progress'),  #2
        ToodledoTask.STATUS.index('Planning'): OxTask.get_status('Not started'),#3
        ToodledoTask.STATUS.index('Delegated'): OxTask.get_status('Waiting'),   #4
        ToodledoTask.STATUS.index('Waiting'): OxTask.get_status('Waiting'),     #5
        ToodledoTask.STATUS.index('Hold'): OxTask.get_status('Deferred'),       #6
        ToodledoTask.STATUS.index('Postponed'): OxTask.get_status('Deferred'),  #7
        ToodledoTask.STATUS.index('Someday'): OxTask.get_status('Deferred'),    #8
        ToodledoTask.STATUS.index('Canceled'): OxTask.get_status('Deferred'),   #9
        ToodledoTask.STATUS.index('Reference'): OxTask.get_status('Deferred')   #10
    }

    priority_map = {
        -1: OxTask.get_priority('None'),
        0: OxTask.get_priority('Low'),
        1: OxTask.get_priority('Medium'),
        2: OxTask.get_priority('High'),
        3: OxTask.get_priority('High')
    }

    def __init__(self, engine, other):
        ThisFromThat.__init__(self, engine, other, 'ox <- td')

    def update(self, other, that=None, this=None, sid=None):

        todo, task = ThisFromThat.update(self, other, that, this, sid)
        oxsync = self._engine; ox = self._engine._ox
        tdsync = self._other; tdapi = self._other.client
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

        title = utf8(todo.title)
        if title != task.title:
            task.title = title
            self.logger.debug(u'Title changed to [%s]' % (title))
            
        note = utf8(todo.note)
        if note != task.note:
            task.note = note

        DAY = 60*60 * 24
        OX_UTC_TIME = 0
        TD_UTC_TIME = 60*60 * 12 

        full_time = None

        start_time = None
        start_date = None
        
        if todo._start_time:
            full_time = False 
            start_time = todo._start_time + (ox.utc_offset/1000)
            if start_time != task.start_time:
                self.logger.debug(u'Start time changed from [%s] to [%s]' % (strflocal(task.start_time, None),
                                                                           strflocal(start_time, None)))
        else:
            if todo._start_date:
                full_time = True
                start_date = todo._start_date - TD_UTC_TIME
            if start_date != task.start_date:
                self.logger.debug(u'Start date changed from [%s] to [%s]' % (strflocal(task.start_date, None),
                                                                           strflocal(start_date, None)))
                
        task.start_time = start_time
        task.start_date = start_date
        
        end_time = None
        end_date = None
        
        if todo._due_time:
            full_time = False 
            end_time = todo._due_time + (ox.utc_offset/1000)
            if end_time != task.end_time:
                self.logger.debug(u'end time changed from [%s] to [%s]' % (strflocal(task.end_time, None),
                                                                         strflocal(end_time, None)))
        else:
            if todo._due_date:
                full_time = True
                end_date = todo._due_date - TD_UTC_TIME
            if end_date != task.end_date:
                self.logger.debug(u'end date changed from [%s] to [%s]' % (strflocal(task.end_date, None),
                                                                         strflocal(end_date, None)))
                
        task.end_time = end_time
        task.end_date = end_date
        
        task.full_time = full_time

        alarm = None
        if todo._remind_date:
            alarm = todo._remind_date
        if alarm != task.alarm:
            self.logger.debug(u'Reminder changed from [%s] to [%s]' % (strflocal(task.alarm, None),
                                                                     strflocal(alarm, None)))
        task.alarm = alarm

        tags = []
        prefix_used = []
        categories = u''

        status = 0
        if not todo.completed:    
            if todo.status is not None:
                status = self.status_map[todo.status]
                if tdsync.options.get('ox_tag_status'):
                    prefix = tdsync.options.get('ox_tag_status')
                    if todo.status not in [0, 1, 2, 5]:
                        # map to extended status tag
                        tag = prefix + ToodledoTask.STATUS[todo.status]
                        tags.append(tag)
                        prefix_used.append(prefix)
                        self.logger.debug(u'Create extended status tag [%]' % (tag))
        else:
            status = OxTask.get_status('Done')
            # task.date_completed = todo._date_completed
            
        if status != task.status:
            self.logger.debug(u'Status changed from [%s] to [%s]' % (task.status, status))
        task.status = status

        priority = None
        if todo.priority is not None:
            priority = self.priority_map[todo.priority]
            if tdsync.options.get('ox_tag_priority'):
                prefix = tdsync.options.get('ox_tag_priority')
                if todo.priority == -1:
                    tag = utf8(prefix + 'Negative')
                    tags.append(tag)
                    prefix_used.append(prefix)
                    self.logger.debug(u'Create extendend priority tag [%s]' % (tag))
                elif todo.priority == 3:
                    tag = utf8(prefix + 'Top')
                    tags.append(tag)
                    prefix_used.append(prefix)
                    self.logger.debug(u'Create extendend priority tag [%s]' % (tag))
                else:
                    pass

        if priority != task.priority:
            self.logger.debug(u'Priority changed from [%s] to [%s]' % (task.priority, priority))
        task.priority = priority

        if tdsync.options.get('ox_tag_star'):
            if todo.star:
                tag = tdsync.options.get('ox_tag_star')
                tags.append(tag)
                self.logger.debug(u'Create star tag [%s]' % (tag))

        if tdsync.options.get('ox_tag_context'):
            if todo.context:
                tag = tdsync.options.get('ox_tag_context') + tdapi.contexts[todo.context]['name']
                tags.append(tag)
                self.logger.debug(u'Create context tag [%s]' % (tag))

        if tdsync.options.get('ox_tag_goal'):
            if todo.goal:
                tag = tdsync.options.get('ox_tag_goal') + tdapi.goals[todo.goal]['name']
                tags.append(tag)
                self.logger.debug(u'Create goal tag [%s]' % (tag))

        if tdsync.options.get('ox_tag_location'):
            if todo.location:
                tag = tdsync.options.get('ox_tag_location') + tdapi.locations[todo.location]['name']
                tags.append(tag)
                self.logger.debug(u'Create location tag [%s]' % (tag))

        for tag in todo.tag_names():
            if tag == tdsync.options.get('ox_tag_star', ','):
                continue
            elif tag.startswith(tdsync.options.get('ox_tag_context', ',')):
                continue
            elif tag.startswith(tdsync.options.get('ox_tag_goal', ',')):
                continue
            elif tag.startswith(tdsync.options.get('ox_tag_location', ',')):
                continue
            elif tag.startswith(tdsync.options.get('ox_tag_status', ',')):
                continue
            elif tag.startswith(tdsync.options.get('ox_tag_priority', ',')):
                continue
            else:
                tags.append(tag)
                self.logger.debug(u'Create category tag [%s]' % (tag))

        if len(tags) > 0:
            categories = u','.join(tags)
        if categories != task.categories:
            self.logger.debug(u'Categories changed from [%s] to [%s]' % (task.categories, categories))
        task.categories = categories

        task.notification = True
        task._data['full_time'] = False

        task = task.update()
        task.load()
        self.logger.debug(u'%s: Updating completed with timestamp %s' % (self.class_name, strflocal(task.timestamp)))
        return task
