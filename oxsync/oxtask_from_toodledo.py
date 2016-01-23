#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pyutils import strflocal

from pysync import ThisFromThat
class OxTaskFromToodldo(ThisFromThat):

    def __init__(self, engine, other):
        ThisFromThat.__init__(self, engine, other, 'ox <- td')

    def update(self, other, that=None, this=None):

        todo, task = ThisFromThat.update(self, other, that, this)

        ox = self._engine._ox
        maxsize = self._engine.maxsize
        update = self._update

        from oxsync import OxTaskSync
        from oxapi import OxTask

        task['title'] = todo.title

        # if update:
        #     # update task from
        #     if task.number_of_attachments > 0:
        #         for attachment in self._ox.get_attachments(task):
        #             if attachment.filename.startswith(note.guid):
        #                 attachment.detach()
        #
        # # optional store evernote content as attachment
        # if self.options.get('evernote_html', False):
        #     task.upload([{'content': note.html, 'mimetype': 'text/html', 'name': note.guid + '.html'}])
        # if self.options.get('evernote_enml', False):
        #     task.upload([{'content': note.content, 'mimetype': 'text/xml', 'name': note.guid + '.enml'}])
        #
        # # reload and update timestamp
        # task = task.load()
        #
        # ########################
        # # process task content #
        # ########################
        #
        # content = ''
        # if self.options.get('evernote_sourceURL', True):
        #     if note.attributes.sourceURL:
        #         if not note.attributes.sourceURL.startswith(self._ox.server):
        #             self.logger.info('%s: Updating content with source URL %s' % (self.class_name, note.attributes.sourceURL))
        #             content += "SOURCE: %s\n" % (note.attributes.sourceURL)
        #
        # if note.contentLength > self.maxsize:
        #     self.logger.info('%s: Evernote content exceeds limit of %d KB!' % (self.class_name, self.maxsize/1024))
        #     content += "Evernote content exceeds limit of %d KB!" % (self.maxsize/1024)
        # else:
        #     content += note.plain
        #
        # if self.options.get('evernote_link', True):
        #     tag = self.options.get('evernote_link_tag', 'EVERNOTE')
        #     content = OxTaskSync.enlink_add(content, note.edit_url, tag)
        #
        # if self.options.get('evernote_iframe', True):
        #     tag = self.options.get('evernote_iframe_tag', 'IFRAME')
        #     content = OxTaskSync.enlink_add(content, note.view_url, tag)
        #
        # task._data['note'] = content
        #
        # ############################
        # # process other attributes #
        # ############################
        #
        # # always update reminderTime from Evernote
        # newtime = strflocal(note.attributes.reminderTime) if note.attributes.reminderTime is not None else 'None'
        # attribute = self.options.get('evernote_reminderTime', 'end_date')
        # task._data[attribute] = note.attributes.reminderTime
        # self.logger.info('%s: Updating %s from note reminderTime [%s]' %
        #                  (self.class_name, attribute, newtime))
        #
        # # always update reminderDoneTime and task status
        # oldstatus = int(task._data.get('status', 0))
        # if note.attributes.reminderDoneTime is not None:
        #     newtime = strflocal(note.attributes.reminderTime)
        #     newstatus = OxTask.get_status('done')
        # else:
        #     newtime = None
        #     if task._data.get('status') and OxTask.get_status(int(task._data['status'])) == 'Done':
        #         # reset task status
        #         newstatus = int(OxTask.get_status('In progress'))
        #     else:
        #         # don't change
        #         newstatus = int(task._data.get('status', 0))
        #
        # attribute = self.options.get('evernote_reminderDoneTime', 'date_completed')
        # task._data[attribute] = note.attributes.reminderDoneTime
        # self.logger.info('%s: Updating task %s from note reminderDoneTime [%s]' %
        #                  (self.class_name, attribute, newtime))
        #
        # task._data['status'] = newstatus
        #
        # if newstatus != oldstatus:
        #     self.logger.info('%s: Updating task status from [%s] to [%s]' %
        #                      (self.class_name, OxTask.get_status(oldstatus), OxTask.get_status(newstatus)))
        #
        # ######################
        # # process categories #
        # ######################
        #
        # self.logger.info('%s: Updating categories from tags %s' % (self.class_name, note.categories))
        #
        # status_prefix = None
        # status_now = task.status
        # status_new = status_now
        # if self.options.get('evernote_tag_status'):
        #     status_prefix = unicode(self.options['evernote_tag_status'])
        #     status_new = OxTask.get_status('Not started')
        #
        # priority_prefix = None
        # priority_now = int(task.priority) if task.priority is not None else None
        # priority_new = priority_now
        # if self.options.get('evernote_tag_priority'):
        #     priority_prefix = unicode(self.options['evernote_tag_priority'])
        #     priority_new = OxTask.get_priority('None')
        #
        # private_tag = None
        # private_new = task.private_flag
        # private_now = task.private_flag
        # if self.options.get('evernote_tag_private'):
        #     private_tag = unicode(self.options['evernote_tag_private'])
        #     private_new = False
        #
        # categories = []
        # for tag in note.categories.split(','):
        #
        #     if status_prefix and tag.startswith(status_prefix):
        #
        #         status_new = OxTask.get_status(tag[1:].lower())
        #         if status_now != status_new:
        #             self.logger.info('%s: Updating task status to [%s]' % (self.class_name, OxTask.get_status(status_new)))
        #
        #     elif priority_prefix and tag.startswith(priority_prefix):
        #
        #         priority_new = OxTask.get_priority(tag[1:].lower())
        #         if priority_now != priority_new:
        #             self.logger.info('%s: Updating task priority to [%s]' % (self.class_name, OxTask.get_priority(priority_new)))
        #
        #     elif private_tag and tag == private_tag:
        #
        #             private_new = True
        #             if private_now != private_new:
        #                 self.logger.info('%s: Updating private flag to [%s]' % (self.class_name, private_new))
        #     else:
        #         categories.append(tag)
        #
        # task._data['status'] = status_new
        #
        # if priority_new == 0:
        #     # undocumented OX magic
        #     task._data['priority'] = 'null'
        # else:
        #     task._data['priority'] = str(priority_new)
        #
        # task._data['private_flag'] = private_new
        #
        # # OxTask @categories.setter
        # task.categories = categories
        # task._data['title'] = note.title
        # task._data['full_time'] = False

        task = task.update()
        task.load()
        self.logger.info('%s: Updating completed with timestamp %s' % (self.class_name, strflocal(task.timestamp)))
        return task
