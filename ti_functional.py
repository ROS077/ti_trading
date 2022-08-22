import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta

from tinkoff.invest import Client, CandleInterval, InstrumentIdType, Quotation, schemas, OrderDirection,\
                            StopOrderDirection, StopOrderExpirationType, StopOrderType
import yaml
import pytz
import lock_info

CONTRACT_PREFIX = "tinkoff.public.invest.api.contract.v1."
main_account_id = lock_info.main_account_id
TOKEN = lock_info.token


def money_to_val(value):
    """
    Переводит и возвращает цену из формата Quotation в float
    :param value: Quotation
    :return: float
    """
    return value.units + value.nano / 1e9


def money_to_val_r(value, rnd=10):
    """
    Переводит и возвращает цену из формата float в Quotation
    :param rnd: int - decimal
    :param value: float - price
    :return: Quotation
    """
    units, nano = (map(int, str(float(value)).split('.')))
    nano = int(round((value - units), rnd) * 1e9)
    return Quotation(units, nano)


def price_features(nano):
    """
    Возвращает для тикера свойства округления:
    nano: int - цена после запятой, по ней определяется уровень и база округления
    n_dec: кол-во знаков после запятой 
    base: база округления
    """
    n_dec = 10 - len(str(nano))
    base = int(str(nano)[0]) / 10 ** n_dec
    return (n_dec, base)


def trade_round(price, n_dec=10, base=0.01):
    """
    Округляет по полученной базе (base) до n_dec чисел после запятой 
    """
    return round(base * round(float(price) / base), n_dec)


def calc_num_lots_for_buy(lot, cur_close, perc=0.2):
    """
    Расчет лота (суммы) под сделку
    :param lot: int - лотность инструмента
    :param cur_close: float - текущая цена инструмента
    :param perc: float - доля от всего портфеля, выделенная под покупку
    :return:
    """
    available_sum = get_available_balance()['rub']  # свободная сумма
    cur_cost_positions = get_current_positions().cur_pos_price.values.sum()  # текущие позиции
    account_cost = available_sum + cur_cost_positions  # оценочная стоимость портфеля

    sum_deal = min(account_cost * perc, available_sum)  # выделенная под покупку сумма
    min_deal = cur_close * lot  # минимальная сумма покупки
    num_lots_deal = sum_deal // (min_deal * 1.02)  # кол-во лотов для сделки

    return int(num_lots_deal)


def order(figi, lots, price, account_id, round_features, direction, order_type):
    """
    Выставляет ордер на покупку/продажу по лимитной/рыночной ценам
    :param figi: str - индентификатор инстумента
    :param lots: int - кол-во лотов для покупки
    :param price: float - цена ордера
    :param account_id: str - номер счета
    :param round_features: (int, float)- свойства для округления цен
    :param direction: str - направление заявки (покупка/продажа)
    :param order_type: str - тип заявки (по рыночной/лимитной цене)
    :return: request from client.orders.post_order
    """
    price_quotation = money_to_val_r(trade_round(price, *round_features))

    if direction == 'buy':
        direction_order = OrderDirection.ORDER_DIRECTION_BUY
    elif direction == 'sell':
        direction_order = OrderDirection.ORDER_DIRECTION_SELL

    if order_type == 'market':
        ord_type = schemas.OrderType.ORDER_TYPE_MARKET
        price = None
    elif order_type == 'limit':
        ord_type = schemas.OrderType.ORDER_TYPE_LIMIT

    order_id = figi + '-' + datetime.utcnow().strftime('%d.%m %H:%M')

    with Client(TOKEN) as client:
        r = client.orders.post_order(
            figi=figi,
            quantity=lots,
            price=price_quotation,
            direction=direction_order,
            account_id=account_id,
            order_type=ord_type,
            order_id=order_id
        )

    print(r)


def stop_order(figi, lots, price, account_id, round_features, direction, order_type):
    """
    Выставляет ордер на покупку/продажу по stop_loss/take_profit
    :param figi: str - индентификатор инстумента
    :param lots: int - кол-во лотов для покупки
    :param price: float - цена ордера
    :param account_id: str - номер счета
    :param round_features: (int, float)- свойства для округления цен
    :param direction: str - направление заявки (покупка/продажа)
    :param order_type: order_type: str - тип заявки (stop_loss/take_profit)
    :return:
    """
    price_stop_acivation_quotation = money_to_val_r(
        trade_round(price, *round_features))  # Цена активации стоп-заявки
    price_quotation = money_to_val_r(trade_round(price * 0.97, *round_features))  # продавать по цене ниже стопа

    if direction == 'buy':
        direction_order = StopOrderDirection.STOP_ORDER_DIRECTION_BUY
    elif direction == 'sell':
        direction_order = StopOrderDirection.STOP_ORDER_DIRECTION_SELL

    if order_type == 'stop_loss':
        ord_type = StopOrderType.STOP_ORDER_TYPE_STOP_LOSS
    elif order_type == 'take_profit':
        ord_type = StopOrderType.STOP_ORDER_TYPE_TAKE_PROFIT

    exp_type = StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL

    print(figi, lots, price_quotation, price_stop_acivation_quotation, direction_order, account_id, exp_type, ord_type)

    with Client(TOKEN) as client:

        r = client.stop_orders.post_stop_order(
            figi=figi,
            quantity=lots,
            price=price_quotation,
            stop_price=price_stop_acivation_quotation,
            direction=direction_order,
            account_id=account_id,
            expiration_type=exp_type,
            stop_order_type=ord_type
        )
    print(r)


def save_yaml(to_yaml, file_name):
    """
    Сохраняет yaml-файл
    :param to_yaml:
    :param file_name:
    :return:
    """
    with open(f'{file_name}.yaml', 'w') as f:
        yaml.dump(to_yaml, f, default_flow_style=False)


def load_yaml(file_name):
    """
    Загружает yaml-файл
    :param file_name: str
    :return:  загруженный yaml-файл
    """
    with open(f'{file_name}.yaml') as f:
        params = yaml.safe_load(f)
    return params


def get_historical_info(figi, candle_interval=CandleInterval.CANDLE_INTERVAL_15_MIN, days=160):
    timezone = pytz.timezone("Europe/Moscow")
    hist = pd.DataFrame()

    with Client(TOKEN) as client:
        for candle in client.get_all_candles(
                figi=figi,
                from_=datetime.now() - timedelta(days=days),
                to=datetime.now(),
                interval=candle_interval,
        ):
            hist_dict = {'figi': [figi],
                         'open': [money_to_val(candle.open)],
                         'close': [money_to_val(candle.close)],
                         'high': [money_to_val(candle.high)],
                         'low': [money_to_val(candle.low)],
                         'value': [np.mean([money_to_val(candle.open), money_to_val(candle.close),
                                            money_to_val(candle.high), money_to_val(candle.low)]) * candle.volume],
                         'volume': [candle.volume],
                         'begin': [candle.time.astimezone(timezone).strftime('%Y-%m-%d %H:%M:%S')],
                         }

            hist = pd.concat((hist, pd.DataFrame.from_dict(hist_dict)), axis=0)

    hist = hist.sort_values(by='begin').drop_duplicates()

    return hist.reset_index(drop=True)


def get_main_stock_info(stocks, id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER, class_code='TQBR'):
    stock_info = pd.DataFrame()

    with Client(TOKEN) as client:
        for stock in stocks:
            ticker_info = client.instruments.share_by(id_type=id_type,
                                                      class_code=class_code,
                                                      id=stock)

            stock_dict = {'figi': [ticker_info.instrument.figi],
                          'ticker': [ticker_info.instrument.ticker],
                          'name': [ticker_info.instrument.name],
                          #                           'last_price': [np.nan],
                          'lot': [ticker_info.instrument.lot],
                          'currency': [ticker_info.instrument.currency],
                          'class_code': [ticker_info.instrument.class_code],
                          'country_of_risk': [ticker_info.instrument.country_of_risk],
                          'sector': [ticker_info.instrument.sector],
                          'exchange': [ticker_info.instrument.exchange],
                          'min_price_step': [ticker_info.instrument.min_price_increment],
                          'buy_available_flag': [int(ticker_info.instrument.buy_available_flag)],
                          'sell_available_flag': [int(ticker_info.instrument.sell_available_flag)],
                          'short_enabled_flag': [int(ticker_info.instrument.short_enabled_flag)],
                          'api_trade_available_flag': [int(ticker_info.instrument.api_trade_available_flag)],
                          }

            stock_info = pd.concat((stock_info, pd.DataFrame.from_dict(stock_dict)), axis=0)

    return stock_info.reset_index(drop=True)


def get_current_positions():
    """
    Получение информации по открытым позициям
    """

    with Client(TOKEN) as client:
        portfolio = client.operations.get_portfolio(account_id=main_account_id)

        curr_positions = pd.DataFrame([{
            'figi': p.figi,
            'instrument_type': p.instrument_type,
            'quantity': int(money_to_val(p.quantity)),
            'avg_price': money_to_val(p.average_position_price),
            'cur_pos_price': money_to_val(p.quantity) * money_to_val(p.average_position_price) + money_to_val(
                p.expected_yield),
            'expected_yield': money_to_val(p.expected_yield),
            'currency': p.average_position_price.currency,
        } for p in portfolio.positions])

        if curr_positions.shape[0] > 0:
            curr_positions['position_direction'] = curr_positions.quantity.apply(lambda x: 'long' if x > 0 else 'short')
        else:
            curr_positions = pd.DataFrame(columns=['figi', 'cur_pos_price'])

    return curr_positions


def get_available_balance():
    """
    Возвращает информацию по доступным денежным средствам
    Наименование валюты: сумма (Например {'rub': 11770.18})
    """
    with Client(TOKEN) as client:
        cur_bal = client.operations.get_positions(account_id=main_account_id).money

    balance = {}

    for bal in cur_bal:
        balance[bal.currency] = money_to_val(bal)
    return balance


def get_current_candle_1h(figi, candle_interval=CandleInterval.CANDLE_INTERVAL_HOUR):
    """
    Берем информацию по текущей свече для конкретной бумаги, 
    для принятия окончательного решения на открытие /закрытие позиции 
    или установки новых take_profit / stop_loss
    """
    curr_candle = None
    timezone = pytz.timezone("Europe/Moscow")

    with Client(TOKEN) as client:
        for candle in client.get_all_candles(
                figi=figi,
                from_=datetime.now() - timedelta(hours=1),
                to=datetime.now(),
                interval=candle_interval,
        ):
            curr_candle = {'figi': figi,
                           'open': money_to_val(candle.open),
                           'close': money_to_val(candle.close),
                           'high': money_to_val(candle.high),
                           'low': money_to_val(candle.low),
                           'begin': candle.time.astimezone(timezone).strftime('%Y-%m-%d %H:%M:%S')
                           }
            # проверка на соответствие данных последнему часу
            # cur_hour = datetime.now().replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
            # assert curr_candle['begin'] == cur_hour, 'The last time of the candle is different from the current value'

    if not curr_candle:
        raise RuntimeError('func: get_current_candle_1h - Current candle does not exist!')

    return curr_candle


def get_current_candle_15m(figi, candle_interval=CandleInterval.CANDLE_INTERVAL_15_MIN):
    """
    Берем информацию по текущей свече для конкретной бумаги, 
    для принятия окончательного решения на открытие /закрытие позиции 
    или установки новых take_profit / stop_loss
    """
    curr_candle = None
    timezone = pytz.timezone("Europe/Moscow")

    with Client(TOKEN) as client:
        for candle in client.get_all_candles(
                figi=figi,
                from_=datetime.now() - timedelta(minutes=15),
                to=datetime.now(),
                interval=candle_interval,
        ):
            curr_candle = {'figi': figi,
                           'open': money_to_val(candle.open),
                           'close': money_to_val(candle.close),
                           'high': money_to_val(candle.high),
                           'low': money_to_val(candle.low),
                           'begin': candle.time.astimezone(timezone).strftime('%Y-%m-%d %H:%M:%S')
                           }
    if not curr_candle:
        raise RuntimeError('func: get_current_candle_15m - Current candle does not exist!')

    return curr_candle


def ma_indicator(data, ma_fast=12, ma_long=24):
    """
    Add Moving Average indicators
    :param data: pd.DataFrame
    :param ma_fast: fast MA interval
    :param ma_long: slow MA interval
    :return: pd.DataFrame
    """
    data[f'close_ma_fast'] = data['close'].rolling(window=ma_fast).mean()
    data[f'close_ma_long'] = data['close'].rolling(window=ma_long).mean()
    data['to_buy'] = np.where(data.close_ma_fast > data.close_ma_long, 1, 0)
    data['last_direction'] = data['to_buy'].shift(+1)
    data['signal'] = np.where(data.to_buy != data.last_direction, 1, 0)
    return data


def macd_indicator(data, macd_min, macd_max, macd_signal):
    """
    Add MACD indicators
    :param data: pd.DataFrame
    :param macd_min: fast MACD interval
    :param macd_max: slow MACD interval
    :param macd_signal: signal MACD interval
    :return: pd.DataFrame
    """
    data['macd'], data['macdsignal'], data['macdhist'] = talib.MACD(data.close,
                                                                    fastperiod=macd_min,
                                                                    slowperiod=macd_max,
                                                                    signalperiod=macd_signal)
    data['macd_buy'] = np.where(data.macd > data.macdsignal, 1, 0)
    data['macd_last_direction'] = data['macd_buy'].shift(+1)
    data['macd_signal'] = np.where(data.macd_buy != data.macd_last_direction, 1, 0)

    return data
