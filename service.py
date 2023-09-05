# -*- coding: utf-8 -*-
import urllib.request
import re
import pandas as pd
import matplotlib.pyplot as plot
import numpy as np
import datetime
import matplotlib.gridspec as gridspec
import time


def getHtml(url):
    '''
        description: 获取整个html
    '''
    while True:
        try:
            html = urllib.request.urlopen(url, timeout=5).read()
            break
        except:
            print("超时重试")
    html = html.decode('gbk')
    return html


def getTable(html):
    '''
        description: 获取表
    '''
    s = r'(?<=<table class="datatbl" id="datatbl">)([\s\S]*?)(?=</table>)'
    pat = re.compile(s)
    code = pat.findall(html)
    return code


def getTitle(tableString):
    '''
        description: 获取列名
    '''
    s = r'(?<=<thead)>.*?([\s\S]*?)(?=</thead>)'
    pat = re.compile(s)
    code = pat.findall(tableString)
    s2 = r'(?<=<tr).*?>([\s\S]*?)(?=</tr>)'
    pat2 = re.compile(s2)
    code2 = pat2.findall(code[0])
    s3 = r'(?<=<t[h,d]).*?>([\s\S]*?)(?=</t[h,d]>)'
    pat3 = re.compile(s3)
    code3 = pat3.findall(code2[0])
    return code3


def getBody(tableString):
    '''
        description: 获取所有记录
    '''
    s = r'(?<=<tbody)>.*?([\s\S]*?)(?=</tbody>)'
    pat = re.compile(s)
    code = pat.findall(tableString)
    s2 = r'(?<=<tr).*?>([\s\S]*?)(?=</tr>)'
    pat2 = re.compile(s2)
    code2 = pat2.findall(code[0])
    s3 = r'(?<=<t[h,d]).*?>(?!<)([\s\S]*?)(?=</)[^>]*>'
    pat3 = re.compile(s3)
    code3 = []
    for tr in code2:
        code3.append(pat3.findall(tr))
    return code3


def scrap_tick(symbol, date, page=1, url=url):
    '''
        description: 爬取每日分时数据
        symbol: market+code, sh600000, sz000001, ..., stock_code=symbol[-6:]
        date: string as YYYY-MM-DD
        page: default 1 
    '''
    # 利用headers拉动请求，模拟成浏览器去访问网站，仅能跳过最简单的反爬虫机制。
    # 由于新浪设置了更高级别的反爬虫机制(限定IP访问机制)，从而只能采取sleep被动等待策略。
    # “停止异常访问一段时间后(5~60分钟)会自动解封, 请耐心等待.”
    # request timeout不宜设定过长，尽量在新浪封禁前完成单日爬取

    tick_list = []
    while True:
        base_url = 'http://market.finance.sina.com.cn/transHis.php?symbol='
        Url = base_url + symbol + '&date=' + date + '&page=' + str(page)
        # Url: http://market.finance.sina.com.cn/transHis.php?symbol=sh600000&date=2019-04-19&page=1
        print(Url)
        html = getHtml(Url)
        table = getTable(html)
        if len(table) != 0:
            tbody = getBody(table[0])
            if len(tbody) == 0:
                print("结束")
                break
            if page == 1:
                thead = getTitle(table[0])
                print(['---------------------------']+thead)
            for tr in tbody:
                tick_list.append([date]+tr)
        else:
            print("当日无数据")
            break
        page += 1

    cols = ['tick_date','tick_time','price','price_change','volume','amount','tick_type']
    df = pd.DataFrame(tick_list, columns=cols)
    # all columns are string type
    return df


def format_tick(df):
    '''
        df is original dataframe with daily tick data from scrap_tick()
        return formatted dafaframe
    '''
    if len(df) == 0 :
        return df

    # Deal with price and volume
    df[['price', 'volume']] = df[['price', 'volume']].apply(pd.to_numeric)
    df['volume'] = df['volume'].values \
                   * df['tick_type'].apply(lambda x: 1 if x==u'买盘' else -1 if x==u'卖盘' else 0 )

    # # Reindex by datetime(waste of time)
    # index_list = []
    # for i in df.index :
    #     index = str(df.loc[i]['tick_date']) + ' ' + str(df.loc[i]['tick_time'])[-8:]
    #     index_list.append(datetime.datetime.strptime(index, "%Y-%m-%d %H:%M:%S"))
    # df.index = index_list

    # # Reindex by datetime(more fast)
    df['datetime'] = df['tick_date'] + ' ' + df['tick_time']
    df['datetime'] = df['datetime'].apply(lambda x: datetime.datetime.strptime(x, "%Y-%m-%d %H:%M:%S"))
    df.set_index(['datetime'], inplace=True)

    # # Sort dataframe by datetime
    # df.sort_values(['tick_date', 'tick_time'], inplace=True)

    # Sort dataframe from desc to asc
    df.sort_index(inplace=True)

    # Re-sampling
    # String type column will be dropped after resampling.
    # After re-sampling, (non-trading days and) non-trading time will be introduced.
    df = df.resample(rule='1min').mean() #, how='mean') #重采样后会引入非交易日和非交易时间

    # Remove non-trading time
    df = df[((df.index.time >= datetime.time(9, 30)) & (df.index.time <= datetime.time(11, 30)))
            | ((df.index.time >= datetime.time(13, 0)) & (df.index.time <= datetime.time(15, 0)))]

    #df['price'] = df['price'].fillna(method='bfill')   #以收盘价填充最后几分钟的股价（以神州信息2015-5-11为例，最后一笔数据14:44:48，该填充方式会引入下一日开盘价）
    df['price'] = df['price'].fillna(method='ffill')    #改用以最后一笔高频数据填充
    df['volume'] = df['volume'].fillna(0)               #以0填充最后几分钟的成交量

    # # Drop useless columns(have been dropped)
    # df = df.drop(['tick_date', 'tick_time'], axis=1)

    '''
    df.info()
    < class 'pandas.core.frame.DataFrame'>
    Index: 242 entries, YYYY-MM-DD 09: 30:00 to YYYY-MM-DD 15:00:00
    Data columns (total 2 columns):
    price     242 non-null float64
    volume    242 non-null float64
    dtypes: float64(2)
    memory usage: 5.7 + KB
    '''
    return df


def multiple_tick(symbol, start_date, period):
    '''
        symbol: market+code, sh600000, sz000001, ..., stock_code=symbol[-6:]
        start_date: string, YYYY-MM-DD
        period: int
    '''
    days = list(pd.date_range(start_date, periods=period, freq='D').values.astype('datetime64[D]'))
    df_multiple = pd.DataFrame()
    for day in days:
        df = scrap_tick(symbol, str(day))
        df = format_tick(df)
        df_multiple = df_multiple.append(df)
        if day == days[-1]:
            break
        print('sleeping for 300 seconds...')
        time.sleep(300)

    return df_multiple


def save_tick(df):
    '''
    df is formatted dataframe from format_tick() or multiple_tick()
    save df to txt file
    '''
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    df.to_csv(timestamp+'.txt', sep=';', float_format='%.2f', index=True, header=True)
    print("tick data saved.")


def load_tick(filename):
    '''
    load tick data as df from csv file
    '''
    df = pd.read_csv(filename, sep=';', header=0, index_col=0)
    print(filename, 'file loaded with', len(df), 'rows.')
    return df


def plot_tick(df, display=False):
    '''
        绘制多日(1m)分时图(含成交量)
        df is of mutiple days from multiple_tick()
    '''
    # Make xticks and xticklabels
    df['order'] = np.arange(len(df))
    days = list(set(df.index.date)) #set不支持索引取值需转换为list
    days.sort()                     #set去重后为乱序
    xticks = []
    for day in days:
        xticks.append(df[df.index.date == day]['order'].min())
        print (df[df['order'] == xticks[-1]].index)
    xticks.append(len(df)-1)
    print("xticks:", xticks)
    xticklabels = days[:]   #list复制而不能是赋值
    #xticklabels.insert(0, xticklabels[0]+datetime.timedelta(days = -1))

    fig, ax = plot.subplots(figsize=(12, 4), nrows=2, ncols=1)
    gs = gridspec.GridSpec(3, 1)#1->6
    ax[0] = plot.subplot(gs[:-1, :])
    ax[1] = plot.subplot(gs[2, :])

    #ax[0].grid(axis="x")    #先定义网格线，避免柱状图被覆盖
    ax[0].plot(df['order'], df['price'])
    ax[0].set_xticks(xticks)
    ax[0].set_xticklabels([])
    ax[0].set_xlim([xticks[0], xticks[-1]])     #设置x轴坐标范围
    ax[0].tick_params(length=0)                 #隐藏刻度(含x，y轴)
    ax[0].get_xaxis().set_visible(False)        #隐藏x轴（浅灰色，含）
    ax[0].spines['bottom'].set_visible(False)   #隐藏子图下边沿（实黑色）

    #ax[1].grid(axis="x")
    ax[1].bar(df[df['volume'] >= 0]['order'], df[df['volume'] >= 0]['volume'], color='r')
    ax[1].bar(df[df['volume'] < 0]['order'], df[df['volume'] < 0]['volume'], color='g')
    ax[1].set_xticks(xticks)
    ax[1].set_xticklabels(xticklabels, rotation = 0)  #角度
    for tick in ax[1].xaxis.get_majorticklabels():
        tick.set_horizontalalignment("left")
    ax[1].set_xlim([xticks[0], xticks[-1]])
    ax[1].set_ylim([-abs(df['volume'].max()), abs(df['volume'].max())])
    ax[1].tick_params(length=0)
    ax[0].get_xaxis().set_visible(False)
    ax[1].spines['top'].set_visible(False)
    #-----------------------------1 Day-------------------------------
    #xticks=list(range(0,len(fr),len(fr)/4))
    #xticks.append(len(fr))
    #ax.set_xticks(xticks)
    #ax.set_xticklabels(['9:30','10:30','11:30/13:00','14:00','15:00'])
    #-----------------------------------------------------------------
    fig.tight_layout()                          #调整整体空白
    plot.subplots_adjust(wspace=0, hspace=0)    #调整子图间距

    if display:
        plot.show()
    else :
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
        filename = timestamp+'.jpg'
        plot.savefig(filename)
        print(filename+'figure saved.')
