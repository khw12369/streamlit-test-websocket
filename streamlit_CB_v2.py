import streamlit as st
import websocket
import json
import threading
import time

# 스트림릿 페이지 설정
st.set_page_config(page_title="Binance WebSocket", page_icon=":chart_with_upwards_trend:")
websocket_instances = {}
converted_tickerlist = ['btcusdt']

# 데이터 저장을 위한 세션 상태 초기화
if 'data' not in st.session_state:
    st.session_state['data'] = []

def create_socket(symbols_chunk, chunk_id):
    def on_open(ws):
        for symbol in symbols_chunk:
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": [f"{symbol}@kline_1m"],
                "id": 1
            }
            ws.send(json.dumps(subscribe_message))

            print(symbol)
            time.sleep(0.5)  # To respect the 5 messages per second limit

    def on_error(ws, error):
        error_message = f"Websocket error: {error}"
        print(error_message)  # Print error for debugging

    def on_close(ws, close_status_code, close_msg):
        print(f"Connection closed with status {close_status_code}, message: {close_msg}")
        print("Attempting to reconnect...")
        time.sleep(10)  # Wait for 10 seconds before attempting to reconnect
        create_socket(symbols_chunk, chunk_id)  # Call a function to reconnect without creating a new thread

    def on_pong(ws, payload):
        print("Pong received:", payload)

    def on_message(ws, message):
        data = json.loads(message)
        st.session_state['data'].append(data)

    def connect_and_run():

        socket = "wss://fstream.binance.com/ws?"
        ws = websocket.WebSocketApp(socket,
                                    on_open=on_open,
                                    on_close=on_close,
                                    on_error=on_error,
                                    on_message=on_message,
                                    on_pong=on_pong)
        websocket_instances[chunk_id] = ws
        ws.run_forever(ping_interval=60, ping_timeout=10)
        #ws.run_forever()


    connect_and_run()

def run():
    chunk_size = 50  # Adjust as needed
    chunks = [converted_tickerlist[i:i + chunk_size] for i in
              range(0, len(converted_tickerlist), chunk_size)]

    threads = []
    for i, chunk in enumerate(chunks):
        t = threading.Thread(target=create_socket, args=(chunk, i))
        t.start()

        threads.append(t)
        time.sleep(1)

    for thread in threads:
        thread.join()

def display_data():
    if 'data' in st.session_state:
        for new_data in st.session_state['data']:
            st.write(new_data)  # 여기서 UI를 업데이트합니다.
        st.session_state['data'].clear()

# 스트림릿 앱 메인 함수
def main():
    st.title("Binance WebSocket 예제")

    # 웹소켓 실행을 위한 스레드 시작
    #thread = threading.Thread(target=run_websocket)
    #thread.start()
    websocket_instances = {}
    #run_websocket()
    run()

    # 앱이 종료될 때까지 대기
    #st.button("종료하기", on_click=run_websocket())

if __name__ == "__main__":
    main()

    if st.button('Display new data'):
        display_data()
