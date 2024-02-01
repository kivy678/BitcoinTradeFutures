# -*- coding:utf-8 -*-

#############################################################################

import logging

from env import BINANCE_ACCESS, BINANCE_SECRET

from binance.um_futures import UMFutures
from binance.lib.utils import config_logging
from binance.error import ClientError

import pprint

#############################################################################

config_logging(logging, logging.DEBUG)

#############################################################################


if __name__ == '__main__':

    print('Main start')

    um_futures_client = UMFutures(key=BINANCE_ACCESS, secret=BINANCE_SECRET)

    try:

        # 지갑 정보 가져오기
        resp = um_futures_client.balance(recvWindow=6000)

        for d in resp:
            print(d['asset'], d['balance'])


    except ClientError as error:
        logging.error(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


    print('Main End')
