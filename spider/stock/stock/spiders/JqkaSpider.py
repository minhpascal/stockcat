#!/usr/bin/python
#-*- coding: UTF-8 -*-
#author: fox
#desc: 抓取同花顺上的股票数据
#date: 2013-07-26

import sys, re, json
#sys.path.append('../../../server')  
#from pyutil.util import safestr
from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy import log
from stock.items import StockItem

class JqkaSpider(BaseSpider):
    name = "10jqka"
    allowed_domains = ["10jqka.com", "10jqka.com.cn"]
    base_url = "http://www.10jqka.com"
    item_count = 0
    industry = ""
    slug = ""

    def __init__(self, url):
        self.url = url
        self.start_urls = [url]

    # 解析行业页面
    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        # 解析行业名称
        self.industry = hxs.select('//div[@class="crumbs"]/span[@class="cur"]/text()')[0].extract()
        url_fields = self.url.rstrip("/").split("/")
        self.slug = url_fields[-1]

        # 解析页码
        page_list = []
        for page_no_str in hxs.select('//div[@class="m_page main_page"]/a/text()').extract():
            if page_no_str.isdigit():
                page_list.append(int(page_no_str))
        page_count = max(page_list)
        #print "industry=" + self.industry + " page_count=" + str(page_count)
         
        prefix = "http://q.10jqka.com.cn/interface/stock/detail/zdf/desc/"
        for page_index in range(1, page_count+1):
            api_url = prefix + str(page_index) + "/1/" + self.slug
            #print api_url
            yield Request(api_url, callback=self.parse_data)
            
    # 解析api的请求应答        
    def parse_data(self, response):
        resp = json.loads(response.body)
        stock_url = "http://stockpage.10jqka.com.cn/"

        for stock_info in resp['data']:
            #print stock_info['stockname'], stock_info['stockcode']
            yield Request(stock_url + stock_info['stockcode'] + "/", callback=self.parse_stock)

    # 解析个股详情页面的数据
    def parse_stock(self, response):
        hxs = HtmlXPathSelector(response)
        #log.msg(response.body)
        item = StockItem()

        #print hxs.select('//div/h1')
        #print hxs.select('//div/h1/a/text()').extract()
        #print hxs.select('//div/h1/a/strong/text()').extract()
        item['name'] = hxs.select('//div/h1/a/strong/text()').extract()[0] 
        item['code'] = hxs.select('//div/h1/a/text()').extract()[1].strip(" \t\n")
        #print item
      
        company_node = hxs.select('//dl[contains(@class, "company_details")]')
        strong_list = company_node.select('.//dd/strong/text()').extract()
        #print strong_list

        item['captial'] = float(strong_list[0]) 
        item['out_captial'] = float(strong_list[1])
        item['profit'] = float(strong_list[4])
        item['assets'] = float(strong_list[5])
        #print item
    
        company_url = "http://stockpage.10jqka.com.cn/" + item['code'] + "/company/"
        request = Request(company_url, callback=self.parse_company)  
        request.meta['item'] = item
        yield request

    # 解析公司详情
    def parse_company(self, response):
        hxs = HtmlXPathSelector(response)
        item = response.meta['item']

        span_list = hxs.select('//div[@class="bd"]/table[@class="m_table"]/tbody/tr/td/span/text()').extract()
        #print span_list
        item['company'] = span_list[0]
        item['location'] = span_list[1]

        tab2_span_list = hxs.select('//div[@class="m_tab_content2"]/table/tbody/tr/td/span/text()').extract()
        #print tab2_span_list
        item['business'] = tab2_span_list[0]

        return item

