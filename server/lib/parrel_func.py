#!/usr/bin/python
#-*- coding: UTF-8 -*-
#author: fox
#desc: 抓取数据的实际逻辑
#date: 2014-06-24

import os, sys, random, json, logging, math
import datetime, urllib2
from multiprocessing.dummy import Pool as ThreadPool
#sys.path.append('../../../server')
sys.path.append('../../../../server')
from pyutil.util import Util, safestr, format_log
from stock_util import get_predict_volume
import redis

# 并行处理的基类
class ParrelFunc(object):
    item_list = []

    def __init__(self, day, config_info, datamap, worker_config):
        self.day = day
        self.config_info = config_info
        self.datamap = datamap
        self.worker_config = worker_config

        self.item_per_thread = worker_config['item_per_thread']
        # 连接REDIS
        self.conn = redis.StrictRedis(self.config_info['REDIS']['host'], int(self.config_info['REDIS']['port']))
        self.logger = logging.getLogger("fetch")

    def run(self):
        self.item_list = self.get_data()
        count = max(int(math.ceil(len(self.item_list) / self.item_per_thread)), 1)
        self.logger.debug("desc=parrel_itemlist item_count=%d thread_count=%d item_list=%s", len(self.item_list), count, '|'.join([str(v) for v in self.item_list]))

        if count > 1:
            pool = ThreadPool(count)
            pool.map(self.core, self.item_list)
            pool.close()
            pool.join()
        else:
            map(self.core, self.item_list)

    # 获取输入的数据列表
    def get_data(self):
        return []

    # 单个item的处理函数
    def core(self, item):
        return

    # 启动/恢复运行时加载中间状态
    def load(self):
        pass

    # 中间暂停/结束运行时保存中间状态
    def save(self):
        pass

# 并行抓取当日总览数据
class ParrelDaily(ParrelFunc):

    def run(self):
        super(ParrelDaily, self).run()

    def get_data(self):
        item_list = []
        scode_list = self.datamap['id2scode'].values()
        stock_count = len(scode_list)

        if "dataset" in self.worker_config:
            scode_dataset = []
            for sid in self.worker_config["dataset"]:
                if sid in self.datamap['id2scode']:
                    scode_dataset.append(self.datamap['id2scode'][sid])
            item_list.append(",".join(scode_dataset))
        else:
            offset = 0
            percount = 50
            while offset < stock_count:
                item_list.append(",".join(scode_list[offset : min(offset + percount, stock_count)]))
                offset += percount

        return item_list

    # 获取股票当前价格及成交量等信息
    def core(self, item):
        scode = item
        url = "http://qt.gtimg.cn/r=" + str(random.random()) + "q=" + scode
        #print url

        try:
            response = urllib2.urlopen(url, timeout=1)
            content = response.read()
        except urllib2.HTTPError as e:
            self.logger.warning("err=get_stock_daily scode=%s code=%s", scode, str(e.code))
            return 
        except urllib2.URLError as e:
            self.logger.warning("err=get_stock_daily scode=%s reason=%s", scode, str(e.reason))
            return

        if content:
            content = safestr(content.decode('gbk'))
            #self.logger.info("desc=daily_content content=%s", content)
            lines = content.strip("\r\n").split(";")

            for line in lines:
                if 0 == len(line):
                    continue

                daily_item = self.parse_stock_daily(line)
                if daily_item is None:
                    continue

                # 追加到redis队列中
                if self.conn:
                    self.conn.rpush("daily-queue", json.dumps(daily_item))
                self.logger.info(format_log("fetch_daily", daily_item))
                #print format_log("fetch_daily", daily_item)

    # 解析单个股票行情数据
    def parse_stock_daily(self, line):
        parts = line.split("=")
        #print line, parts
        content = parts[1].strip('"')
        #print content

        fields = content.split("~")
        #print fields
        if len(fields) < 44:
            line_str = safestr(line)
            self.logger.error(format_log("daily_lack_fields", {'line': line_str, 'content': content}))
            return None

        # 当日停牌则不能存入
        open_price = float(fields[5])
        close_price = float(fields[3])
        if open_price == 0.0 or close_price == 0.0:
            return None

        item = dict()

        try:
            item['name'] = safestr(fields[1])
            item['code'] = stock_code = fields[2]
            item['sid'] = int(self.datamap['code2id'][stock_code])
            item['day'] = self.day
            item['last_close_price'] = float(fields[4])
            item['open_price'] = open_price
            item['high_price'] = float(fields[33])
            item['low_price'] = float(fields[34])
            item['close_price'] = close_price
            # 当前时刻, 格式为HHMMSS
            item['time'] = fields[30][8:]
            item['vary_price'] = float(fields[31])
            item['vary_portion'] = float(fields[32])
            # 成交量转化为手
            item['volume'] = int(fields[36])
            item['predict_volume'] = get_predict_volume(item['volume'], item['time'])
            # 成交额转化为万元
            item['amount'] = int(fields[37])
            item['exchange_portion'] = fields[38]
            item['pe'] = fields[39]
            item['swing'] = fields[43]
            item['out_capital'] = fields[44]
        except IndexError:
            self.logger.error(format_log("parse_daily", {'content': content}))
            return None

        return item

# 并行抓取股票盘中每分钟的实时价格和成交量
class ParrelRealtime(ParrelFunc):
    # 存储股票上次拉取分时成交量的时间 sid -> time
    time_map = {}

    def load(self):
        key = "rt-overview-" + str(self.day)
        value = self.conn.get(key)
        if value: 
            self.time_map = json.loads(value)

    def save(self):
        if len(self.time_map) > 0:
            key = "rt-overview-" + str(self.day)
            self.conn.set(key, json.dumps(self.time_map), 86400)

    def get_data(self):
        item_list = []
        sid_list = self.datamap['pool_list']

        if "dataset" in self.worker_config:
            sid_list = self.worker_config['dataset']
        for sid in sid_list:
            if sid in self.datamap['id2scode']:
                item_list.append((sid, self.datamap['id2scode'][sid]))
        #for sid, scode in self.datamap['id2scode'].items():
        #    item_list.append((sid, scode))
        return item_list

    def core(self, item):
        sid = item[0]
        scode = item[1]
        url = "http://data.gtimg.cn/flashdata/hushen/minute/" + scode + ".js?maxage=10&" + str(random.random())
        #print scode, url

        try:
            response = urllib2.urlopen(url, timeout=1)
            content = response.read()
        except urllib2.HTTPError as e:
            self.logger.warning("err=get_stock_realtime sid=%d scode=%s code=%s", sid, scode, str(e.code))
            return None
        except urllib2.URLError as e:
            self.logger.warning("err=get_stock_realtime sid=%d scode=%s reason=%s", sid, scode, str(e.reason))
            return None

        content = content.strip(' ;"\n').replace("\\n\\", "")
        lines = content.split("\n")
        #print lines

        date_info = lines[1].split(":")
        data_day = int("20" + date_info[1])
        hq_item = list()
        last_time = 0

        if sid in self.time_map:
            last_time = self.time_map[sid]

        new_time = last_time
        for line in lines[2:]:
            fields = line.split(" ")
            # 直接用小时+分组成的时间, 格式为HHMM
            time = int(fields[0])

            if time <= last_time:
                continue

            data_item = dict()
            data_item['time'] = time
            data_item['price'] = float(fields[1])
            data_item['volume'] = int(fields[2])

            if data_item['volume'] <= 0:
                continue

            hq_item.append(data_item)
            new_time = max(time, new_time)

        # 表示当天所有的成交量都为0, 当天停牌
        if len(hq_item) == 0:
            return

        # 更新last_time
        self.time_map[sid] = new_time

        self.conn.rpush("realtime-queue", json.dumps({'sid': sid, 'day': data_day, 'items': hq_item}))
        #print format_log("fetch_realtime", {'sid': sid, 'scode': scode, 'time': hq_item[len(hq_item) - 1]['time'], 'price': hq_item[len(hq_item) - 1]['price']})
        self.logger.info(format_log("fetch_realtime", {'sid': sid, 'scode': scode, 'time': hq_item[len(hq_item) - 1]['time'], 'price': hq_item[len(hq_item) - 1]['price']}))

 # 并行抓取股票盘成交明细
class ParrelTransaction(ParrelFunc):
    # 存储股票上次拉取成交明细的位置(sid, seq)
    pos_map = dict()
    ignore_set = set()

    def load(self):
        key = "ts-overview-" + str(self.day)
        value = self.conn.get(key)
        if value: 
            self.pos_map = json.loads(value)

    def save(self):
        if len(self.pos_map) > 0:
            key = "ts-overview-" + str(self.day)
            self.conn.set(key, json.dumps(self.pos_map), 86400)

    def get_data(self):
        item_list = []
        sid_list = []

        #print self.datamap['pool_list']
        if "dataset" in self.worker_config:
            sid_list = self.worker_config['dataset']
        else:
            ts_set = self.conn.smembers("tsset-" + str(self.day))
            if ts_set:
                sid_list = [ int(sid) for sid in list(ts_set)]
            else:
                sid_list = self.datamap['pool_list']

        for sid in sid_list:
            if sid in self.datamap['id2scode']:
                item_list.append((sid, self.datamap['id2scode'][sid]))

        #print item_list
        return item_list

    def core(self, item):
        sid = item[0]
        scode = item[1]
        if sid in self.ignore_set:
            return

        if sid in self.pos_map:
            (pno, last_id) = self.pos_map[sid]
        else:
            pno = last_id = 0

        url = "http://stock.gtimg.cn/data/index.php?appn=detail&action=data&c=" + scode + "&p=" + str(pno)
        #print scode, url

        try:
            response = urllib2.urlopen(url, timeout=1)
            content = response.read()
        except urllib2.HTTPError as e:
            self.logger.warning("err=get_stock_transaction sid=%d scode=%s pno=%d code=%s", sid, scode, pno, str(e.code))
            return None
        except urllib2.URLError as e:
            self.logger.warning("err=get_stock_transaction sid=%d scode=%s pno=%d reason=%s", sid, scode, pno, str(e.reason))
            return None

        # 拉取内容为空, 表明股票当天停牌, TODO: 加入公共的停牌列表中
        if 0 == len(content.strip()):
            self.ignore_set.add(sid)
            return

        lines = content.split('"')
        if len(lines) < 2:
            self.logger.warning("err=invalid_resp sid=%d scode=%s content=%s", sid, scode, content)
            return
        #print lines

        elements = lines[1].split("|")
        new_id = last_id
        transaction_list = []

        for element in elements:
            field_list = element.split("/")
            #print field_list
            transaction = dict()

            id = int(field_list[0])
            if id <= last_id :
                continue

            transaction['time'] = field_list[1].replace(":", "")
            transaction['price'] = float(field_list[2])
            transaction['vary_price'] = float(field_list[3])
            transaction['volume'] = int(field_list[4])
            transaction['amount'] = int(field_list[5])
            # 类型为B/S/M, 分别代表买盘/卖盘/中性盘
            transaction['type'] = field_list[6]

            new_id = max(id, new_id)
            transaction_list.append(transaction)

        transaction_count = len(transaction_list)
        #print format_log("fetch_transaction", {'sid': sid, 'scode': scode, 'p': pno, 'last_id': last_id, 'new_id': new_id, 'detail_count': transaction_count})
        self.logger.info(format_log("fetch_transaction", {'sid': sid, 'scode': scode, 'p': pno, 'last_id': last_id, 'new_id': new_id, 'detail_count': transaction_count}))

        if transaction_count > 0:
            # 每个时间段达到70笔成交记录时, p需要加1
            if transaction_count == 70:
                pno += 1

            #更新pno和last_id的值
            self.pos_map[sid] = (pno, new_id)

            self.conn.rpush("ts-queue", json.dumps({'sid': sid, 'day': self.day, 'items': transaction_list}))

# 并行从新浪美股抓取美股当日总览数据
class ParrelUSDaily(ParrelFunc):

    def run(self):
        super(ParrelUSDaily, self).run()

    def get_callcode(self, scode):
        return scode.replace("us", "gb_").lower()

    def get_data(self):
        item_list = []
        scode_list = [ self.get_callcode(scode) for scode in self.datamap['id2scode'].values() ]
        stock_count = len(scode_list)
        #print stock_count

        if "dataset" in self.worker_config:
            scode_dataset = []
            for sid in self.worker_config["dataset"]:
                if sid in self.datamap['id2scode']:
                    scode_dataset.append(self.get_callcode(self.datamap['id2scode'][sid]))
            item_list.append(",".join(scode_dataset))
        else:
            offset = 0
            percount = 50
            while offset < stock_count:
                item_list.append(",".join(scode_list[offset : min(offset + percount, stock_count)]))
                offset += percount

        return item_list

    # 获取股票当前价格及成交量等信息
    def core(self, item):
        scode = item
        url = "http://hq.sinajs.cn/?_=" + str(random.random()) + "&list=" + scode
        #print url

        try:
            response = urllib2.urlopen(url, timeout=1)
            content = response.read()
        except urllib2.HTTPError as e:
            self.logger.warning("err=get_stock_daily scode=%s code=%s", scode, str(e.code))
            return 
        except urllib2.URLError as e:
            self.logger.warning("err=get_stock_daily scode=%s reason=%s", scode, str(e.reason))
            return

        if content:
            content = safestr(content.decode('gbk'))
            #self.logger.info("desc=daily_content content=%s", content)
            lines = content.strip("\r\n").split(";")

            for line in lines:
                if 0 == len(line):
                    continue

                daily_item = self.parse_stock_daily(line)
                if daily_item is None:
                    continue

                # 追加到redis队列中
                #if self.conn:
                #    self.conn.rpush("daily-queue", json.dumps(daily_item))
                self.logger.info(format_log("fetch_daily", daily_item))
                #print format_log("fetch_daily", daily_item)

    # 解析单个股票行情数据
    def parse_stock_daily(self, line):
        line = line.strip("\r\n")
        parts = line.split("=")
        #print line, parts
        stock_code = parts[0].replace("var hq_str_gb_", "").upper()
        content = parts[1].strip('"')
        #print content

        fields = content.split(",")
        #print fields
        if len(fields) < 28:
            line_str = safestr(line)
            self.logger.error(format_log("daily_lack_fields", {'line': line_str, 'content': content}))
            return None

        # 当日停牌则不能存入
        open_price = float(fields[5])
        close_price = float(fields[1])
        if open_price == 0.0 or close_price == 0.0:
            return None

        item = dict()

        try:
            item['name'] = safestr(fields[0])
            item['code'] = stock_code
            item['sid'] = int(self.datamap['code2id'][stock_code])
            item['day'] = self.day
            item['last_close_price'] = float(fields[26])
            item['open_price'] = open_price
            item['high_price'] = float(fields[6])
            item['low_price'] = float(fields[7])
            item['close_price'] = close_price
            # 当前时刻, 格式为HHMMSS
            time_parts = fields[3].split(" ")
            item['time'] = time_parts[1].replace(":", "")
            item['vary_price'] = float(fields[4])
            item['vary_portion'] = float(fields[2])
            # 成交量单位为股
            item['volume'] = int(fields[10])
            #item['predict_volume'] = get_predict_volume(item['volume'], item['time'])
            # 成交额转化为万元
            item['amount'] = 0
            # 总股本
            item['out_capital'] = float(fields[19])
            # 总市值
            item['cap'] = float(fields[12])
            # 计算换手率
            if item['out_capital'] > 0:
                item['exchange_portion'] = item['volume'] / item['out_capital'] * 100
            item['swing'] = (item['high_price'] - item['low_price']) / item['last_close_price'] * 10
        except IndexError:
            self.logger.error(format_log("parse_daily", {'content': content}))
            return None
        except Exception as e:
            return None

        if item['out_capital'] > 0:
            capital = item['out_capital'] / 10000
            self.logger.debug("op=update_sql sql={update t_stock set capital=%.2f, out_capital=%.2f where id = %d;}", capital, capital, item['sid'])
        return item
