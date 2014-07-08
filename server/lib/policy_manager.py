#!/usr/bin/python
#-*- coding: UTF-8 -*-
#author: fox
#desc: 分析策略的管理框架
#date: 2014/06/27

import sys, re, json, os
import datetime, time
import redis
sys.path.append('../../../../server')
from pyutil.util import Util, safestr
from pyutil.sqlutil import SqlUtil, SqlConn
from policy_worker import PolicyWorker
from stock_util import get_stock_list, get_past_openday, get_past_data

class PolicyManager(object):
    instance_map = {}

    def __init__(self, config_info):
        self.config_info = config_info
        self.db_config = config_info['DB']
        self.redis_config = config_info['REDIS']
        self.day = int("{0:%Y%m%d}".format(datetime.date.today()))

    def core(self):
        policy_content = open(self.config_info['POLICY']['config']).read()
        print policy_content
        worker_config = json.loads(policy_content)
        print worker_config

        datamap = self.make_datamap()
        queue_policy_map = dict()
        queue_list = []

        for policy_name, policy_config in worker_config.items():
            queue_list.append(policy_config['queue'])
            queue_policy_map[policy_config['queue']] = policy_name

            instance_list = []
            for i in range(policy_config['thread_count']):
                policy_instance = PolicyWorker(policy_name, i, policy_config, self.config_info, datamap)
                policy_instance.start()
                print "name=" + policy_name + " index=" + str(i) + " id=" + str(policy_instance.ident)
                instance_list.append(policy_instance)
            self.instance_map[policy_name] = instance_list

        # TODO: 考虑在主线程中取出队列item, 然后稳定分发到对应instance的queue里
        conn = redis.StrictRedis(self.redis_config['host'], self.redis_config['port'])
        while True:
            try:
                data = conn.blpop(queue_list, 1)
                if data is None:
                    continue

                key = data[0]
                if key not in queue_policy_map:
                    conn.rpush(key, data[1])
                    continue

                name = queue_policy_map[key]
                item = json.loads(data[1])
                #print item

                sid = item['sid']
                index = sid % len(self.instance_map[name])
                self.instance_map[name][index].enqueue(item)

                print "op=dispatch_item key=" + str(key) + " name=" + name + " sid=" + str(sid) + " index=" + str(index)
            except (KeyboardInterrupt, SystemExit): 
                print "catch keybord interrupt"
                self.terminate()
                break

    def terminate(self):
        for policy_name, instance_list in self.instance_map.items():
            for instance in instance_list:
                instance.stop()
                instance.join()

        self.instance_map.clear()
        
    # 构造公共数据
    def make_datamap(self):
        datamap = dict()
        datamap['stock_list'] = stock_list = get_stock_list(self.db_config, 1)

        scode2id_map = dict()
        id2scode_map = dict()
        for sid, stock_info in stock_list.items():
            scode = stock_info['ecode'].lower() + stock_info['code']
            scode2id_map[stock_info['code']] = sid
            id2scode_map[sid] = scode

        datamap['scode2id'] = scode2id_map
        datamap['id2scode'] = id2scode_map
        datamap['past_data'] = get_past_data(self.db_config, self.redis_config, self.day, 5)
        print len(datamap['past_data'])

        return datamap

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: " + sys.argv[0] + " <conf>"
        sys.exit(1)

    config_info = Util.load_config(sys.argv[1])
    config_info['DB']['port'] = int(config_info['DB']['port'])
    config_info['REDIS']['port'] = int(config_info['REDIS']['port'])

    manager = PolicyManager(config_info)
    manager.core()