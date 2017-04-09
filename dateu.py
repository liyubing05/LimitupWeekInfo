# -*- coding: utf-8 -*-
"""
Created on Thu Feb  2 14:33:37 2017

@author: lyb
"""
import datetime as dtt
from pandas import read_csv
from tushare import stock as tstck

def get_date():
    'Get the date of today and yesterday'
    tday = get_today()
    yday = last_tddate(tday)
    while is_holiday(str(yday)):
        yday = last_tddate(yday)
    return str(tday), str(yday)


def get_today():
    day = dtt.datetime.today().date()
    return day


def day_last_week(date, days=-7):
    lasty = date + dtt.timedelta(days)
    return lasty


def trade_cal():
    '''
            交易日历
    isOpen=1是交易日，isOpen=0为休市
    '''
    df = read_csv(tstck.cons.ALL_CAL_FILE)
    return df


def is_holiday(date):
    '''
            判断是否为交易日，返回True or False
    '''
    df = trade_cal()
    holiday = df[df.isOpen == 0]['calendarDate'].values
    if isinstance(date, str):
        tday = dtt.datetime.strptime(date, '%Y-%m-%d')

    if tday.isoweekday() in [6, 7] or date in holiday:
        return True
    else:
        return False


def last_tddate(tday):
    t = int(tday.strftime("%w"))
    if t == 0:
        return day_last_week(tday, -2)
    else:
        return day_last_week(tday, -1)
