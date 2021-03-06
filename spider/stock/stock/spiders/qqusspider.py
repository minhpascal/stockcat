#!/usr/bin/python
#-*- coding: UTF-8 -*-
#author: fox
#desc: 抓取qq上的美股股票列表
#date: 2014/09/29

import sys, re, json, random
sys.path.append('../../../server')  
from pyutil.util import safestr
from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy import log
from stock.items import StockItem

class QQUsSpider(BaseSpider):
    name = "qqus"
    allowed_domains = ["gtimg.cn", "finance.qq.com", "stockhtm.finance.qq.com", "stock.finance.qq.com"]
    industry = ""

    def __init__(self, url, category, page_count):
        self.category = category
        self.page_count = int(page_count)
        self.url = url
        self.start_urls = [url]

    def parse(self, response):
        for i in range(1, self.page_count + 1):
            url = "http://stock.gtimg.cn/data/index.php?appn=usRank&t=" + self.category + "/volume&p=" + str(i) + "&o=0&l=80&v=list_data&_du_r_t=" + str(random.random())
            print url
            yield Request(url, callback=self.parse_json)

    # 解析列表页的应答包
    def parse_json(self, response):
        parts = response.body.split("=")
        content = safestr(parts[1].decode('gbk'))
        #print content

        data = json.loads(content)
        item_list = data['data']['result']
        print len(item_list)

        for info in item_list:
            item = StockItem()
            item['location'] = 3

            code = info[0]   
            code_parts = code.split(".")
            if len(code_parts) >= 2:
                ecode = code_parts[-1]
                if "N" == ecode:
                    item['ecode'] = "NYSE"
                elif "OQ" == ecode:
                    item['ecode'] = "NASDAQ" 

            item['name'] = info[2]
            item['code'] = info[1]

            stock_url = "http://stockhtm.finance.qq.com/astock/ggcx/" + code + ".htm"
            #print stock_url
            request = Request(stock_url, callback=self.parse_data)
            request.meta['item'] = item
            yield request

    # 解析
    def parse_data(self, response):
        hxs = HtmlXPathSelector(response)
        item = response.meta['item']

        # 获取股息
        col25_list = hxs.select('//span[contains(@class, "col-2-5")]/text()').extract()
        for text in col25_list:
            if text == "--":
                continue
            else:
                item['dividend'] = float(text)

        col24_list = hxs.select('//span[contains(@class, "col-2-4")]/text()').extract()
        for text in col24_list:
            if text == "--":
                continue
            else:
                text = text.replace(",", "")
                #print text
                m = re.match(r"(\d+)[^0-9]*", text)
                if m:
                    item['captial'] = float(float(m.group(1)) / 10000)

        #print item

        ecode = "N"
        if item['ecode'] == "NASDAQ":
            ecode = "OQ"
        info_url = "http://stock.finance.qq.com/astock/list/view/info.php?c=" + item['code'] + "." + ecode
        #print info_url

        request = Request(info_url, callback=self.parse_company)
        request.meta['item'] = item
        yield request

    # 解析公司详情
    def parse_company(self, response):
        hxs = HtmlXPathSelector(response)
        item = response.meta['item']

        td_list = hxs.select('//table/tr/td/text()').extract()
        td_count = len(td_list)
        if td_count >= 2:
            item['alias'] = safestr(td_list[1])
        if td_count >= 9:
            item['business'] = safestr(td_list[-1])

        #print item
        return item

