import ti_functional as tif

def ma_trading_strategy(tick, account_id, stock_info, tf='15m'):
    # берем по тикеру информацию: фиги, лотность, доступность шортов
    figi, lot, short, quotation_round = stock_info[stock_info.ticker == tick][['figi', 'lot',
                                                                               'short_enabled_flag',
                                                                               'min_price_step']].values[0]

    # лучшие параметры для данного тикера
    params = tif.load_yaml('best_ma_params')
    min_ma, max_ma, stop_loss_lvl = params[figi]['min_ma'], params[figi]['max_ma'], params[figi]['stop_loss']

    # для 15м парсим свечи за последние 10 дней (только для возможности построения МА), убирая последнюю строку
    data = tif.get_historical_info(figi, days=10)[:-1]
    data = tif.ma_indicator(data, ma_fast=min_ma, ma_long=max_ma)  # добавляем МА

    print(f'size: {data.shape[0]}', end=' -> ')
    print(f'min/max MA:{min_ma}/{max_ma}, stop_loss: {stop_loss_lvl}', end=' -> ')

    # открытые позиции
    open_positions = tif.load_yaml('deals_params')
    cur_pos = tif.get_current_positions()

    # если позиция была открыта и до сих пор открыта, то берем по ней информацию
    if tick in open_positions and tick in cur_pos.figi.values:
        pos_info = open_positions[tick]
        cnt_lot, buy_price, _stop_loss_ = pos_info['lot'], pos_info['buy_price'], pos_info['stop_loss']
    elif tick in open_positions:
        del open_positions[tick]
        cnt_lot, buy_price, _stop_loss_ = 0, 0, 0
        # можно сюда добавить функцию с поиском цены закрытия и добавление данных в историю сделок
    else:
        cnt_lot, buy_price, _stop_loss_ = 0, 0, 0

    # информация последней свечки
    last_candle = data.iloc[-1]
    close, to_buy, signal = last_candle.close, last_candle.to_buy, last_candle.signal

    # текушая свеча
    cur_candle = tif.get_current_candle_15m(figi)
    cur_close = cur_candle['close']

    # свойства для округление цен
    round_features = tif.price_features(quotation_round.nano)

    #################################################################################################
    print(f'to_buy: {to_buy}, signal: {signal}, cnt_lot: {cnt_lot}')

    if to_buy == 1 and signal == 1 and cnt_lot == 0:

        lots_for_buy = tif.calc_num_lots_for_buy(lot, cur_close)

        buy_price = cur_close * 1.0005
        stop_loss = cur_close * (1 - stop_loss_lvl)
        take_profit = cur_close * (1 + 0.05)

        if lots_for_buy > 0:
            # лимитная заявка с уровнем покупки не выше тек.цена+погрешность
            tif.order(figi, lots_for_buy, buy_price, account_id, round_features,
                            direction='buy', order_type='limit')
            #         tif.order(figi, lots_for_buy, buy_price, account_id, round_features,
            #             direction='buy', order_type='market')
            tif.stop_order(figi, lots_for_buy, stop_loss, account_id, round_features,
                          direction='sell', order_type='stop_loss')
            tif.stop_order(figi, lots_for_buy, take_profit, account_id, round_features,
                          direction='sell', order_type='take_profit')

            open_positions[tick] = {'lots': lots_for_buy, 'price': buy_price,
                                    'stop_loss': stop_loss, 'take_profit': take_profit}
            print(f'Position is open: {open_positions[tick]}')
        else:
            print(f'Недостаточно средств для открытия позиции')

    elif to_buy == 1 and cnt_lot >= 1:
        new_stop_loss = cur_close * (1 - stop_loss_lvl)
        new_take_profit = cur_close * (1 + 0.03)

        if _stop_loss_ < new_stop_loss:
            tif.stop_order(figi, cnt_lot, new_stop_loss, account_id, round_features, direction='sell',
                       order_type='stop_loss')
            open_positions[tick]['stop_loss'] = new_stop_loss
            #             tif.stop_order(figi, cnt_lot, new_take_profit, account_id, round_features, direction='sell', order_type='take_profit')
            #             tif.open_positions[tick]['taset_take_profitke_profit'] = new_take_profit

            print(f'Cur.price: {cur_close}, stop_loss changed: {old_stop_loss} --> {new_stop_loss}')

    elif to_buy == 0 and cnt_lot > 0:
        tif.order(figi, cnt_lot, buy_price, account_id, round_features, direction='sell', order_type='market')
        del open_positions[tick]
        print(
            f'Closed position: buy: {buy_price}, sell: {cur_close}, profit: {round((cur_close - buy_price) / buy_price, 2)}%')

    #     elif cur_cnt==0: # to_buy==0 and cnt_lot==0:
    #         continue

    #     else:
    #         break

    # сохраняем изменения активным по сделкам
    tif.save_yaml(open_positions, 'deals_params')

