import streamlit as st

# 세션 상태 초기화
if 'button_clicked' not in st.session_state:
    st.session_state.button_clicked = False

# 버튼 클릭 처리 함수
def handle_click():
    st.session_state.button_clicked = not st.session_state.button_clicked

# 버튼을 화면에 표시하고, 클릭 시 handle_click 함수를 호출
clicked = st.button("매매 시작", on_click=handle_click)

# 버튼 클릭 상태에 따라 다른 메시지 표시
if st.session_state.button_clicked:
    st.success("매매가 활성화되었습니다. 매매를 시작합니다.")
    # 매매 로직을 여기에 추가
    # 예: trading_function()
else:
    st.info("매매가 비활성화되었습니다. 매매를 시작하려면 버튼을 클릭하세요.")

# 버튼 클릭 상태에 따른 추가적인 작업
# 예를 들어, 매매 시작 버튼이 활성화된 상태에서만 매매 로직을 수행
if st.session_state.button_clicked:
    # 매매 로직 수행
    # 예: perform_trading()
    st.write("매매 로직이 실행 중입니다...")
