# -*- coding: utf-8 -*-
"""
Created on Thu Feb  2 14:33:37 2017

@author: lyb
"""
import win32gui as wg
import win32con as wc
import tushare as ts
import tkinter as tk
import tkinter.scrolledtext as tkst

from os import path, getcwd
from time import sleep
from dateu import get_date
from numpy import array
from datetime import datetime
from retrying import retry

import _thread

# ******* Classes *******


class MyGUI:
    '''
    Iniitilize widgets
    '''

    def __init__(self, my_par):
        'Set contents for all widgets'
        self.master = master = tk.Tk()
        self.init_win(my_par)
        self.editArea1 = self.init_inp(0, 1, "周期分钟   -->", my_par.dt)
        self.editArea2 = self.init_inp(1, 1, "百分阈值   -->", my_par.pc)
        self.editArea3 = self.init_inp(2, 1, "上个交易日 -->", my_par.y)
        self.init_disp()

        self.btnBg = tk.Button(self.frame, text="开始",
                               command=lambda: tutest_procd(self, my_par))
        self.btnBg.grid(padx=40, row=0, column=2, columnspan=2, sticky='nsew')
        self.btnQt = tk.Button(self.frame, text="退出", command=master.destroy)
        self.btnQt.grid(padx=40, row=1, column=2, columnspan=2, sticky='nsew')

    def init_win(self, my_par):
        'Main window'
        self.master.geometry('600x300+10+10')
        self.master.title(my_par.ttl)
        self.frame = tk.Frame(master=self.master)
        self.frame.grid(row=0, column=0, sticky='nsew')
        tk.Grid.rowconfigure(self.master, 0, weight=1)
        tk.Grid.columnconfigure(self.master, 0, weight=1)

    def init_inp(self, ro, co, label, txt):
        'Input area'
        tk.Label(master=self.frame, text=label).grid(
            padx=10, row=ro, column=co - 1, sticky='w')
        editArea = tk.Entry(master=self.frame, width=15)
        editArea.grid(padx=40, row=ro, column=co, sticky='w')
        editArea.insert(0, txt)
        return editArea

    def init_disp(self):
        'Output area'
        self.dispArea = tkst.ScrolledText(
            master=self.frame, wrap=tk.WORD, width=60, height=10)
        self.dispArea.grid(padx=10, pady=10, row=3, column=0,
                           columnspan=4, rowspan=4, sticky='nsew')
        self.dispArea.bind("<1>", lambda event: self.dispArea.focus_set())
        self.update_disp('等待指示！')
        tk.Grid.rowconfigure(self.frame, 3, weight=1)
        tk.Grid.columnconfigure(self.frame, 0, weight=1)

    def update_disp(self, txt):
        'Output area update'
        self.dispArea.configure(state='normal')
        self.dispArea.insert('end', txt + '\n')
        self.dispArea.configure(state='disabled')
        self.dispArea.see('end')
        self.dispArea.update()

    def delete_disp(self):
        'Output area clean'
        self.dispArea.configure(state='normal')
        self.dispArea.delete('1.0', 'end')
        self.dispArea.configure(state='disabled')
        self.dispArea.update()


class MyParams:
    '''
    Iniitilize parameters:
    tday - this trade day
    yday - last trade day
    dt_min - time interval
    ts_perc - percent threshold value
    txt - input file of stock lists
    '''

    def __init__(self, tday, yday, dt_min, ts_perc, txt):
        cpath = path.basename(path.normpath(getcwd()))
        self.ttl = str(datetime.now()) + ' - ' + cpath
        self.t = tday
        self.y = yday
        self.dt = dt_min
        self.pc = ts_perc
        with open(txt) as f:
            self.ln = [r.split()[0] for r in f]


class MyHistQts:
    '''
    Get history volume and information
    '''

    def __init__(self, mygui, par):
        self.info_h = []
        self.get_hist_vol(mygui, par)

    def get_hist_vol(self, mygui, par):
        self.vol_h = [0 for i in range(len(par.ln))]
        for ir in range(len(par.ln)):
            dfy = ts.get_hist_data(par.ln[ir], start=par.y, end=par.y)
            if dfy.empty:
                my_gui.update_disp(str(par.ln[ir]) + ' ' + par.y + ' 停牌')
            else:
                self.vol_h[ir] = dfy.iloc[0]['volume']
            # self.info_h = self.info_h + str(par.ln[ir]) + ' ' + par.y + \
            #         ' 日交易量为 ' + str(self.vol_h[ir]) + '\n'
        self.vol_h = array(self.vol_h)
        par.ln = array(par.ln)[self.vol_h != 0].tolist()
        self.vol_h = self.vol_h[self.vol_h != 0].tolist()


class MyRealQts:
    '''
    Get real-time stock information
    '''

    def __init__(self, par):
        self.get_real_vol(par)

    def get_real_vol(self, par):
        'Get real-time volume'
        dft = self.ult_get_realtime_quotes(par.ln)
        self.vol = [float(i) / 100 for i in dft['volume'].tolist()]
        self.amt = [float(i) for i in dft['amount'].tolist()]
        self.name = dft['name'].tolist()
        self.lctime = dft['time'].tolist()
        self.get_price_change(dft)
        # self.info = today + ' ' + str(self.lctime) + ' 时成交量为 ' + str(self.vol)

    def get_price_change(self, dft):
        'Get real-time price change wrt. the close price of yesterday'
        prc_hist = [float(i) for i in dft['pre_close'].tolist()]
        self.prc = [float(i) for i in dft['price'].tolist()]
        self.prcc = [i for i in range(len(self.prc))]
        for ir in range(len(self.prc)):
            self.prcc[ir] = (self.prc[ir] - prc_hist[ir]) / prc_hist[ir]

    @retry
    def ult_get_realtime_quotes(self, lines):
        'Retry ultimate times'
        return ts.get_realtime_quotes(lines)


class isAlert:
    '''
    Compute real-time volume within a short period, compare it with the voluem
    of last trade day, and alert if condition is satisfied.
    '''

    def __init__(self, hist, rd1, rd2, my_gui, par):
        self.status = [False for i in range(len(par.ln))]
        self.cal_vol(hist, rd1, rd2, my_gui, par)

    def cal_vol(self, hist, rd1, rd2, my_gui, par):
        for ir in range(len(rd1.vol)):
            rt = (rd2.vol[ir] - rd1.vol[ir]) / hist.vol_h[ir] * 100.
            at = rd2.amt[ir] - rd1.amt[ir]

            try:
                pt = (rd2.prc[ir] - rd1.prc[ir]) / rd1.prc[ir]
            except ZeroDivisionError:
                pt = 0.

            if(rt > par.pc):
                atxt = chinese(str(rd2.name[ir]), 9) +\
                    "{:<10}".format(str(rd2.lctime[ir])) +\
                    "{:<9}".format(str(format(rd2.prcc[ir], '.2%'))) +\
                    "{:<11}".format(str(format(pt, '.2%'))) +\
                    "{:<8}".format(str(at)) +\
                    ' || ' + str(par.dt) + '分钟内成交量为昨日' +\
                    "{:<8}".format(str(format(rt / 100., '.2%')))
                my_gui.update_disp(atxt)
                self.flash(par.ttl)
                self.status[ir] = True

    def flash(self, ttl):
        'Flash the caption and taskbar icon'
        ID = wg.FindWindow(None, ttl)
        wg.FlashWindowEx(ID, wc.FLASHW_STOP, 0, 0)
        cur_foreground = wg.GetForegroundWindow()
        if ID == cur_foreground:
            taskbar = wg.FindWindow("Shell_TrayWnd", None)
            wg.SetForegroundWindow(taskbar)
        wg.FlashWindowEx(ID, wc.FLASHW_ALL | wc.FLASHW_TIMERNOFG, 0, 0)

# ******* Functions *******
def fo_nomerge(name):
    i = 0
    while path.exists(name + '-' + str(i) + '.txt'):
        i += 1
    fo = open(name + '-' + str(i) + '.txt', 'w')
    return fo


def chinese(oldstr, length):
    '''
    To solve the chinese character alignment issue in python.
    The display and count differences in length is automatically compensated.
    '''
    count = 0
    for s in oldstr:
        if ord(s) > 127:
            count += 1
    newstr = oldstr
    if length > count:
        newstr = '{0:{wd}}'.format(oldstr, wd=length - count)
    return newstr


def trig_alert(mygui, par):
    '''
    Check the status of cal_vol every specific time interval
    '''
    vol_hist = MyHistQts(mygui, par)
    info = '************* 开始监控盘中实时交易量 *************\n' +\
        chinese('股名', 9) + chinese('时间', 10) + chinese('涨幅', 9) +\
        chinese('瞬时涨幅', 11) + chinese('成交金额', 8)
    my_gui.update_disp(info)

    real_data1 = MyRealQts(par)
    count = 0
    sleep(int(par.dt * 60))

    # fo = fo_nomerge('AlertStatus')
    # fo.write(str(count) + '分钟：' + str(par.ln) + '\n')
    while(count < 420 / par.dt):
        real_data2 = MyRealQts(par)
        # real_data2.vol = [i + 2000 for i in real_data1.vol]  # Only for test
        alert = isAlert(vol_hist, real_data1, real_data2, mygui, par)
        real_data1 = real_data2
        count = count + 1
        # fo.write(str(count) + '分钟：' + str(alert.status) + '\n')
        sleep(int(par.dt * 60))

    # fo.close()
    my_gui.update_disp('监控完成！')


def tutest_procd(mygui, my_par):
    try:
        my_par.dt = float(my_gui.editArea1.get())
        my_par.pc = float(my_gui.editArea2.get())
        my_par.yday = my_gui.editArea3.get()
        datetime.strptime(my_par.yday, '%Y-%m-%d')
    except ValueError:
        my_gui.update_disp("参数格式不正确！请重新输入！！!")
        return

    my_gui.delete_disp()
    my_gui.update_disp(" 监控股票 " + str(my_par.ln))
    _thread.start_new_thread(trig_alert, (mygui, my_par))


today, yesterday = get_date()
my_par = MyParams(today, yesterday, str(2), str(2), "股票代码.txt")
my_gui = MyGUI(my_par)
my_gui.master.mainloop()
