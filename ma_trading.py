import time
import ti_functional as tif
from trading_strategies import ma_trading_strategy
import lock_info


main_account_id = lock_info.main_account_id
stock_list =  ['SBER', 'VTBR', 'SNGS', 'LKOH', 'GAZP', 'YNDX', 'TCSG', 'RUAL',
               'PLZL', 'MAGN', 'POLY', 'MTSS', 'ROSN', 'MOEX', 'RTKM', 'TATN']

stock_info = tif.get_main_stock_info(stock_list)
#
# def start_trading():
#     now = time.localtime()
#     while 10.15 < now.tm_hour + now.tm_hour/100 < 18.35:
#         now = time.localtime()
#         print(f'Current time: {now.tm_hour}:{now.tm_min}:{now.tm_sec}')
#
#         if now.tm_min in [2, 17, 32, 47]:
#             for tick in stock_list:
#                 print(tick, end=' -> ')
#                 ma_trading_strategy(tick, main_account_id, stock_info)
#
#         time.sleep(59)  # Delay for 15 minute (15 * 60 seconds).
#
#     print(f'Current time: {now.tm_hour:02}:{now.tm_min:02}:{now.tm_sec:02}')
#     print('Time outside the trading period')
#
# if __name__ == "__main__":
#     start_trading()
#

tick = 'SBER'
ma_trading_strategy(tick, main_account_id, stock_info)