import streamlit as st
import pandas as pd
import plotly.express as px
import OpenDartReader
import db_manager

DART_API_KEY = 'c7701951' + 'd3927d434089d60e4a0590dc56dc047c'
dart = OpenDartReader(DART_API_KEY)

TARGET_STOCKS = {
    '마이크로컨텍솔': '098120', '티에스이': '131290', '티에프이': '425420', 'ISC': '095340',
    '디아이': '003160', '엑시콘': '092870', '인텍플러스': '064290', '이오테크닉스': '039030',
    '케이씨텍': '281820', '브이엠': '089970', '피에스케이': '319660', '테스': '095610',
    '엠케이전자': '033160', '티엘비': '356860', '심텍': '222800',
    '이엔에프테크놀로지': '102710', '티씨케이': '064760', '하나머티리얼즈': '166090', '엘티씨': '170920',
    'DB하이텍': '000990', '두산': '000150'
}

st.set_page_config(page_title="소부장 트래킹 대시보드", layout="wide")

def check_password():
    def password_entered():
        # 기본 비밀번호는 0000 입니다. 원하시면 여기서 변경 가능합니다.
        if st.session_state["password"] == "0000": 
            st.session_state["password_correct"] = True
            del st.session_state["password"] 
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔒 나만의 주식 대시보드입니다. 비밀번호를 입력하세요:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔒 나만의 주식 대시보드입니다. 비밀번호를 입력하세요:", type="password", on_change=password_entered, key="password")
        st.error("비밀번호가 틀렸습니다.")
        return False
    else:
        return True

if not check_password():
    st.stop()

st.title("📈 반도체 소부장 종목 트래킹 대시보드")

# Sidebar
st.sidebar.header("종목 선택")
selected_company = st.sidebar.selectbox("종목을 선택하세요", list(TARGET_STOCKS.keys()))
ticker = TARGET_STOCKS[selected_company]

try:
    df = db_manager.get_historical_estimates(ticker)
except Exception:
    df = pd.DataFrame()

st.header(f"[{ticker}] {selected_company}")

if not df.empty:
    latest = df.iloc[-1]
    
    col1, col2, col3, col4 = st.columns(4)
    mcap = latest['market_cap']
    op26 = latest['op_26']
    op27 = latest['op_27']
    
    col1.metric("시가총액", f"{mcap:,.0f} 억" if pd.notnull(mcap) else "N/A")
    col2.metric("26E 영업이익", f"{op26:,.0f} 억" if pd.notnull(op26) else "N/A")
    col3.metric("27E 영업이익", f"{op27:,.0f} 억" if pd.notnull(op27) else "N/A")
    
    por26 = round(mcap / op26, 2) if pd.notnull(mcap) and pd.notnull(op26) and op26 > 0 else "N/A"
    por27 = round(mcap / op27, 2) if pd.notnull(mcap) and pd.notnull(op27) and op27 > 0 else "N/A"
    
    col4.metric("26E / 27E POR", f"{por26}배 / {por27}배")

    st.subheader("📊 실적 추정치 변화 트렌드")
    
    chart_df = df[['date', 'op_26', 'op_27']].dropna(subset=['op_26', 'op_27'], how='all')
    if not chart_df.empty:
        chart_df = chart_df.melt(id_vars='date', value_vars=['op_26', 'op_27'], var_name='연도', value_name='영업이익(억)')
        chart_df['연도'] = chart_df['연도'].map({'op_26': '2026E', 'op_27': '2027E'})
        fig = px.line(chart_df, x='date', y='영업이익(억)', color='연도', markers=True, title=f"{selected_company} 예상 영업이익 변화 추이")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("아직 누적된 실적 추정치 데이터가 충분하지 않습니다. (리포트 업데이트 필요)")
        
    with st.expander("📝 누적 데이터베이스 기록 보기"):
        st.dataframe(df)
else:
    st.warning("데이터베이스에 해당 종목의 데이터가 없습니다. 네이버나 텔레그램 트래커 스크립트를 먼저 실행해주세요.")

st.subheader("📢 최근 공시 (DART)")
try:
    import datetime
    today = datetime.datetime.today()
    start_date = (today - datetime.timedelta(days=180)).strftime('%Y%m%d')
    dart_df = dart.list(ticker, start=start_date) 
    
    if dart_df is not None and not dart_df.empty:
        dart_df = dart_df[['rcept_dt', 'report_nm', 'flr_nm']]
        dart_df.columns = ['접수일자', '보고서명', '제출인']
        st.dataframe(dart_df.head(15), use_container_width=True)
    else:
        st.info("최근 6개월간 공시 내역이 없습니다.")
except Exception as e:
    st.error(f"공시 정보를 불러오는 중 에러가 발생했습니다: {e}")
