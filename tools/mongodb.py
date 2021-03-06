#!/usr/bin/python
# -*- coding: utf-8 -*-
################################################################################

import functools
import logging
import math
import pymongo
import sys
from bson.son import SON
from itertools import islice
from os.path import basename

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def cache(db, coll, doc):
    '''save doc to db.coll if it doesn't exist, update if it does'''
    #doc.pop('_id', None)
    logger.debug('mongodb.cache: %s.%s, %s' % (db, coll, doc))
    if not db[coll].find_one(doc):
        logger.info('mongodb.cache: CACHED! %s.%s, %s' % (db, coll, doc))
        db[coll].insert(doc)

def i2query(i):
    '''returns a tuple of argument values labeled (arg1,<value>),
    (arg2,<value>), ..., (argn,<value>) '''
    return zip(['arg%d'%n for n in xrange(1,len(i)+1)], i)

def make_query(i=None, p=None):
    '''generates a mongodb query from i and p, placing p before i to match 
    index order'''
    q = SON()
    #q = {}
    if p:
        q['rel'] = p
    if i:
        for k,v in i2query(i):
            q[k] = v
    #print >>sys.stderr, 'make_query:', i, p, q
    return q

def memoize(db, collection):
    connection = pymongo.Connection('localhost', 1979)
    db_ = connection[db]
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                db_[collection].ensure_index(
                    [(k, pymongo.ASCENDING) for k in kwargs.keys()]
                    )
                result = db_[collection].find_one(kwargs)
                if result:
                    #print >>sys.stderr, 'MONGODB: HIT in %s.%s: %s' % \
                    #    (db, collection, result)
                    return result['value']
                else:
                    #print >>sys.stderr, 'MONGODB: MISS in %s.%s: %s' % \
                    #    (db, collection, kwargs)
                    value = func(*args, **kwargs) 
                    if value:
                        result = kwargs
                        result['value'] = value
                        #print >>sys.stderr, 'MONGODB: CACHING in %s.%s: %s:' % \
                        #    (db, collection, result)
                        db_[collection].insert(result)
                        return value
            except Exception as err:
                #print >>sys.stderr, 'MONGODB MEMOIZATION ERROR!', err, args, kwargs
                #raise err
                f = func(*args, **kwargs)
                #print >>sys.stderr, '%s(%s, %s): %s' % (func, args, kwargs, f)
                return f
        return wrapper
    return decorator

def fullname(db_):
    '''return host, port, database, and collection name of db'''
    host_ = db_.database.connection.host
    port_ = db_.database.connection.port
    fullname = db_.full_name
    return '%s:%s/%s' % (host_, port_, fullname)

def file2collection(file):
    '''sanitize a filename to use as a collection'''
    return basename(file).split('.')[0].split('-')[0]

def staggered_retrieval(iterator, maximum, batch):
    '''returns items in iterator by iterating over slices of size N'''
    slices = int(math.ceil(float(maximum) / batch))
    print >>sys.stdout, 'slices:', slices
    return (x
            for x in islice(iterator, batch)
            for y in xrange(slices))

def fast_find(db, c, query={}, batch=1000, **kwargs):
    with db[c].find(spec=query, batch=batch, timeout=False, **kwargs) as xs:
        # print >>sys.stderr, '%s.find(spec=%s,batch=%s,kwargs=%s).explain(): %s' % (db[c], query, batch, kwargs, xs.explain())
        slices = int(math.ceil(float(xs.count()) / batch))
        for y in xrange(slices):
            for x in islice(xs, batch):
                yield x
