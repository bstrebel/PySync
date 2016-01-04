#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, sys, json, re, uuid, logging, codecs

from pyutils import LogAdapter
from pysync import *

from oxapi import OxHttpAPI
from oxsync import OxTaskSync

from enapi import EnClient
from ensync import EnClientSync

# logging configuration
sh = logging.StreamHandler()
sf = logging.Formatter('%(levelname)-7s %(module)s %(message)s')
sh.setFormatter(sf)

fh = logging.FileHandler('sync.log', encoding='utf-8')
ff = logging.Formatter('%(asctime)s %(levelname)-7s %(module)s %(message)s')
fh.setFormatter(ff)

# logging via LoggerAdapter
root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(sh)
root.addHandler(fh)

logger = LogAdapter(root, {'package': 'root'})

# set log level of requests module
requests = logging.getLogger('requests')
requests.setLevel(logging.ERROR)

#logger.setLevel(logging.DEBUG)
logger.debug("Logging initialized ...")

from secrets import en_dev_token, ox_server, ox_user, ox_password

ox = OxHttpAPI.get_session(server=ox_server, user=ox_user, password=ox_password, logger=root)
en = EnClient.get_client(token=en_dev_token, logger=root)
#en = {'token': os.environ.get('EVERNOTE_TOKEN'), 'sandbox': False}

right = {'class': OxTaskSync, 'session': ox, 'options': { 'folder': 'OxSync', 'key': 'title'}}
left = { 'class': EnClientSync, 'session': en, 'options': {'notebook': 'OxSync', 'key': 'title'}}

sync_file = 'sync_map.json'
sync_map = None

if os.path.isfile('sync_map.json'):
    with codecs.open(sync_file, 'r', encoding='utf-8') as fp:
        # TODO: extract map from sync metadata
        sync_map = json.load(fp)

sync = PySync(left, right, sync_map, logger)
sync_map = sync.process()
ox.logout()

# TODO: add sync metadata
if sync_map:
    with codecs.open(sync_file, 'w', encoding='utf-8') as fp:
        json.dump(sync_map, fp, indent=4, ensure_ascii=False, encoding='utf-8')
