# -*- coding: UTF-8 -*-

# import

from colorama import Fore, Style
import inspect
import pandas as pd
import random
from datetime import datetime  # For datetime objects
import backtrader as bt

# globals

# functions/classes
class TestStrategy_SMA(bt.Strategy):
    """
    Sandbox for different test strategies
    """
    params = (
        ('bars_decline', 3),
        ('bars_since_last_sell', 5),
        ('ma_period', 15),
        ('long_period', 25),
    )

    def __init__(self):
        # Keep a reference to the "close" line (column) in the data[0] data series
        # self.data is equivalent to self.datas[0] or self.data_0, if there is more than one data feed
        self._dataclose = self.datas[0].close

        # To keep track of pending orders
        self._order = None

        # 105
        self._bar_executed = 0
        # self._buyprice = None
        # self._buycomm = None

        # 105a For logging trade results only
        self.trade_results = pd.DataFrame({
            'date': pd.Series(dtype='str'),
            'price': pd.Series(dtype='float64'),
            'pnl': pd.Series(dtype='float64'),
            'pnlcomm': pd.Series(dtype='float64')
        })

        #106 Add a Moving Average indicator.
        # Adding an indicator changes the strategy's behavior!
        # A SMA needs a certain number of bars (params.ma_period) to calculate the average.
        # No call to next() will be made until the SMA has enough bars to calculate the average.
        self._sma = bt.indicators.MovingAverageSimple(self.datas[0], period=self.params.ma_period)

        # 107 Add more indicators
        bt.indicators.ExponentialMovingAverage(self.datas[0], period=self.p.long_period)
        # Weighted Moving Average = trend indicator
        bt.indicators.WeightedMovingAverage(self.datas[0], period=self.p.long_period, subplot=True)
        bt.indicators.StochasticSlow(self.datas[0]) # Stochastic Oscillator
        # Moving Average Convergence Divergence = trend indicator as histogram
        bt.indicators.MACDHisto(self.datas[0])
        # Relative Strength Index = momentum indicator
        rsi = bt.indicators.RSI(self.datas[0])
        # Smoothed Moving Average of the RSI = trend indicator
        bt.indicators.SmoothedMovingAverage(rsi, period=10)
        # Average True Range = volatility indicator
        self._atr = bt.indicators.ATR(self.datas[0],)   # plot=False) # Average True Range

    def log(self, txt, dt=None):
        """
        Logging function for this strategy
        """
        caller = inspect.stack()[1].function
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{len(self):3} {caller:15}\t{dt.strftime('%d.%m.%Y')} {txt}')

    def next(self):
        """
        Die Methode next() in einer Backtrader-Strategie wird bei jedem neuen Datenpunkt (Bar) aufgerufen und enthält
        die Handelslogik der Strategie.
        Die next()-Methode überprüft den aktuellen Marktstatus, entscheidet basierend auf der definierten Handelslogik,
        ob Kauf- oder Verkaufsorders erstellt werden sollen, und loggt relevante Informationen.
        """
        # Log the closing price of the series from the reference
        # self.log(f'{Style.DIM}Close {self.dataclose[0]:,.2f}{Style.RESET_ALL}\tNumber of bars processed: {len(self)}')
        # self.log(f'{self.data.open[0]:,.2f} {self.data.high[0]:,.2f} {self.data.low[0]:,.2f}'
        #          f' {Style.BRIGHT}{self.data.close[0]:,.2f}{Style.NORMAL}  Vol: {self.data.volume[0]:,.2f}')

        self.log(f'Portfolio: Position size: {self.position.size} shares,'
                 f' Available cash: {self.broker.get_cash():,.2f}'
                 f' Investment value: {self.broker.get_value() - self.broker.get_cash():,.2f}'
                 f' Portfolio value: {self.broker.get_value():,.2f}', )

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self._order:
            self.log(f'{Fore.RED}Order pending: {self._order.isbuy()} No new order allowed!{Fore.RESET}')
            return

        # 105 Check if the closing prices have decreased over the last `days_decline` bars
        # buy_condition = all(self._dataclose[-i] < self._dataclose[-(i + 1)] for i in range(self.p.bars_decline - 1))
        # sell_condition = len(self) >= (self._bar_executed + self.p.bars_since_last_sell)

        prob = 1 # random.choice([1, 0]) # 50% chance for a buy order
        buy_condition = (self._dataclose[0] > self._sma[0]) and prob # better to buy when the price is above the moving average
        sell_condition = (self._dataclose[0] < self._sma[0]) # sell when the price is below the moving average

        # based on  volatility
        # buy_condition = self._atr[0] < 2.0
        # sell_condition = self._atr[0] > 2.2


        # Check if we are in the market. Every completed BUY order creates a position?
        if not self.position:
            # Not yet ... we MIGHT BUY if ...
            if buy_condition:
                # BUY, BUY, BUY!!! (with all possible default parameters)
                self.log(f'{Fore.GREEN}Create BUY order {self._dataclose[0]:,.2f}{Fore.RESET}')
                self._order = self.buy()
        else:
            # Already in the market (positions exist) ... we might sell
            if sell_condition:
                # SELL, SELL, SELL!!! (with all possible default parameters)
                self.log(f'{Fore.YELLOW}Create SELL order {self._dataclose[0]:,.2f}{Fore.RESET}')
                # Keep track of the created order to avoid a 2nd order
                self._order = self.sell()

    def notify_order(self, order):
        """
        The order lifecycle is managed through the notify_order method,
        which is called whenever the status of an order changes.
        This ensures that the strategy can react to order completions, rejections, or cancellations in a controlled manner.
        Here is a brief overview of how orders are processed:
            - Order Submission: Orders are submitted within the next method.
            - Order Notification: The notify_order method is called to update the status of the order.
            - Order Execution: Orders are executed based on the market data and broker conditions.
        This synchronous processing ensures that the strategy can manage orders and positions in a
        predictable and sequential manner.

        This method will be called whenever an order status changes
        Order details can be analyzed
        """
        action = f'{Fore.GREEN}BUY{Fore.RESET}' if order.isbuy() else f'{Fore.YELLOW}SELL{Fore.RESET}'

        if order.status in {order.Submitted, order.Accepted}:
            self.log(f'{action} order {order.Status[order.status]} to/by broker - Nothing to do')
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status == order.Completed:
            self.log(f'{Style.BRIGHT}{action} order executed at {order.executed.price:,.2f}'
                     f'\tCommission: {order.executed.comm:,.2f} {Style.RESET_ALL}')

            # 105
            if order.isbuy():
                pass
                # self.buyprice = order.executed.price
                # self.buycomm = order.executed.comm

            # len(self) is the number of bars processed
            self._bar_executed = len(self)  # Save the bar where the order was executed

        elif order.status in {order.Canceled, order.Margin, order.Rejected}:
            self.log(f'{Fore.RED}Order note executed! Status = {order.status} (Canceled/Margin/Rejected){Fore.RESET}')

        # Write down: no pending order
        self._order = None

    # 105
    def notify_trade(self, trade):
        """
        The notify_trade method is called whenever there is a change in the status of a trade.
        This method is used to handle and log trade results, such as when a trade is closed or its status changes.
        The method has two primary functions:
            - Logs Trade Results: It logs the results of a trade, including whether it was a profit or loss,
              and the gross and net profit/loss.
            - Updates Trade DataFrame: It updates a DataFrame with the trade details, such as date, price, status,
              and profit/loss.
        notify_trade is Called:
            - Trade Closed: When a trade is closed, the method logs the result and updates the DataFrame.
            - Trade Status Change: When the status of a trade changes, it logs the new status.
        """
        if trade.isclosed:
            result = 'profit' if trade.pnlcomm > 0 else 'loss'
            self.log(
                    f'Trade is closed. Operation {result}, gross: {trade.pnl:,.2f}, net (incl.commission): {trade.pnlcomm:,.2f}'
            )
            # 105a Log the trade results
            new_row = {
                'date': self.datas[0].datetime.date(0).strftime('%d.%m.%Y'),
                'price': float(trade.price),
                'pnl': float(trade.pnl),
                'pnlcomm': float(trade.pnlcomm)
            }

            # Append the new row to the DataFrame
            self.trade_results = self.trade_results._append(new_row, ignore_index=True)

        else:
            self.log(f'Trade status: {trade.status_names[trade.status]}\tNothing to do!')
            return

class TestStrategy_simple(bt.Strategy):

    def log(self, txt, dt=None):
        ''' Logging function fot this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

    def next(self):
        # Simply log the closing price of the series from the reference
        self.log('Close, %.2f' % self.dataclose[0])

        if self.dataclose[0] < self.dataclose[-1]:
            # current close less than previous close

            if self.dataclose[-1] < self.dataclose[-2]:
                # previous close less than the previous close

                # BUY, BUY, BUY!!! (with all possible default parameters)
                self.log('BUY CREATE, %.2f' % self.dataclose[0])
                self.buy()

class TestStrategy_104(bt.Strategy):

    def log(self, txt, dt=None):
        ''' Logging function fot this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # To keep track of pending orders
        self.order = None

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log('BUY EXECUTED, %.2f' % order.executed.price)
            elif order.issell():
                self.log('SELL EXECUTED, %.2f' % order.executed.price)

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        # Write down: no pending order
        self.order = None

    def next(self):
        # Simply log the closing price of the series from the reference
        self.log('Close, %.2f' % self.dataclose[0])

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return

        # Check if we are in the market
        if not self.position:

            # Not yet ... we MIGHT BUY if ...
            if self.dataclose[0] < self.dataclose[-1]:
                    # current close less than previous close

                    if self.dataclose[-1] < self.dataclose[-2]:
                        # previous close less than the previous close

                        # BUY, BUY, BUY!!! (with default parameters)
                        self.log('BUY CREATE, %.2f' % self.dataclose[0])

                        # Keep track of the created order to avoid a 2nd order
                        self.order = self.buy()

        else:

            # Already in the market ... we might sell
            if len(self) >= (self.bar_executed + 5):
                # SELL, SELL, SELL!!! (with all possible default parameters)
                self.log('SELL CREATE, %.2f' % self.dataclose[0])

                # Keep track of the created order to avoid a 2nd order
                self.order = self.sell()

class TestStrategy_Commission(bt.Strategy):

    def log(self, txt, dt=None):
        ''' Logging function fot this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))

                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:  # Sell
                self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm))

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))

    def next(self):
        # Simply log the closing price of the series from the reference
        self.log('Close, %.2f' % self.dataclose[0])

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return

        # Check if we are in the market
        if not self.position:

            # Not yet ... we MIGHT BUY if ...
            if self.dataclose[0] < self.dataclose[-1]:
                    # current close less than previous close

                    if self.dataclose[-1] < self.dataclose[-2]:
                        # previous close less than the previous close

                        # BUY, BUY, BUY!!! (with default parameters)
                        self.log('BUY CREATE, %.2f' % self.dataclose[0])

                        # Keep track of the created order to avoid a 2nd order
                        self.order = self.buy()

        else:

            # Already in the market ... we might sell
            if len(self) >= (self.bar_executed + 5):
                # SELL, SELL, SELL!!! (with all possible default parameters)
                self.log('SELL CREATE, %.2f' % self.dataclose[0])

                # Keep track of the created order to avoid a 2nd order
                self.order = self.sell()


if __name__ == '__main__':
    print('This script is not meant to be run directly.')
