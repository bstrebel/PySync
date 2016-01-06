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

        self.logger.debug('Initalizing PySync with %s and %s ...' % (left, right))

        self._opts = opts
        self._left = left
        self._right = right
        self._sync = opts['sync']
        self._new_sync = None

    @property
    def logger(self): return self._adapter

    @property
    def left(self): return self._left

    @property
    def right(self): return self._right

    @property
    def sync(self): return self._sync['map']

    @sync.setter
    def sync(self, value): self._sync['map'] = value

    def _add_item(self, sid, lr, id, tm, key=None):

        from pysync import Sync

        if self._new_sync is None:
            sync = self.sync
        else:
            sync = self._new_sync
        if sid not in sync:
            sync[sid] = {}

        if key is not None:
            if isinstance(key, str):
                sync[sid]['key'] = key.decode('utf-8')
            else:
                sync[sid]['key'] = key

            # sync[sid]['key'] = key.encode('utf-8')

        sync[sid][lr] = {'id': id, 'time': tm}
        self.logger.debug('%s: %-5s %s %s %s' % (sid, lr, strflocal(tm), id, key))

    def process(self):

        left = self._left
        right = self._right

        left_map = left.sync_map()
        right_map = right.sync_map()

        if self.sync is None:
            """
            Initial sync: create sync_map
            """
            found = {}
            self.sync = {}
            self._new_sync = None

            self.logger.info("Initalizing sync map ...")

            for key in left:

                self.logger.info('Checking %s' % (self.left))
                sid = str(uuid.uuid1())
                self._add_item(sid, 'left', key, left[key]['time'], left[key]['key'])

                # find items by key
                guid = right.find_key(left[key]['key'])
                if guid:
                    found[guid] = True
                    self.logger.info('Found matching item [%s] at %s' % (left[key]['key'], self.right))
                    self._add_item(sid, 'right', guid, right[guid]['time'], right[guid]['key'])
                else:
                    # create missing item on right side
                    self.logger.info('Create missing item [%s] at %s' % (left[key]['key'], self.right))
                    new_id, new_time, title = right.create(left)
                    self._add_item(sid, 'right', new_id, new_time, title)

            for key in right:

                self.logger.info('Checking %s' % (self.left))

                if key not in found:
                    # new key on the right side
                    sid = str(uuid.uuid1())
                    self.logger.info('Create missing item [%s] at %s' % (right[key]['key'], self.left))
                    self._add_item(sid, 'right', key, right[key]['time'], right[key]['key'])
                    new_id, new_time, title = left.create(right)
                    self._add_item(sid, 'left', new_id, new_time, title)

            # return self.sync

        else:
            """
            Update existing sync map
            """
            self._new_sync = {}

            self.logger.info('Processing sync map ...')

            for sid in self.sync:

                lid = self.sync[sid]['left']['id']
                rid = self.sync[sid]['right']['id']

                self.logger.info('%s: [%s]' % (sid, self.sync[sid]['key']) )
                self.logger.info('%s: %s %s' % (sid, self._left, self.sync[sid]['left']))
                self.logger.info('%s: %s %s' % (sid, self._right, self.sync[sid]['right']))

                if lid in left:
                    # left item exitst
                    litem = left[lid]
                else:
                    # item deleted on left side
                    # => delete right item
                    if rid in right:
                        self.logger.info('%s: Item deleted at %s' % (sid, self.left))
                        right.delete()
                    continue

                if rid in right:
                    # right item exitst
                    ritem = right[rid]
                else:
                    # item deleted on right side
                    # => delete left item
                    if lid in left:
                        self.logger.info('%s: Item deleted at %s' % (sid, self.right))
                        left.delete()
                    continue

                # both items exists: compare and update sync map
                ltime =  self.sync[sid]['left']['time']
                rtime =  self.sync[sid]['right']['time']

                if ltime < litem['time']:
                    self.logger.info('%s: Item changed at left %s' % (sid, self.left))
                    if rtime < ritem['time']:
                        self.logger.info('%s: Item also changed at right %s' % (sid, self.right))
                        if litem['time'] < ritem['time']:
                            self.logger.info('%s: Item newer at right %s ' % (sid, self.right))
                            self.logger.info('%s: Updating left item at %s' % (sid, self.left))
                            litem['time'] = left.update(right)
                        else:
                            self.logger.info('%s: Item newer at left %s ' % (sid, self.left))
                            self.logger.info('%s: Updating right item at %s' % (sid, self.right))
                            ritem['time'] = right.update(left)
                    else:
                        self.logger.info('%s: Updating right item at %s' % (sid, self.right))
                        ritem['time'] = right.update(left)
                else:
                    if rtime < ritem['time']:
                        self.logger.info('%s: Item changed at right %s' % (sid, self.right))
                        self.logger.info('%s: Updating left item at %s' % (sid, self.left))
                        litem['time'] = left.update(right)

                self._add_item(sid, 'left', lid, litem['time'], litem['key'])
                self._add_item(sid, 'right', rid, ritem['time'], ritem['key'])

                del left[lid]
                del right[rid]

            self.logger.info('Checking for new items at %s' % (self.left))
            for key in left:
                # new items on the left side
                new_id, new_time, title = right.create(left)

                sid = str(uuid.uuid1())
                self._add_item(sid, 'left', key, left[key]['time'], left[key]['key'])
                self._add_item(sid, 'right', new_id, new_time, title)

                self.logger.info('%s: [%s]' % (sid, self._new_sync[sid]['key']) )
                self.logger.info('%s: %s %s' % (sid, self.left, self._new_sync[sid]['left']))
                self.logger.info('%s: %s %s' % (sid, self.right, self._new_sync[sid]['right']))

            self.logger.info('Checking for new items at %s' % (self.right))
            for key in right:
                # new items on the left side
                new_id, new_time, title = left.create(right)

                sid = str(uuid.uuid1())
                self._add_item(sid, 'right', key, right[key]['time'], right[key]['key'])
                self._add_item(sid, 'left', new_id, new_time, title)

                self.logger.info('%s: [%s]' % (sid, self._new_sync[sid]['key']) )
                self.logger.info('%s: %s %s' % (sid, self.left, self._new_sync[sid]['left']))
                self.logger.info('%s: %s %s' % (sid, self.right, self._new_sync[sid]['right']))

            self._sync['map'] = self._new_sync

        return self._sync

def parse_config(relation, config, _logger):

    from ConfigParser import ConfigParser

    from oxsync import OxTaskSync
    from ensync import EnClientSync

    logger = LogAdapter(_logger, {'package': 'config'})

    class_map = {

        'OxTaskSync': OxTaskSync,
        'EnClientSync': EnClientSync
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

    return left, right, rel

def main():

    from ConfigParser import ConfigParser
    from argparse import ArgumentParser

    options = {
        'secrets': '~/.pysync.secrets',
        'loglevel_requests': 'ERROR',
        'loglevel': 'INFO'
    }

# region Command line arguments

    parser = ArgumentParser(description='PySnc Engine Rev. 0.1 (c) Bernd Strebel')
    parser.add_argument('-c', '--config', type=str, help='use alternate configuration file')
    parser.add_argument('-r', '--relations', type=str, help='list of pysync relations to process')

    parser.add_argument('-l', '--loglevel', type=str,
                        choices=['DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'CRITICAL',
                                 'debug', 'info', 'warn', 'warning', 'error', 'critical'],
                        help='debug log level')

    args = parser.parse_args()
    opts = Options('PYSYNC', args, options)
    config = opts.config_parser

    if config is None:
        LogAdapter(get_logger(), {'package': 'main'}).critical("Missing configuration file!")
        exit(1)

    logger = LogAdapter(opts.logger, {'package': 'main'})

# endregion

# region Basic configuration and logger settings

    # set log level of requests module
    requests = logging.getLogger('requests')
    requests.setLevel(log_level(opts.loglevel_requests))

    logger.info('Parsing configuration file %s' % (opts.config_file))

    if opts.relations:
        relations = list(opts.relations.split(','))
    else:
        logger.critical('Missing relations!')
        exit(1)

# endregion

    sessions = {}

    for relation in relations:

        left_opts, right_opts, relation_opts = parse_config(relation, config, opts.logger)

        # initialise web service sessions via @staticmethod session()

        left_session = left_opts['class'].session(left_opts, opts.logger)
        if not left_session:
            logger.critical("Session initialization for %s failed!" % (left_opts['class']))
            exit(3)

        right_session = right_opts['class'].session(right_opts, opts.logger)
        if not right_session:
            logger.critical("Session initialization for %s failed!" % (right_opts['class']))
            exit(3)

        # TODO: store sessions for shared usage

        # initialize sync engine classes
        left = left_opts['class'](left_session, left_opts, logger=opts.logger)
        right = right_opts['class'](right_session, right_opts, logger=opts.logger)

        # initialize sync map
        relation_opts['sync'] = {'map': None}
        if os.path.isfile(relation_opts['map']):
            with codecs.open(relation_opts['map'], 'r', encoding='utf-8') as fp:
                relation_opts['sync'] = json.load(fp)

        relation_opts['sync'] = PySync(left, right, relation_opts, opts.logger).process()

        left.end_session()
        right.end_session()

        if relation_opts['sync']:
            relation_opts['sync']['relation'] = relation
            relation_opts['sync']['left'] = '%s' % (left)
            relation_opts['sync']['right'] = '%s' % (right)
            relation_opts['sync']['time'] = strflocal()
            with codecs.open(relation_opts['map'], 'w', encoding='utf-8') as fp:
                json.dump(relation_opts['sync'], fp, indent=4, ensure_ascii=False, encoding='utf-8')

# region __Main__

if __name__ == '__main__':

    main()
    exit(0)

# endregion
