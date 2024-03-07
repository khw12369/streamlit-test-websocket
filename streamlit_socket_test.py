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
import os

api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                        if data.get('k'):
                            symbol = data['s'][:-4] + '/' + data['s'][-4:]
                            current_price = data['k']['c']

                            timestamp = data['E'] if data['E'] else None
                            time = datetime.fromtimestamp(timestamp / 1000.0).strftime('%m-%d %H:%M:%S')
                            df.loc[symbol] = [symbol, current_price, None, None, None, None, None, None, None, time]  # 데이터 업데이트
                            df['Cur.Price'] = df['Cur.Price'].astype(str)
                            placeholder.table(df)
                        # 데이터 처리 로직을 여기에 구현하세요.

                    elif isinstance(response, bytes):
                        # 핑/퐁 메시지 처리
                        opcode = response[0] & 0x0f
                        if opcode == 0x9:  # 0x9는 핑 메시지의 오퍼레이션 코드
                            logger.info("Ping message received, sending Pong response.")
                            await websocket.pong(response[1:])  # 퐁 응답을 보냄

                    else:
                        df.loc[symbol] = [None, None, None, None, None, None, None, None, None, None]  # 데이터 업데이트
                        placeholder.table(df)
                        #await asyncio.sleep(1)
                        break

                #await asyncio.sleep(1)
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"{symbol} connection closed: {e}, attempting to reconnect...")
            await asyncio.sleep(10)
            continue

        except Exception as e:
            logger.error(f"{symbol} connection closed: {e}, attempting to reconnect...")
            await asyncio.sleep(10)
            continue

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
        'apiKey': api_key,
        'secret': api_secret,
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

api_key = api_key
api_secret = api_secret

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
