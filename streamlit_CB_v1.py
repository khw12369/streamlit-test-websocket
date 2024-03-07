import streamlit as st
import asyncio
import websockets
import json
import pandas as pd
from datetime import datetime
from collections import deque
import ccxt
from binance import AsyncClient, BinanceSocketManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def connect_and_subscribe_v3(symbol, df):
    recent_prices = {symbol: deque(maxlen=5) for symbol in tickerlist}

    while True:
        try:
            async with websockets.connect("wss://fstream.binance.com/ws") as websocket:
                subscribe_message = {
                    "method": "SUBSCRIBE",
                    "params": [f"{symbol}@kline_1m"],
                    "id": 1
                }
                await websocket.send(json.dumps(subscribe_message))

                last_ping_time = datetime.now()

                while True:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=180)  # 3분 동안 메시지 대기
                        data = json.loads(response)
                        if data.get('k'):
                            symbol = data['s'][:-4] + '/' + data['s'][-4:]
                            current_price = data['k']['c']
                            timestamp = data['E'] if data['E'] else None
                            time = datetime.fromtimestamp(timestamp / 1000.0).strftime('%m-%d %H:%M:%S')
                            df.loc[symbol] = [symbol, current_price, None, None, None, None, None, None, None,
                                              time]  # 데이터 업데이트

                            previous_amt = float(df.at[symbol, 'Position Amt']) if df.at[symbol, 'Position Amt'] else 0
                            avg_price = float(df.at[symbol, 'Avg.Price']) if df.at[symbol, 'Avg.Price'] else 0
                            longcheck = df.at[symbol, 'L.Check'] if df.at[symbol, 'L.Check'] else "F"
                            shortcheck = df.at[symbol, 'S.Check'] if df.at[symbol, 'S.Check'] else "F"
                            ma = df.at[symbol, '5MA'] if df.at[symbol, '5MA'] else None
                            long_losscut = df.at[symbol, "L.losscut_price"] if df.at[
                                symbol, "L.losscut_price"] else None
                            short_losscut = df.at[symbol, "S.losscut_price"] if df.at[
                                symbol, "S.losscut_price"] else None

                            df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck,
                                              long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                            placeholder.table(df)

                            if str(data['k']['x']) == 'True':
                                recent_prices[symbol].append(float(data['k']['c']))
                                longcheck = "F"
                                shortcheck = "F"

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck,
                                                  long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)

                            ma = average_last_period(recent_prices[symbol], float(data['k']['c']), 5)

                            if ma is not None:
                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck,
                                                  long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)

                            if ma is not None and df.at[symbol, 'L.Check'] != 'T' and float(current_price) >= float(
                                    ma) * (1 + 0.035):
                                longcheck = "T"

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck,
                                                  shortcheck]  # 데이터 업데이트
                                placeholder.table(df)

                            if ma is not None and df.at[symbol, 'S.Check'] != 'T' and float(current_price) <= float(
                                    ma) * (1 - 0.035):
                                shortcheck = "T"

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck,
                                                  long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)

                            if avg_price != 0 and float(previous_amt) > 0:
                                long_losscut = float(avg_price) + float(usdt_balance) * 0.02 / float(previous_amt)

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck,
                                                  long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)

                            if avg_price != 0 and previous_amt < 0:
                                short_losscut = float(avg_price) + float(usdt_balance) * 0.02 / float(previous_amt)

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck,
                                                  long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)

                            if float(previous_amt) == 0 and st.session_state.button_clicked:
                                if ma is not None and float(current_price) <= float(ma) * (1 + 0.03) and str(
                                        longcheck) == "T":
                                    available_amt = round(float(usdt_balance) / float(current_price), 3)
                                    short_open(binance_futures, symbol, available_amt)
                                    rewrite_cash()

                                if ma is not None and float(current_price) <= float(ma) * (1 - 0.03) and str(
                                        shortcheck) == "T":
                                    available_amt = round(float(usdt_balance) / float(current_price), 3)
                                    long_open(binance_futures, symbol, available_amt)
                                    rewrite_cash()

                            if previous_amt > 0 and st.session_state.button_clicked:
                                if long_losscut is not None and float(current_price) <= float(long_losscut):
                                    long_close(binance_futures, symbol, previous_amt)
                                    rewrite_cash()
                                elif avg_price != 0 and float(current_price) / float(avg_price) - 1 >= 0.01:
                                    long_close(binance_futures, symbol, previous_amt)
                                    rewrite_cash()

                            if previous_amt < 0 and st.session_state.button_clicked:
                                if short_losscut is not None and float(current_price) >= float(short_losscut):
                                    short_close(binance_futures, symbol, previous_amt)
                                    rewrite_cash()
                                elif avg_price != 0 and float(avg_price) / float(current_price) - 1 >= 0.01:
                                    short_close(binance_futures, symbol, previous_amt)
                                    rewrite_cash()

                        now = datetime.now()
                        if (now - last_ping_time).total_seconds() >= 180:
                            await websocket.ping()
                            last_ping_time = now

                        if not websocket.open:
                            df.loc[symbol] = [None, None, None, None, None, None, None, None, None, None]  # 데이터 업데이트
                            placeholder.table(df)

                    except asyncio.TimeoutError:
                        # 3분간 메시지가 없으면 핑을 보내 연결을 유지합니다.
                        await websocket.ping()
                        last_ping_time = datetime.now()

        except websockets.exceptions.ConnectionClosed:
            print(f"{symbol} 연결이 끊어짐. 재연결 시도...")
            await asyncio.sleep(1)  # 재연결 전에 잠시 대기 후 다시 시도

        await asyncio.sleep(1)  # 연결 시도 사이에 잠시 대기

async def connect_and_subscribe_v2(symbol, df):
    recent_prices = {symbol: deque(maxlen=5) for symbol in df.columns}

    while True:
        try:
            async with websockets.connect("wss://fstream.binance.com/ws", ping_interval=60, ping_timeout=10) as websocket:
                subscribe_message = {
                    "method": "SUBSCRIBE",
                    "params": [f"{symbol}@kline_1m"],
                    "id": 1
                }
                await websocket.send(json.dumps(subscribe_message))
                await asyncio.sleep(0.5)  # 0.5초 간격으로 구독

                while True:
                    response = await websocket.recv()
                    data = json.loads(response)
                    if data.get('k'):
                        symbol = data['s'][:-4] + '/' + data['s'][-4:]
                        current_price = data['k']['c']
                        timestamp = data['E'] if data['E'] else None
                        time = datetime.fromtimestamp(timestamp / 1000.0).strftime('%m-%d %H:%M:%S')
                        df.loc[symbol] = [symbol, current_price, None, None, None, None, None, None, None, time]  # 데이터 업데이트

                        previous_amt = float(df.at[symbol, 'Position Amt']) if df.at[symbol, 'Position Amt'] else 0
                        avg_price = float(df.at[symbol, 'Avg.Price']) if df.at[symbol, 'Avg.Price'] else 0
                        longcheck = df.at[symbol, 'L.Check'] if df.at[symbol, 'L.Check'] else "F"
                        shortcheck = df.at[symbol, 'S.Check'] if df.at[symbol, 'S.Check'] else "F"
                        ma = df.at[symbol, '5MA'] if df.at[symbol, '5MA'] else None
                        long_losscut = df.at[symbol, "L.losscut_price"] if df.at[symbol, "L.losscut_price"] else None
                        short_losscut = df.at[symbol, "S.losscut_price"] if df.at[symbol, "S.losscut_price"] else None

                        df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                        placeholder.table(df)

                        if str(data['k']['x']) == 'True':
                            recent_prices[symbol].append(float(data['k']['c']))
                            longcheck = "F"
                            shortcheck = "F"

                            df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                            placeholder.table(df)

                        ma = average_last_period(recent_prices[symbol], float(data['k']['c']), 5)

                        if ma is not None:
                            df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                            placeholder.table(df)

                        if ma is not None and df.at[symbol, 'L.Check'] != 'T' and float(current_price) >= float(ma) * (1 + 0.035):
                            longcheck = "T"

                            df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, shortcheck]  # 데이터 업데이트
                            placeholder.table(df)

                        if ma is not None and df.at[symbol, 'S.Check'] != 'T' and float(current_price) <= float(ma) * (1 - 0.035):
                            shortcheck = "T"

                            df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                            placeholder.table(df)

                        if avg_price != 0 and float(previous_amt) > 0:
                            long_losscut = float(avg_price) + float(usdt_balance) * 0.02 / float(previous_amt)

                            df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                            placeholder.table(df)

                        if avg_price != 0 and previous_amt < 0:
                            short_losscut = float(avg_price) + float(usdt_balance) * 0.02 / float(previous_amt)

                            df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                            placeholder.table(df)

                        if float(previous_amt) == 0 and st.session_state.button_clicked:
                            if ma is not None and float(current_price) <= float(ma) * (1 + 0.03) and str(longcheck) == "T":
                                available_amt = round(float(usdt_balance) / float(current_price), 3)
                                short_open(binance_futures, symbol, available_amt)
                                rewrite_cash()

                            if ma is not None and float(current_price) <= float(ma) * (1 - 0.03) and str(shortcheck) == "T":
                                available_amt = round(float(usdt_balance) / float(current_price), 3)
                                long_open(binance_futures, symbol, available_amt)
                                rewrite_cash()

                        if previous_amt > 0  and st.session_state.button_clicked:
                            if long_losscut is not None and float(current_price) <= float(long_losscut):
                                long_close(binance_futures, symbol, previous_amt)
                                rewrite_cash()
                            elif avg_price != 0 and float(current_price) / float(avg_price) - 1 >= 0.01:
                                long_close(binance_futures, symbol, previous_amt)
                                rewrite_cash()

                        if previous_amt < 0  and st.session_state.button_clicked:
                            if short_losscut is not None and float(current_price) >= float(short_losscut):
                                short_close(binance_futures, symbol, previous_amt)
                                rewrite_cash()
                            elif avg_price != 0 and float(avg_price) / float(current_price) - 1 >= 0.01:
                                short_close(binance_futures, symbol, previous_amt)
                                rewrite_cash()
                    # 데이터 처리 로직
                    # 데이터가 유효할 경우의 처리 로직

                # 웹소켓 연결이 닫혀있으면 재연결 시도
                if not websocket.open:
                    print(f"{symbol} 연결이 끊어짐, 재연결 시도...")
                    break  # 내부 while 루프를 빠져나와 외부 while 루프에서 재연결 시도

        except websockets.exceptions.ConnectionClosed as e:
            print(f"{symbol} 연결이 끊어짐: {e}, 재연결 시도...")
        except Exception as e:
            print(f"{symbol}에서 예외 발생: {e}, 재연결 시도...")

        await asyncio.sleep(1)  # 재연결 전에 잠시 대기

async def connect_and_subscribe(symbol, df):
    recent_prices = {symbol: deque(maxlen=5) for symbol in tickerlist}
    close_for_reversal_turtle = {symbol: deque(maxlen=20) for symbol in tickerlist}

    global usdt_balance
    while True:
        await asyncio.sleep(1)
        try:
            async with websockets.connect("wss://fstream.binance.com/ws") as websocket:
                subscribe_message = {
                    "method": "SUBSCRIBE",
                    "params": [f"{symbol}@kline_1m"],
                    "id": 1
                }
                await websocket.send(json.dumps(subscribe_message))
                await asyncio.sleep(0.5)  # 0.5초 간격으로 구독

                while True:

                    response = await websocket.recv()
                    if isinstance(response, str):
                        data = json.loads(response)
                        #logger.info(f"Received data: {data}")

                        # 데이터 처리 로직을 여기에 구현하세요.
                        if data.get('k'):
                            symbol = data['s'][:-4] + '/' + data['s'][-4:]
                            current_price = data['k']['c']
                            timestamp = data['E'] if data['E'] else None
                            time = datetime.fromtimestamp(timestamp / 1000.0).strftime('%m-%d %H:%M:%S')
                            df.loc[symbol] = [symbol, current_price, None, None, None, None, None, None, None,time]  # 데이터 업데이트
                            df['Cur.Price'] = df['Cur.Price'].astype(str)

                            previous_amt = float(df.at[symbol, 'Position Amt']) if df.at[symbol, 'Position Amt'] else 0
                            avg_price = float(df.at[symbol, 'Avg.Price']) if df.at[symbol, 'Avg.Price'] else 0
                            longcheck = df.at[symbol, 'L.Check'] if df.at[symbol, 'L.Check'] else "F"
                            shortcheck = df.at[symbol, 'S.Check'] if df.at[symbol, 'S.Check'] else "F"
                            ma = df.at[symbol, '5MA'] if df.at[symbol, '5MA'] else None
                            long_losscut = df.at[symbol, "L.losscut_price"] if df.at[
                                symbol, "L.losscut_price"] else None
                            short_losscut = df.at[symbol, "S.losscut_price"] if df.at[
                                symbol, "S.losscut_price"] else None

                            df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                            placeholder.table(df)

                            if str(data['k']['x']) == 'True':
                                recent_prices[symbol].append(float(data['k']['c']))
                                close_for_reversal_turtle[symbol].append(float(data['k']['c']))
                                longcheck = "F"
                                shortcheck = "F"

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)

                            ma = average_last_period(recent_prices[symbol], float(data['k']['c']), 5)
                            soup_turtle_long = find_two_largest(close_for_reversal_turtle[symbol], 20)
                            soup_turtle_short = find_two_smallest(close_for_reversal_turtle[symbol], 20)

                            if float(previous_amt) == 0:
                                if soup_turtle_long is not None and float(data['k']['c']) < soup_turtle_long[1]:
                                    available_amt = round(float(usdt_balance) / float(current_price), 3)
                                    short_open(binance_futures, symbol, available_amt)
                                    rewrite_cash()
                                    short_losscut = soup_turtle_long[0]

                                    df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                    placeholder.table(df)

                                if soup_turtle_short is not None and float(data['k']['c']) > soup_turtle_short[1]:
                                    available_amt = round(float(usdt_balance) / float(current_price), 3)
                                    long_open(binance_futures, symbol, available_amt)
                                    rewrite_cash()
                                    long_losscut = soup_turtle_short[0]

                                    df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                    placeholder.table(df)

                            if ma is not None:
                                if df.at[symbol, 'L.Check'] != 'T' and float(current_price) >= float(ma) * (1 + 0.035):
                                    longcheck = "T"

                                if df.at[symbol, 'S.Check'] != 'T' and float(current_price) <= float(ma) * (1 - 0.035):
                                    shortcheck = "T"

                                # 데이터 업데이트 부분을 모든 조건문이 끝난 후에 한 번만 실행
                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]
                                placeholder.table(df)

                            """
                            if avg_price != 0:
                                if float(previous_amt) > 0:
                                    long_losscut = float(avg_price) + float(usdt_balance) * 0.02 / float(previous_amt)

                                if previous_amt < 0:
                                    short_losscut = float(avg_price) + float(usdt_balance) * 0.02 / float(previous_amt)

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]
                                placeholder.table(df)
                            """

                            '''
                            if ma is not None:
                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)

                            if ma is not None and df.at[symbol, 'L.Check'] != 'T' and float(current_price) >= float(
                                    ma) * (1 + 0.035):
                                longcheck = "T"

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)

                            if ma is not None and df.at[symbol, 'S.Check'] != 'T' and float(current_price) <= float(
                                    ma) * (1 - 0.035):
                                shortcheck = "T"

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)

                            if avg_price != 0 and float(previous_amt) > 0:
                                long_losscut = float(avg_price) + float(usdt_balance) * 0.02 / float(previous_amt)

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)

                            if avg_price != 0 and previous_amt < 0:
                                short_losscut = float(avg_price) + float(usdt_balance) * 0.02 / float(previous_amt)

                                df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                                placeholder.table(df)
                            '''

                            '''
                            if float(previous_amt) == 0:
                                if ma is not None and float(current_price) <= float(ma) * (1 + 0.03) and str(longcheck) == "T":
                                    available_amt = round(float(usdt_balance) / float(current_price), 3)
                                    short_open(binance_futures, symbol, available_amt)
                                    rewrite_cash()

                                if ma is not None and float(current_price) <= float(ma) * (1 - 0.03) and str(
                                        shortcheck) == "T":
                                    available_amt = round(float(usdt_balance) / float(current_price), 3)
                                    long_open(binance_futures, symbol, available_amt)
                                    rewrite_cash()
                            '''

                            if float(previous_amt) > 0:
                                if long_losscut is not None and float(current_price) <= float(long_losscut):
                                    long_close(binance_futures, symbol, previous_amt)
                                    rewrite_cash()
                                elif avg_price != 0 and float(current_price) / float(avg_price) - 1 >= 0.025:
                                    long_close(binance_futures, symbol, previous_amt)
                                    rewrite_cash()

                            if float(previous_amt) < 0:
                                if short_losscut is not None and float(current_price) >= float(short_losscut):
                                    short_close(binance_futures, symbol, previous_amt)
                                    rewrite_cash()
                                elif avg_price != 0 and float(avg_price) / float(current_price) - 1 >= 0.025:
                                    short_close(binance_futures, symbol, previous_amt)
                                    rewrite_cash()

                    elif isinstance(response, bytes):
                        # 핑/퐁 메시지 처리
                        opcode = response[0] & 0x0f
                        if opcode == 0x9:  # 0x9는 핑 메시지의 오퍼레이션 코드
                            logger.info("Ping message received, sending Pong response.")
                            await websocket.pong(response[1:])  # 퐁 응답을 보냄

                    else:
                        df.loc[symbol] = [None, None, None, None, None, None, None, None, None, None]  # 데이터 업데이트
                        placeholder.table(df)
                        await asyncio.sleep(1)
                        break

                await asyncio.sleep(1)

        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"{symbol} connection closed: {e}, attempting to reconnect...")
            await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"{symbol} connection closed: {e}, attempting to reconnect...")
            await asyncio.sleep(10)

async def run_all_symbols(symbols, df):
    chunks = [symbols[i:i + 50] for i in range(0, len(symbols), 50)]

    chunk_tasks = []
    for chunk in chunks:
        async def run_chunk(chunk):
            tasks = [asyncio.create_task(connect_and_subscribe(symbol, df)) for symbol in chunk]
            await asyncio.gather(*tasks)

        # 각 청크에 대해 별도의 비동기 태스크 생성
        chunk_task = asyncio.create_task(run_chunk(chunk))
        chunk_tasks.append(chunk_task)

    # 모든 청크 태스크가 완료될 때까지 기다림
    await asyncio.gather(*chunk_tasks)

# 비동기적으로 웹소켓을 통해 데이터 수신
async def listen_to_websocket(symbols, df):
    recent_prices = {symbol: deque(maxlen=5) for symbol in tickerlist}
    global usdt_balance
    async def connect_websocket():
        async with websockets.connect(
                "wss://fstream.binance.com/ws",
                ping_interval=60,
                ping_timeout=10) as websocket:
            # 모든 심볼에 대해 구독 메시지 전송
            for symbol in symbols:
                subscribe_message = {
                    "method": "SUBSCRIBE",
                    "params": [f"{symbol}@kline_1m"],
                    "id": 1
                }
                await websocket.send(json.dumps(subscribe_message))
                await asyncio.sleep(0.5)  # 0.5초 간격으로 구독

            # 데이터 수신 및 처리
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                #columns = ["Symbol", "Cur.Price", "5MA", "Position Amt", "Avg.Price", "L.Check", "L.losscut_price", "S.Check", "S.losscut_price"]
                if data.get('k'):
                    symbol = data['s'][:-4] + '/' + data['s'][-4:]
                    current_price = data['k']['c']
                    df.loc[symbol] = [symbol, current_price, None, None, None, None, None, None, None]  # 데이터 업데이트

                    previous_amt = float(df.at[symbol, 'Position Amt']) if df.at[symbol, 'Position Amt'] else 0
                    avg_price = float(df.at[symbol, 'Avg.Price']) if df.at[symbol, 'Avg.Price'] else 0
                    longcheck = df.at[symbol, 'L.Check'] if df.at[symbol, 'L.Check'] else "F"
                    shortcheck = df.at[symbol, 'S.Check'] if df.at[symbol, 'S.Check'] else "F"
                    ma = df.at[symbol, '5MA'] if df.at[symbol, '5MA'] else None
                    long_losscut = df.at[symbol, "L.losscut_price"] if df.at[symbol, "L.losscut_price"] else None
                    short_losscut = df.at[symbol, "S.losscut_price"] if df.at[symbol, "S.losscut_price"] else None

                    df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut]  # 데이터 업데이트
                    placeholder.table(df)

                    if str(data['k']['x']) == 'True':
                        recent_prices[symbol].append(float(data['k']['c']))
                        longcheck = "F"
                        shortcheck = "F"

                        df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut]  # 데이터 업데이트
                        placeholder.table(df)

                    ma = average_last_period(recent_prices[symbol],float(data['k']['c']), 5)

                    if ma is not None:
                        df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut]  # 데이터 업데이트
                        placeholder.table(df)

                    if ma is not None and df.at[symbol, 'L.Check'] != 'T' and float(current_price) >= float(ma)*(1+0.035):
                        longcheck = "T"

                        df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, shortcheck]  # 데이터 업데이트
                        placeholder.table(df)

                    if ma is not None and df.at[symbol, 'S.Check'] != 'T' and float(current_price) <= float(ma)*(1-0.035):
                        shortcheck = "T"

                        df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut]  # 데이터 업데이트
                        placeholder.table(df)

                    if avg_price != 0 and float(previous_amt) > 0:
                        long_losscut = float(avg_price) + float(usdt_balance) * 0.02 / float(previous_amt)

                        df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut]  # 데이터 업데이트
                        placeholder.table(df)

                    if avg_price != 0 and previous_amt < 0:
                        short_losscut = float(avg_price) + float(usdt_balance) * 0.02 / float(previous_amt)

                        df.loc[symbol] = [symbol, current_price, ma, previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut]  # 데이터 업데이트
                        placeholder.table(df)

                    if ma is not None and float(current_price) <= float(ma)*(1+0.03) and str(longcheck) == "T":
                        available_amt = round(float(usdt_balance) / float(current_price), 3)
                        short_open(binance_futures, symbol, available_amt)

                    if ma is not None and float(current_price) <= float(ma)*(1-0.03) and str(shortcheck) == "T":
                        available_amt = round(float(usdt_balance) / float(current_price), 3)
                        long_open(binance_futures, symbol, available_amt)

                    if previous_amt > 0:
                        if long_losscut is not None and float(current_price) <= float(long_losscut):
                            long_close(binance_futures,symbol, previous_amt)
                        elif avg_price != 0 and float(current_price) / float(avg_price) - 1 >= 0.01:
                            long_close(binance_futures, symbol, previous_amt)

                    if previous_amt < 0:
                        if short_losscut is not None and float(current_price) >= float(short_losscut):
                            short_close(binance_futures, symbol, previous_amt)
                        elif avg_price != 0 and float(avg_price) / float(current_price) - 1 >= 0.01:
                            short_close(binance_futures, symbol, previous_amt)


    await connect_websocket()

async def user_data_stream(api_key, api_secret, df):
    client = await AsyncClient.create(api_key, api_secret)
    bm = BinanceSocketManager(client)
    ts = bm.futures_user_socket()

    async with ts as tscm:
        while True:
            data = await tscm.recv()
            if data.get('e') and data['e'] == "ORDER_TRADE_UPDATE" and data['o']['X'] == 'FILLED':
                symbol = data['o']['s'][:-4] + '/' + data['o']['s'][-4:]
                avg_price = float(data['o']['ap'])
                amt = float(data['o']['q']) * (-1 if data['o']['S'] != 'BUY' else 1)

                current_price = float(df.at[symbol, 'Cur.Price']) if df.at[symbol, 'Cur.Price'] else None
                time = df.at[symbol, "updates_time"] if df.at[symbol, "updates_time"] else None
                ma = float(df.at[symbol, '5MA']) if pd.notna(df.at[symbol, '5MA']) else None
                longcheck = df.at[symbol, 'L.Check']
                shortcheck = df.at[symbol, 'S.Check']
                long_losscut = df.at[symbol, "L.losscut_price"] if df.at[symbol, "L.losscut_price"] else None
                short_losscut = df.at[symbol, "S.losscut_price"] if df.at[symbol, "S.losscut_price"] else None

                previous_amt = float(df.at[symbol, 'Position Amt']) if df.at[symbol, 'Position Amt'] else 0
                df.loc[symbol] = [symbol, current_price, ma, amt+previous_amt, avg_price, longcheck, long_losscut, shortcheck, short_losscut, time]  # 데이터 업데이트
                placeholder.table(df)


            # Streamlit에 유저 데이터 업데이트 표시
            #data_placeholder.write(data)

async def main(api_key, api_secret, symbols, df):
    #asyncio.gather를 사용하여 두 웹소켓 작업을 동시에 실행
    await asyncio.gather(
        user_data_stream(api_key, api_secret, df),
        #listen_to_websocket(symbols, df),
        run_all_symbols(symbols, df),
    )

def calculate_moving_average(prices, moving_average_period):
    if len(prices) == moving_average_period:
        return sum(prices) / moving_average_period
    else:
        return None

def api_load():
    return ccxt.binance(config={
        'apiKey': "HgoM8YxJ5DZwJXaVRZ87JEEeGpmWDSAXGSzxGeCsM25tqbi6xPHDTT2fMXQFt9bR",
        'secret': "8t03t3Fa1GQZCD2f99r3HEE9GYVeXNhS4FyjZpCVPTbGofmoPYATilUCoXWJKixf",
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True,
        },
    })

def api_call_to_get_balance():
    return ccxt.binanceus.fetch_balance(api_load(), params={"type": "future", 'recvWindow': 10000000})

def long_open(client, coin, amt):
    client.set_leverage(8, coin)
    client.create_market_order(client, coin, 'buy', amt)

    balance_data = api_call_to_get_balance()
    usdt_balance = balance_data['free']['USDT']

    with header:
        st.write(f"Available USDT balance: {usdt_balance}")

def short_open(client, coin, amt):
    client.set_leverage(8, coin)
    client.create_market_order(client, coin, 'sell', amt)
    balance_data = api_call_to_get_balance()
    usdt_balance = balance_data['free']['USDT']

    with header:
        st.write(f"Available USDT balance: {usdt_balance}")

def long_close(client, coin, positions):
    client.create_market_order(client, coin, 'sell', float(positions), params={'reduceOnly': True})
    balance_data = api_call_to_get_balance()
    usdt_balance = balance_data['free']['USDT']

    with header:
        st.write(f"Available USDT balance: {usdt_balance}")

def short_close(client, coin, positions):
    client.create_market_order(client, coin, 'buy', -float(positions), params={'reduceOnly': True})
    balance_data = api_call_to_get_balance()
    usdt_balance = balance_data['free']['USDT']

    with header:
        st.write(f"Available USDT balance: {usdt_balance}")

def rewrite_cash():
    balance_data = api_call_to_get_balance()
    usdt_balance = balance_data['free']['USDT']

    with header:
        st.write(f"Available USDT balance: {usdt_balance}")

def average_last_period(lst, num, period):
    # if not isinstance(lst, list):
    #    raise TypeError("The first argument must be a list.")
    # if not isinstance(num, (int, float)):
    #    raise TypeError("The second argument must be an int or a float.")

    if len(lst) == period:
        # lst.pop(len(lst) - 1)
        last_five_values = list(lst)[-4:]
        average = (sum(last_five_values) + num) / (len(last_five_values) + 1)
        return average
    else:
        return None

def find_two_largest(numbers, period):
    if len(numbers) == period:
        recent_19 = numbers[-18:]
        sorted_numbers = sorted(recent_19, reverse=True)

        max_value = sorted_numbers[0]
        check_max_value = recent_19[-1] is max_value

        second_largest = sorted_numbers[1]
        recent_four = recent_19[-4:]
        check_recent_four = all(x < second_largest for x in recent_four)

        if check_max_value and check_recent_four:
            return max_value, second_largest

    else:
        return None

def find_two_smallest(numbers, period):
    if len(numbers) == period:
        recent_19 = numbers[-18:]
        sorted_numbers = sorted(recent_19, reverse=False)

        min_value = sorted_numbers[0]
        check_min_value = recent_19[-1] is min_value

        second_smallest = sorted_numbers[1]
        recent_four = recent_19[-4:]
        check_recent_four = all(x > second_smallest for x in recent_four)

        if check_min_value and check_recent_four:
            return min_value, second_smallest
    else:
        return None

########################################################################################################################

api_key = "HgoM8YxJ5DZwJXaVRZ87JEEeGpmWDSAXGSzxGeCsM25tqbi6xPHDTT2fMXQFt9bR"
api_secret = '8t03t3Fa1GQZCD2f99r3HEE9GYVeXNhS4FyjZpCVPTbGofmoPYATilUCoXWJKixf'

binance_futures = api_load()
tickers = list(binance_futures.fetch_tickers().keys())
tickerlist = [tickers[i][:-5] for i in range(len(tickers)) if tickers[i][-4:] == 'USDT']

# 스트리밍할 심볼 리스트
symbols = [ticker.replace('/', '').lower() for ticker in tickerlist]

# 초기 데이터프레임 생성
columns = ["Symbol", "Cur.Price", "5MA", "Position Amt", "Avg.Price", "L.Check", "L.losscut_price", "S.Check", "S.losscut_price", "updates_time"]
df = pd.DataFrame(columns=columns)

for ticker in tickerlist:
    df.loc[ticker] = [None, None, None, None, None, None, None, None, None, None]


# Streamlit 페이지 설정
st.set_page_config(page_title="Coin_bot", layout="wide")
st.title("Coin_bot")

header = st.container()
body = st.container()

rewrite_cash()

with body:
    placeholder = st.empty()


asyncio.run(main(api_key,api_secret,symbols, df))
