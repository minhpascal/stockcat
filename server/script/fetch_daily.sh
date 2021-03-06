#!/bin/bash
#desc: 抓取股票每日总览数据
#author: fox
#date: 2013-08-12

main()
{
    stype="stock"
    day=`date "+%Y%m%d"`

    if [ $# -ge 1 ]
    then
        stype=$1
    fi
    if [ $# -ge 2 ]
    then
        day=$2
    fi

    open=`is_market_open "$day"`
    echo "stype=$stype day=$day open=$open"
    if [ "$open" == "0" ]
    then
        exit
    fi

    cd $STOCK_SCRAPY_PATH
    result_path=$STOCK_SCRAPY_PATH/data/$day
    if [ ! -d $result_path ]
    then
        mkdir $result_path
    fi

    log="daily_${stype}_$day.log"
    filename="daily_${stype}_$day.json"
    echo "log=$log filename=$filename"

    # 用scrapy抓取总览信息
    if [ "stock" == $stype ]
    then
        $SCRAPY_BIN crawl qqdaily -a filename=$STOCK_LIST -a request_count=10 -a day=$day -o $result_path/$filename --logfile=$result_path/fetch_daily.log >> $result_path/$log
        #$SCRAPY_BIN crawl daily -a filename=$STOCK_LIST -a request_count=10 -a day=$day -o $result_path/$filename --logfile=$result_path/fetch_daily.log >> $result_path/$log
    else
        $SCRAPY_BIN crawl qqdaily -a filename=$INDEX_LIST -a request_count=9 -a day=$day -o $result_path/$filename --logfile=$result_path/fetch_daily.log >> $result_path/$log
        #$SCRAPY_BIN crawl daily -a filename=$INDEX_LIST -a request_count=9 -a day=$day -o $result_path/$filename --logfile=$result_path/fetch_daily.log >> $result_path/$log
    fi

    # 导入数据
    $PHP_BIN -c /etc/php.ini $WEB_PATH/console_entry.php importDaily $result_path/$filename >> $WEB_PATH/import_daily.log

    echo "finish"
}


cd ${0%/*}
. ./comm.inc
main "$@"
