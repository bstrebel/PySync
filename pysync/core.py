#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import print_function

import os, sys, uuid, logging, logging.config, json, codecs, time, pyutils

# sys.path = ['/usr/local/lib/python2.7/dist-packages'] + sys.path
from pyutils import Options, LogAdapter, strflocal, get_logger, log_level

# sync engine declarations

class PySync(object):

    def __init__(self, left=None, right=None, opts=None, logger=None):

        if logger is None:
            self._logger = get_logger('pysync', logging.DEBUG)
        else:
            self._logger = logger

        self._adapter = LogAdapter(self._logger, {'package': 'pysync'})

        self.logger.debug(u'Initalizing PySync with %s and %s ...' % (left, right))

        self._opts = opts
        self._left = left
        self._right = right
        self._sync = opts['sync']
        self._new_sync = None

    @property
    def reverse_map(self): return {'left': 'right', 'right': 'left'}

    @property
    def engine_map(self): return {self._opts['left']: 'left', self._opts['right']: 'right'}

    @property
    def logger(self): return self._adapter

    @property
    def left(self): return self._left

    @property
    def right(self): return self._right

    @property
    def opts(self): return self._opts

    @property
    def unidirectional(self):
        # return bool(self.opts.get('unidirectional'))
        false = ['false', 'off', '0', 'none']
        return type(self.opts['unidirectional']) is str and self.opts['unidirectional'].lower() not in false

    @property
    def bidirectional(self): return bool(not self.unidirectional)

    @property
    def direction(self): return 'unidirectional' if self.unidirectional else 'bidirectional'

    @property
    def unidirectional_strict(self):
        return isinstance(self.opts['unidirectional'], str) and self.opts['unidirectional'].lower() == 'strict'


    @property
    def sync(self): return self._sync['map']

    @sync.setter
    def sync(self, value): self._sync['map'] = value

    def _add_item(self, sid, lr, item):

        sync = self.sync if self._new_sync is None else self._new_sync

        if sid not in sync:
            sync[sid] = {}

        if item is not None:

            key = item.get('key')

            if key is not None:
                if 'key' not in sync[sid]:
                    sync[sid]['key'] = key
                del(item['key'])

        sync[sid][lr] = item
        #self.logger.debug(u'%s: %-5s %s %s' % (sid, lr, key, item))

# region Test UTF-8 decoding
            # if isinstance(key, str):
            #     sync[sid]['key'] = key.decode('utf-8')
            # else:
            #     sync[sid]['key'] = key

            # if 'key' in sync[sid]:
            #     if key != sync[sid]['key']:
            #         self.logger.warning('%s: Found different keys [%s] <> [%s]' % (sid, key, sync[sid]['key']))
            # else:
# endregion

    def update(self, update):

        if update.lower() in self.reverse_map:
            left_right = self.reverse_map.get(update.lower())
        else:
            left_right = self.engine_map.get(update)
            if left_right:
                left_right = self.reverse_map.get(left_right)

        if left_right:

            engine = self._opts[self.reverse_map.get(left_right)]
            self.logger.debug(u'Running update for %s on the %s side ...' % (engine, self.reverse_map.get(left_right)))

            for sid in self._sync['map']:

                id = self._sync['map'][sid][left_right]['id']

                self.logger.debug(u'%s: Force update of [%s] at %s' % (id, self._sync['map'][sid]['key'], engine))
                self.logger.debug(u'%s: %s' % (id, self._sync['map'][sid][left_right]))

                self._sync['map'][sid][left_right]['time'] = 0L

        else:

            self.logger.warning('Invalid update option [%s] ignored!')

        return self._sync

    def reset(self, reset):

        if reset.lower() in self.reverse_map:
            left_right = reset.lower()
        else:
            left_right = self.engine_map.get(reset)
            if left_right:
                left_right = self.reverse_map.get(left_right)

        if left_right:

            engine = self._opts[left_right]
            self.logger.debug(u'Running reset for %s on the %s side ...' % (engine, left_right))

            if left_right == 'left':
                sync = self._left
            else:
                sync = self._right

            sync.sync_map()

            for sid in self._sync['map']:

                id = self._sync['map'][sid][left_right]['id']
                self.logger.debug(u'%s: Found [%s] at %s in sync map' % (id, self._sync['map'][sid]['key'], engine))

                if id in sync:
                    # item exists
                    item = sync[id]
                    # self.logger.debug(u'%s: Item deleted at %s' % (id, sync))
                    sync.delete(sid)
                else:
                    self.logger.debug(u'%s: Skip missing item at %s' % (id, sync))

            self._sync['map'] = None

        else:

            self.logger.warning('Invalid update option [%s] ignored!')

        return self._sync

    def last_map(self, left_right):
        if self._sync.get('map'):
            last_map = {}
            for sid in self._sync['map']:
                id = self._sync['map'][sid][left_right]['id']
                last_map[id] = self._sync['map'][sid][left_right]
            return last_map
        return None

    def process(self):

        left = self._left
        right = self._right

        left_last = self.last_map('left') if left.need_last_map else None
        right_last = self.last_map('right') if right.need_last_map else None

        left_map = left.sync_map(last=left_last)
        right_map = right.sync_map(last=right_last)

        if self.sync is None:
            """
            Initial sync: create sync_map
            """
            found = {}
            self.sync = {}
            self._new_sync = None

            self.logger.debug(u'Initalizing [%s] sync map ...' % (self.direction))
            self.logger.debug(u'Checking left side: %s' % (self.left))
            for key in left:

                sid = str(uuid.uuid1())
                self._add_item(sid, 'left', left.map_item(key))

                # find items by key
                guid = right.find_key(left[key]['key'])
                if guid:
                    found[guid] = True
                    self.logger.debug(u'Found matching item [%s] at %s' % (left[key]['key'], self.right))
                    self._add_item(sid, 'right', right.map_item(guid))
                else:
                    # create missing item on right side
                    self.logger.debug(u'Create missing item [%s] at %s' % (left[key]['key'], self.right))
                    item = right.create(left, sid)
                    self._add_item(sid, 'right', item)

            if self.bidirectional:

                self.logger.debug(u'Checking right side: %s' % (self.right))
                for key in right:

                    if key not in found:
                        # new key on the right side
                        sid = str(uuid.uuid1())
                        self.logger.debug(u'Create missing item [%s] at %s' % (right[key]['key'], self.left))
                        self._add_item(sid, 'right', right.map_item(key))
                        item = left.create(right, sid)
                        self._add_item(sid, 'left', item)

            # return self._sync

        else:
            """
            Update existing sync map
            """
            self._new_sync = {}

            self.logger.debug(u'Processing [%s] sync map ...' % (self.direction))

            for sid in self.sync:

                lid = self.sync[sid]['left']['id']
                rid = self.sync[sid]['right']['id']

                self.logger.debug(u'%s: %s' % (sid, self.sync[sid]['key']) )
                self.logger.debug(u'%s: %s %s' % (sid, self._left, self.sync[sid]['left']))
                self.logger.debug(u'%s: %s %s' % (sid, self._right, self.sync[sid]['right']))

                if lid in left:
                    # left item exitst
                    litem = left[lid]
                else:
                    # item deleted on left side
                    # => delete right item
                    if rid in right:
                        self.logger.debug(u'%s: Item deleted at %s' % (sid, self.left))
                        right.delete(sid)
                    continue

                if rid in right:
                    # right item exitst
                    ritem = right[rid]
                else:
                    if self.bidirectional:
                        # item deleted on right side
                        # => delete left item
                        if lid in left:
                            self.logger.debug(u'%s: Item deleted at %s' % (sid, self.right))
                            left.delete(sid)
                    continue

                # both items exists: compare and update sync map
                # ltime =  self.sync[sid]['left']['time']
                # rtime =  self.sync[sid]['right']['time']

                lsync = self.sync[sid]['left']
                rsync = self.sync[sid]['right']

                if left.changed(lsync):
                    self.logger.debug(u'%s: Item changed at left %s' % (sid, self.left))
                    if right.changed(rsync):
                        self.logger.debug(u'%s: Item also changed at right %s' % (sid, self.right))
                        if litem['time'] < ritem['time']:
                            self.logger.debug(u'%s: Item newer at right %s ' % (sid, self.right))
                            if self.bidirectional:
                                self.logger.debug(u'%s: Updating left item at %s' % (sid, self.left))
                                litem = left.update(right, sid=sid)
                            else:
                                self.logger.debug(u'%s: Undo changes for right item at %s' % (sid, self.right))
                                ritem = right.update(left, sid=sid)
                        else:
                            self.logger.debug(u'%s: Item newer at left %s ' % (sid, self.left))
                            self.logger.debug(u'%s: Updating right item at %s' % (sid, self.right))
                            ritem  = right.update(left, sid=sid)
                    else:
                        self.logger.debug(u'%s: Updating right item at %s' % (sid, self.right))
                        ritem = right.update(left, sid=sid)
                else:
                    if right.changed(rsync):
                        self.logger.debug(u'%s: Item changed at right %s' % (sid, self.right))
                        if self.bidirectional:
                            self.logger.debug(u'%s: Updating left item at %s' % (sid, self.left))
                            litem = left.update(right, sid=sid)
                        else:
                            self.logger.debug(u'%s: Undo changes for right item at %s' % (sid, self.right))
                            ritem = right.update(left, sid=sid)

                self._add_item(sid, 'left', litem)
                self._add_item(sid, 'right', ritem)

                del left[lid]
                del right[rid]

            self.logger.debug(u'Checking for new items at %s' % (self.left))
            for key in left:
                # new items on the left side
                sid = str(uuid.uuid1())
                ritem = right.create(left, sid)

                self._add_item(sid, 'left', left.map_item())
                self._add_item(sid, 'right', ritem)

                self.logger.debug(u'%s: [%s]' % (sid, self._new_sync[sid]['key']) )
                self.logger.debug(u'%s: %s %s' % (sid, self.left, self._new_sync[sid]['left']))
                self.logger.debug(u'%s: %s %s' % (sid, self.right, self._new_sync[sid]['right']))

            self.logger.debug(u'Checking for new items at %s' % (self.right))
            for key in right:
                # new items on the right side
                if self.bidirectional:
                    sid = str(uuid.uuid1())
                    litem = left.create(right, sid)

                    self._add_item(sid, 'right', right.map_item())
                    self._add_item(sid, 'left', litem)

                    self.logger.debug(u'%s: [%s]' % (sid, self._new_sync[sid]['key']) )
                    self.logger.debug(u'%s: %s %s' % (sid, self.left, self._new_sync[sid]['left']))
                    self.logger.debug(u'%s: %s %s' % (sid, self.right, self._new_sync[sid]['right']))
                else:
                    if self.unidirectional_strict:
                        self.logger.debug(u'Deleting new item at right because of unidirectional strict: %s' % (right))
                        right.delete(None)
                    else:
                        self.logger.debug(u'Ignoring new item at right because auf unidirectional merge: %s' % (right))

            self._sync['map'] = self._new_sync

        return self._sync

def parse_config(relation, config, _logger):

    from ConfigParser import ConfigParser

    from oxsync import OxTaskSync
    from ensync import EnClientSync
    from tdsync import ToodledoSync

    logger = LogAdapter(_logger, {'package': 'config'})

    class_map = {

        'OxTaskSync': OxTaskSync,
        'EnClientSync': EnClientSync,
        'ToodledoSync': ToodledoSync
    }

    relation_section = 'relation' + '_' + relation
    if config.has_section(relation_section):

        rel = {}
        for key in config.options(relation_section):
            rel[key] = config.get(relation_section, key)

        if rel.get('map'):
            rel['map'] = os.path.expanduser(rel.get('map'))
        else:
            logging.critical('Configuration error: missing map file path for %s' % (relation))
            exit(1)

        left = config.get(relation_section, 'left')
        if left:
            engine_section_left = 'engine' + '_' + left
        else:
            logging.critical('Configuraion error: missing left engine refernce')
            exit(1)

        left = None
        if config.has_section(engine_section_left):
            left = {}
            for key in config.options(engine_section_left):
                left[key] = config.get(engine_section_left, key)
        else:
            logging.critical('Configuration error: missing section [%s]' % (engine_section_left))
            exit(1)

        right = config.get(relation_section, 'right')
        if right:
            engine_section_right = 'engine' + '_' + right
        else:
            logging.critical('Configuraion error: missing right engine refernce')
            exit(1)

        right = None
        if config.has_section(engine_section_right):
            right = {}
            for key in config.options(engine_section_right):
                right[key] = config.get(engine_section_right, key)
        else:
            logging.critical('Configuration error: missing section [%s]' % (engine_section_right))
            exit(1)

        for engine in [left, right]:
            secrets = engine['secrets']
            path = os.path.expanduser(secrets)
            if os.path.isfile(path):
                secret = ConfigParser()
                secret.read(path)
                if secret.has_section('secrets'):
                    engine['secrets'] = {'key': path}
                    for key in secret.options('secrets'):
                        engine['secrets'][key] = secret.get('secrets', key)
                else:
                    logger.critical('Configuration error: missing [secrets] in %s' % (path))
                    exit(1)
            else:
                if config.has_option('options', 'secrets'):
                    secrets = config.get('options', 'secrets')
                    path = os.path.expanduser(secrets)
                    if os.path.isfile(path):
                        secret = ConfigParser()
                        secret.read(path)
                        section = engine['secrets'][1:-1]
                        if secret.has_section(section):
                            engine['secrets'] = {'key': section}
                            for key in secret.options(section):
                                engine['secrets'][key] = secret.get(section, key)
                        else:
                            logger.critical('Configuration error: missing [%s] in %s' % (section, path))
                            exit(1)
                    else:
                        logger.critical('Configuration error: missing secret file %s' % (path))
                        exit(1)
                else:
                    logger.critical('Configuration error: missing secrets in [options]')
                    exit(1)

    else:
        logging.critical('Configuration error: missing section [%s]' % (relation_section))
        exit(1)

    for options in [left, right]:
        if options.get('class'):
            cn = options['class']
            if class_map.get(cn):
                options['class'] = class_map[cn]
            else:
                logger.critical('Configuration error: unknown sync engine [%s]' % (cn))
                exit(1)
        else:
            logger.critical('configuration error: missing class tag')
            exit(1)

    return Options(left), Options(right), Options(rel)

def lock(relation, opts, _logger):

    logger = LogAdapter(_logger, {'package': 'lock'})
    map_file = os.path.expanduser(opts['map'])
    lck_file = os.path.splitext(map_file)[0] + '.lck'
    if os.path.isfile(lck_file):
        logger.error('Relation [%s] locked. Remove %s to unlock synchronization' % (relation, lck_file))
        return False
    if os.path.isfile(map_file):
        with codecs.open(map_file, 'r', encoding='utf-8') as fp:
            content = fp.read()
        logger.debug(u'Locking relation [%s]' % (relation))
        with codecs.open(lck_file, 'w', encoding='utf-8') as fp:
            fp.write(content)
    else:
        open(lck_file, 'a').close()
    return True

def rollback(relation, opts, _logger):

    logger = LogAdapter(_logger, {'package': 'rollback'})
    map_file = os.path.expanduser(opts['map'])
    lck_file = os.path.splitext(map_file)[0] + '.lck'
    if os.path.isfile(lck_file):
        with codecs.open(lck_file, 'r', encoding='utf-8') as fp:
            content = fp.read()
        logger.debug(u'Rollback relation [%s]' % (relation))
        with codecs.open(map_file, 'w', encoding='utf-8') as fp:
            fp.write(content)
            os.remove(lck_file)
            return True

    return False

def unlock(relation, opts, _logger):

    logger = LogAdapter(_logger, {'package': 'unlock'})
    map_file = os.path.expanduser(opts['map'])
    lck_file = os.path.splitext(map_file)[0] + '.lck'
    if os.path.isfile(lck_file):
        logger.debug(u'Unlocking relation [%s]' % (relation))
        os.remove(lck_file)
        return True
    else:
        logger.warning('Lockfile %s for relation [%s] not found!' % (lck_file, relation))
        return False

def check_sync_map(relation, left, right, relation_opts, logger):

    remove = []

    logger.debug(u'Checking sync map ...')

    # check for incomplete sid entries without left or right entry
    for sid in relation_opts['sync']['map']:
        item = relation_opts['sync']['map'][sid]
        OK = True
        if item.get('left') is None:
            logger.debug(u'Missing left entry for [%s]: %s' % (sid, item.get('key')))
            OK = False
        if item.get('right') is None:
            logger.debug(u'Missing right entry for [%s]: %s' % (sid, item.get('key')))
            OK = False
        if not OK:
            remove.append(sid)

    # check for deleted entries in sync map
    for sync in [left, right]:
        for sid in sync._deleted:
            if sid in relation_opts['sync']['map']:
                item = relation_opts['sync']['map'][sid]
                logger.debug(u'Removing deleted entry [%s]: %s' % (sid, item.get('key')))
                remove.append(sid)

    if remove:
        logger.error(u'Repairing sync map ...')
        for sid in set(remove):
            if sid in relation_opts['sync']['map']:
                logger.error(u'Removing [%s]: %s' % (sid, relation_opts['sync']['map'][sid].get('key')))
                del(relation_opts['sync']['map'][sid])

    relation_opts['sync']['relation'] = relation
    relation_opts['sync']['left'] = left.options.signature
    relation_opts['sync']['right'] = right.options.signature
    relation_opts['sync']['time'] = strflocal()

    with codecs.open(relation_opts['map'], 'w', encoding='utf-8') as fp:
        json.dump(relation_opts['sync'], fp, indent=4, ensure_ascii=False, encoding='utf-8')

    return len(relation_opts['sync']['map']), len(remove)

def main():

    from argparse import ArgumentParser
    from pysync import __version__, __author__
    from pysync import SyncError, SyncSessionError, SyncInitError

    options = {
        'secrets': '~/.pysync.secrets',
        'loglevel_requests': 'ERROR',
        'loglevel': 'INFO'
    }

# region Command line arguments

    parser = ArgumentParser(description='PySnc Engine Rev. %s (c) %s' % (__version__, __author__))
    parser.add_argument('-c', '--config', type=str, help='use alternate configuration file(s)')
    parser.add_argument('--relations', type=str, help='list of pysync relations to process')
    parser.add_argument('--rebuild', action='store_true', help='rebuild map file')
    parser.add_argument('--reset', type=str, help='delete entries and recreate from left/right')
    parser.add_argument('--update', type=str, help='force update on left/right side')

    parser.add_argument('-l', '--loglevel', type=str,
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='debug log level')

    args = parser.parse_args()
    opts = Options(options, args, '[config]', prefix='PYSYNC')
    config = opts.config_parser

    if config is None:
        LogAdapter(get_logger(), {'package': 'main'}).critical("Missing configuration file!")
        exit(1)

    logger = LogAdapter(opts.logger, {'package': 'main'})
# endregion

# region Basic configuration and logger settings

    # set log level of requests module
    logging.getLogger('requests').setLevel(log_level(opts.loglevel_requests))
    logging.getLogger('urllib3').setLevel(log_level(opts.loglevel_requests))

    logger.debug(u'Parsing configuration file %s' % (opts.config_file))

    if opts.relations:
        relations = list(opts.relations.split(','))
    else:
        logger.critical('Missing relations!')
        exit(1)

# endregion

    for relation in relations:

        try:
            left_opts, right_opts, relation_opts = parse_config(relation, config, opts.logger)
        except Exception as e:
            logger.exception('Error parsing configuration options. Skipping sync for [%s]' % (relation))
            continue

        if lock(relation, relation_opts, opts.logger):

            # initialise web service sessions via @staticmethod session()
            # and initialize sync engine classes
            try:
                label = left_opts.get('label')
                left_session = left_opts['class'].session(left_opts, opts.logger)
                label = right_opts.get('label')
                right_session = right_opts['class'].session(right_opts, opts.logger)
            except Exception as e:
                # TODO: check exception type, unlock() only in case of an temp. network error etc.
                logger.exception('Session initialization for [%s] failed! Skipping sync for [%s]' % (label, relation))
                # unlock(relation, relation_opts, opts.logger)
                continue

            # initialize sync map
            relation_opts['sync'] = {'map': None}

            if os.path.isfile(relation_opts['map']):

                ####################
                # incremental sync #
                ####################

                with codecs.open(relation_opts['map'], 'r', encoding='utf-8') as fp:
                    relation_opts['sync'] = json.load(fp)

                logger.info(u'%s: starting incremental sync for %d items' % (relation, len(relation_opts['sync'].get('map'))))

                # merge signature from map file
                left_opts.update({'signature': relation_opts['sync']['left']})
                right_opts.update({'signature': relation_opts['sync']['right']})

                try:
                    left = left_opts['class'](left_session, left_opts, logger=opts.logger)
                    right = right_opts['class'](right_session, right_opts, logger=opts.logger)
                except Exception as e:
                    # TODO: check exception type, unlock() only in case of an temp. network error etc.
                    logger.exception('Engine initialization for [%s] failed! Skipping sync for [%s]' % (label, relation))
                    # unlock(relation, relation_opts, opts.logger)
                    continue

                if opts['update']:
                    try:
                        relation_opts['sync'] = PySync(left, right, relation_opts, opts.logger).update(opts['update'])
                    except Exception as e:
                        logger.exception('Unexpected error when processing update option! Skipping sync for [%s]' % relation)
                        unlock(relation, relation_opts, opts.logger)
                        continue

                if opts.reset:
                    try:
                        relation_opts['sync'] = PySync(left, right, relation_opts, opts.logger).reset(opts.reset)
                    except Exception as e:
                        logger.exception('Unexpected error when processing reset option!')
                        check_sync_map(relation, left, right, relation_opts, logger)
                        continue

                if opts.rebuild:
                    relation_opts['sync'] = {'map': None}

            else:

                ################
                # initial sync #
                ################

                logger.info(u'%s: Starting initial sync' % (relation))

                for opt in ['update', 'reset', 'rebuild']:
                    if opts.get(opt):
                        logger.warning('Ignoring option [%s] for initial sync' % (opt))

                try:
                    left = left_opts['class'](left_session, left_opts, logger=opts.logger)
                    right = right_opts['class'](right_session, right_opts, logger=opts.logger)
                except Exception as e:
                    # TODO: check exception type, unlock() only in case of an temp. network error etc.
                    logger.exception('Engine initialization for [%s] failed! Skipping sync for [%s]' % (label, relation))
                    # unlock(relation, relation_opts, opts.logger)
                    continue

            try:
                relation_opts['sync'] = PySync(left, right, relation_opts, opts.logger).process()
            except Exception as e:
                logger.exception('Unexpected error when processing sync map!')
                check_sync_map(relation, left, right, relation_opts, logger)
                continue

            # check/modify sync map by backend engine
            relation_opts = left.commit_sync('left', relation_opts, logger)
            relation_opts = right.commit_sync('right', relation_opts, logger)
            count, errors = check_sync_map(relation, left, right, relation_opts, logger)
            unlock(relation, relation_opts, logger)
            logger.info(u'%s: finished sync for %d items with %d errors' % (relation, count, errors))


            left_opts['class'].end_session(logger)
            right_opts['class'].end_session(logger)

# region __Main__

if __name__ == '__main__':

    main()
    exit(0)

# endregion
