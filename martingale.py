# -*- coding:utf-8 -*-

#############################################################################

import random
from functools import wraps

import math
import time

from decimal import Decimal, getcontext, ROUND_UP, ROUND_DOWN

import logging

from env import BINANCE_ACCESS, BINANCE_SECRET

from binance.um_futures import UMFutures
from binance.lib.utils import config_logging
from binance.error import ClientError

import pprint

#############################################################################

#config_logging(logging, logging.DEBUG)

class ReBuyOrder(Exception): pass

#############################################################################


SYMBOL          = 'ETHUSDT'
MAKER_FEE       = Decimal('0.0005')

TICK_SIZE       = None
STEP_SIZE       = None
MIN_NOTIONAL    = None
ALPHA           = 2
PERCENT         = 6


# 심볼 정보를 가져온다.
def get_symbol_info(clt, symbol):
    resp = clt.exchange_info().get('data')
    #pprint.pprint(resp['rateLimits'])

    for symbol in resp['symbols']:
        if symbol['pair'] == 'ETHUSDT' and symbol['contractType'] == 'PERPETUAL':
            for types in symbol.get('filters'):
                if types.get('filterType') == 'PRICE_FILTER':
                    global TICK_SIZE
                    TICK_SIZE   = Decimal(types.get('tickSize'))

                elif types.get('filterType') == 'MARKET_LOT_SIZE':
                    global STEP_SIZE
                    STEP_SIZE   = Decimal(types.get('stepSize'))

                elif types.get('filterType') == 'MIN_NOTIONAL':
                    global MIN_NOTIONAL
                    MIN_NOTIONAL = Decimal(types.get('notional'))

    #print(f'TICK_SIZE:{TICK_SIZE}, STEP_SIZE:{STEP_SIZE}, MIN_NOTIONAL:{MIN_NOTIONAL}')


# 현재 코인의 가격을 가져온다.
def get_current_price(clt, symbol):
    params = {
        "symbol": symbol,
    }
    resp = clt.query("/fapi/v2/ticker/price", params).get('data')
    return Decimal(resp.get('price'))


# 포지션 오픈
def open_position(clt, symbol, position, side, _type, quantity, price):
    params = {
        'symbol': symbol,
        'side': side,
        'positionSide': position,
        'type': _type,
        'timeInForce': 'GTC',
        'quantity': quantity,
        'price': price
    }

    resp            = clt.new_order(**params)

    weight          = resp.get('limit_usage').get('x-mbx-used-weight-1m')
    order_count_10s = resp.get('limit_usage').get('x-mbx-order-count-10s')
    order_count_1m  = resp.get('limit_usage').get('x-mbx-order-count-1m')

    #print(f'open_position weight-1m:{weight}, order_count_10s:{order_count_10s}, order_count_1m:{order_count_1m}')    

    return resp.get('data').get('orderId')


# 포지션 클로즈
def close_position(clt, symbol, position, side, _type, quantity, price, stopPrice):
    params = {
        'symbol': symbol,
        'side': side,
        'positionSide': position,
        'type': _type,
        'timeInForce': 'GTC',
        'quantity': quantity,
        'price': price,
        'stopPrice': stopPrice
    }

    resp            = clt.new_order(**params)

    weight          = resp.get('limit_usage').get('x-mbx-used-weight-1m')
    order_count_10s = resp.get('limit_usage').get('x-mbx-order-count-10s')
    order_count_1m  = resp.get('limit_usage').get('x-mbx-order-count-1m')

    #print(f'open_position weight-1m:{weight}, order_count_10s:{order_count_10s}, order_count_1m:{order_count_1m}')    

    return resp.get('data').get('orderId')


# 주문 상태 확인
def is_filled_order(clt, symbol, order_id):
        resp = clt.query_order(symbol=symbol, orderId=order_id, recvWindow=2000)
        weight = resp.get('limit_usage').get('x-mbx-used-weight-1m')
        #print(f'is_filled_order weight-1m:{weight}')

        resp = resp.get('data')
        if resp.get('status') == 'FILLED':
            return (round_up_decimal(Decimal(resp.get('avgPrice')), Decimal('0.00000001')),
                    round_up_decimal(Decimal(resp.get('cumQuote')), Decimal('0.00000001'))
                    )            # 체결된 가격과 변환된 USDT 가격을 반환한다.
        else:
            return (None, None)


def cancle_order(clt, symbol, order_id):
    clt.cancel_order(symbol=symbol, orderId=order_id, recvWindow=2000)


# 소수점 자리수를 구한다.
def get_decimal_value(value):
    number = Decimal(str(value))
    return abs(number.as_tuple().exponent)


# 자리수에 맞게 올림
def round_up_decimal(number, exp):
    return number.quantize(exp, rounding=ROUND_UP)


# 자리수에 맞게 버림
def round_down_decimal(number, exp):
    return number.quantize(exp, rounding=ROUND_DOWN)


# 현재 가격 기준으로 오픈할 포지션 가격 구하기
def get_open_price(clt, symbol, position, size, alpha):
    if position == 'LONG':
        current_price   = get_current_price(clt, SYMBOL) - size * alpha
    else:
        current_price   = get_current_price(clt, SYMBOL) + size * alpha

    open_price      = round_up_decimal(current_price, size)

    return open_price


# 최소 구매 코인 수량을 구한다.
def get_min_quantity(price, usdt, size):
    return round_up_decimal(usdt / price, size)


# LOT에 의한 올림을 하기 때문에 USDT 값 또한 조금씩 차이가 나기 때문에 정확한 USDT값을 구한다.
def get_accurate_usdt(price, quantity):
    return round_down_decimal(price * quantity, Decimal('0.00000001'))


# FEE 를 구한다.
def get_fee(usdt, fee):
    return round_down_decimal(usdt * fee, Decimal('0.00000001'))



# 손해보지 않는 PT/SL 사이즈 구해서 실제 차익 구하기
def get_postion_gap(price, tp_usdt, quantity, size):
    tp_point        = round_up_decimal(tp_usdt / quantity, size)
    price_tp_diff   = round_up_decimal(tp_point - price, size)
    return (tp_point, price_tp_diff)


# 손절가 계산한다.
def get_postion_sl(price, diff, size):
    return round_up_decimal(price - diff, size)


def random_position(per):
    if random.randint(1, 10) <= per:
        return {'position': 'LONG', 'open':'BUY', 'close': 'SELL'}
    else:
        return {'position':'SHORT', 'open':'SELL', 'close': 'BUY'}



if __name__ == '__main__':

    print('Main start')

    loss_amount = Decimal('0')
    clt = UMFutures(key=BINANCE_ACCESS, secret=BINANCE_SECRET, show_limit_usage=True)



    try:
         # 코인의 정보를 가져온다.
        get_symbol_info(clt, SYMBOL)   

        while True:
            try:

                random_position_dict = random_position(PERCENT)

                # 오픈할 포지션을 계산하여 최소 구매 코인수량과 정확한 USDT 를 구하고 수수료를 계산
                open_price          = get_open_price(clt, SYMBOL, random_position_dict['position'], TICK_SIZE, ALPHA)
                print(f'{random_position_dict["position"]} open_price:', open_price)

                coin_quantity       = get_min_quantity(open_price, MIN_NOTIONAL, STEP_SIZE)
                min_usdt            = get_accurate_usdt(open_price, coin_quantity)
                fee_buy             = get_fee(min_usdt, MAKER_FEE)
                
                # 전부 더하여 포지션 갭을 구한다.
                tp_usdt = min_usdt + fee_buy + loss_amount
                tp_point, price_tp_diff = get_postion_gap(open_price, tp_usdt, coin_quantity, TICK_SIZE)


                # 클로징시 수수료를 계산한다. 현재 구하는 포인트 지점과 최종적으로 구하는 포인트 지점이 다르기 때문에 수수료가 더 나올수 있다.
                fee_sell            = get_fee(tp_usdt, MAKER_FEE)


                # 매수/매도 포지션을 모두 합쳐서 최종 갭을 구한다.
                sum_usdt            = tp_usdt + fee_sell
                tp_point, price_tp_diff = get_postion_gap(open_price, sum_usdt, coin_quantity, TICK_SIZE)
                sl_point            = get_postion_sl(open_price, price_tp_diff, TICK_SIZE)
                order_id            = open_position(clt, SYMBOL, random_position_dict['position'], random_position_dict['open'], 'LIMIT', coin_quantity, open_price)

                cnt = 0
                while True:
                    # 너무 오래걸리면 취소 후 다시
                    avgPrice, quantity_usdt = is_filled_order(clt, SYMBOL, order_id)
                    if cnt == 5 and (avgPrice is None and quantity_usdt is None):
                        cancle_order(clt, SYMBOL, order_id)
                        raise ReBuyOrder

                    elif avgPrice is None and quantity_usdt is None:
                        time.sleep(1)
                        cnt += 1
                        continue
                    
                    else:
                        print(f'Open Position Filled: {order_id}, loss_amount:{loss_amount}')
                        break

                if random_position_dict['position'] == 'SHORT':
                    tmp = tp_point; tp_point = sl_point; sl_point = tmp

                tp_order_id = close_position(clt, SYMBOL, random_position_dict['position'], random_position_dict['close'], 'TAKE_PROFIT', coin_quantity, price=tp_point, stopPrice=tp_point)
                sl_order_id = close_position(clt, SYMBOL, random_position_dict['position'], random_position_dict['close'], 'STOP',        coin_quantity, price=sl_point, stopPrice=sl_point)

                while True:
                    tp_avgPrice, tp_quantity_usdt = is_filled_order(clt, SYMBOL, tp_order_id)
                    sl_avgPrice, sl_quantity_usdt = is_filled_order(clt, SYMBOL, sl_order_id)

                    if (tp_avgPrice is not None and tp_quantity_usdt is not None):
                        real_fee_sell            = get_fee(tp_quantity_usdt, MAKER_FEE)
                        get_usdt = tp_quantity_usdt - quantity_usdt - (fee_buy + real_fee_sell)
                        loss_amount = 0
                        print(f'tp_avgPrice:{tp_avgPrice}, quantity_usdt:{quantity_usdt}, tp_quantity_usdt:{tp_quantity_usdt}, get_usdt:{get_usdt}, loss_amount:{loss_amount}')

                        cancle_order(clt, SYMBOL, sl_order_id)
                        
                        break

                    elif (sl_avgPrice is not None and sl_quantity_usdt is not None):
                        real_fee_sell            = get_fee(sl_quantity_usdt, MAKER_FEE)
                        loss_usdt = quantity_usdt - sl_quantity_usdt + (fee_buy + real_fee_sell)
                        loss_amount += loss_usdt
                        print(f'sl_avgPrice:{sl_avgPrice}, quantity_usdt:{quantity_usdt}, sl_quantity_usdt:{sl_quantity_usdt}, loss_usdt:{loss_usdt}, loss_amount:{loss_amount}')

                        cancle_order(clt, SYMBOL, tp_order_id)
                        
                        break

                    else:
                        time.sleep(1)
                        continue
        

            except ReBuyOrder:
                print('ReBuyOrder')
                continue

    except ClientError as error:
        logging.error(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


    print('Main End')
