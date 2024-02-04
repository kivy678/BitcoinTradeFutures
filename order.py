# -*- coding:utf-8 -*-

#############################################################################

import logging

from env import BINANCE_ACCESS, BINANCE_SECRET

from binance.um_futures import UMFutures
from binance.lib.utils import config_logging
from binance.error import ClientError

import pprint

#############################################################################

#config_logging(logging, logging.DEBUG)

#############################################################################


if __name__ == '__main__':

    print('Main start')

    um_futures_client = UMFutures(key=BINANCE_ACCESS, secret=BINANCE_SECRET)

    try:

        # 오픈 포지션
        params = {
            'symbol': 'ETHUSDT',
            'side': 'BUY',
            'positionSide': 'LONG',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': 0.009,
            'price': 2305
        }

        resp = um_futures_client.new_order(**params)
        pprint.pprint(resp)


        # 오더 확인하기
        '''
        resp = um_futures_client.query_order(
            symbol="ETHUSDT", orderId=1111111111, recvWindow=2000
        )
        pprint.pprint(resp)
        '''

        '''
        # 목표가
        params = {
            'symbol': 'ETHUSDT',
            'side': 'SELL',
            'positionSide': 'LONG',
            'type': 'TAKE_PROFIT_MARKET',
            'timeInForce': 'GTC',
            'quantity': 0.009,
            'stopPrice': 2350,
        }
        resp = um_futures_client.new_order(**params)
        pprint.pprint(resp)

        # 손절가
        params = {
            'symbol': 'ETHUSDT',
            'side': 'SELL',
            'positionSide': 'LONG',
            'type': 'STOP_MARKET',
            'timeInForce': 'GTC',
            'quantity': 0.009,
            'stopPrice': 2290
        }

        resp = um_futures_client.new_order(**params)
        pprint.pprint(resp)
        '''



    except ClientError as error:
        logging.error(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


    print('Main End')

