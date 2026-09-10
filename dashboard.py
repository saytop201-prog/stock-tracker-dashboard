import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import io
import datetime
import db_manager
from bs4 import BeautifulSoup
import FinanceDataReader as fdr

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
        if st.session_state["password"] == "0000": 
            st.session_state["password_correct"] = True
            del st.session_state["password"] 
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔒 비밀번호를 입력하세요:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔒 비밀번호를 입력하세요:", type="password", on_change=password_entered, key="password")
        st.error("비밀번호가 틀렸습니다.")
        return False
    else:
        return True

if not check_password():
    st.stop()

@st.cache_data(ttl=3600)
def get_historical_financials(ticker):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={ticker}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        dfs = pd.read_html(io.StringIO(res.text), encoding='euc-kr')
        df = dfs[4]
        
        annual_cols = [c for c in df.columns if '최근 연간 실적' in c[0]]
        df_annual = df[annual_cols].copy()
        df_annual.columns = [c[1] for c in annual_cols]
        
        metric_names = ['매출액', '영업이익', '당기순이익', '영업이익률', '순이익률', 'ROE(%)', 
                        '부채비율', '당좌비율', '유보율', 'EPS(원)', 'PER(배)', 'BPS(원)', 'PBR(배)', 
                        '주당배당금', '시가배당률', '배당성향']
        df_annual.index = metric_names[:len(df_annual)]
        return df_annual
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_daily_prices(ticker, years=3):
    start_date = datetime.datetime.now() - datetime.timedelta(days=365 * years)
    df = fdr.DataReader(ticker, start_date)
    return df

st.title("📈 반도체 소부장 트래킹 대시보드")
st.sidebar.header("종목 선택")
selected_company = st.sidebar.selectbox("종목을 선택하세요", list(TARGET_STOCKS.keys()))
ticker = TARGET_STOCKS[selected_company]

st.header(f"[{ticker}] {selected_company}")

df_estimates = db_manager.get_historical_estimates(ticker)
df_brokers = db_manager.get_estimates_by_broker(ticker)
df_financials = get_historical_financials(ticker)

# --- 1. Top Summary Cards ---
if not df_estimates.empty:
    latest = df_estimates.iloc[-1]
    mcap = latest['market_cap']
    op26 = latest['op_26']
    op27 = latest['op_27']
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("시가총액", f"{mcap:,.0f} 억" if pd.notnull(mcap) else "N/A")
    col2.metric("26E 평균 영업이익", f"{op26:,.0f} 억" if pd.notnull(op26) else "N/A")
    col3.metric("27E 평균 영업이익", f"{op27:,.0f} 억" if pd.notnull(op27) else "N/A")
    
    por26 = round(mcap / op26, 2) if pd.notnull(mcap) and pd.notnull(op26) and op26 > 0 else "N/A"
    por27 = round(mcap / op27, 2) if pd.notnull(mcap) and pd.notnull(op27) and op27 > 0 else "N/A"
    col4.metric("26E / 27E POR", f"{por26}배 / {por27}배")

st.divider()

# --- 2. Historical Key Financials & YoY Growth ---
col_fin, col_yoy = st.columns([2, 1])
with col_fin:
    st.subheader("📊 Historical Key Financials (최근 연간 실적)")
    if not df_financials.empty:
        st.dataframe(df_financials, use_container_width=True)
    else:
        st.info("데이터를 불러올 수 없습니다.")

with col_yoy:
    st.subheader("🚀 영업이익 YoY(%) 상승률")
    if not df_financials.empty and not df_brokers.empty:
        try:
            # 2025E 영업이익 (네이버 금융 테이블의 3번째 컬럼이 2025.12 예상치)
            op_25_str = str(df_financials.loc['영업이익'].iloc[2])
            op_25 = float(op_25_str.replace(',', '')) if op_25_str != 'NaN' and op_25_str != 'nan' else None
            
            avg_op26 = df_brokers['op_26'].mean()
            avg_op27 = df_brokers['op_27'].mean()
            
            yoy_data = []
            if op_25 and avg_op26:
                yoy_26 = ((avg_op26 / op_25) - 1) * 100
                yoy_data.append({"연도": "2026E", "영업이익(억)": round(avg_op26), "YoY (%)": f"+{yoy_26:.1f}%" if yoy_26 > 0 else f"{yoy_26:.1f}%"})
            if avg_op26 and avg_op27:
                yoy_27 = ((avg_op27 / avg_op26) - 1) * 100
                yoy_data.append({"연도": "2027E", "영업이익(억)": round(avg_op27), "YoY (%)": f"+{yoy_27:.1f}%" if yoy_27 > 0 else f"{yoy_27:.1f}%"})
                
            if yoy_data:
                st.dataframe(pd.DataFrame(yoy_data), use_container_width=True)
            else:
                st.info("비교할 2025년 영업이익 데이터가 부족합니다.")
        except Exception as e:
            st.error("YoY 계산 중 에러 발생")
    else:
        st.info("추정치 데이터가 없습니다.")

st.divider()

# --- 3. 증권사별 미래 컨센서스 비교 ---
st.subheader("🏢 증권사별 2026E / 2027E 컨센서스")
if not df_brokers.empty:
    # Add Average Row
    avg_row = pd.DataFrame([{
        'broker': '평균 (Average)',
        'op_26': df_brokers['op_26'].mean(),
        'np_26': df_brokers['np_26'].mean(),
        'op_27': df_brokers['op_27'].mean(),
        'np_27': df_brokers['np_27'].mean(),
        'date': '-'
    }])
    df_disp = pd.concat([df_brokers, avg_row], ignore_index=True)
    df_disp.columns = ['증권사', '26E 영업이익', '26E 순이익', '27E 영업이익', '27E 순이익', '업데이트 일자']
    
    # Format
    for col in ['26E 영업이익', '26E 순이익', '27E 영업이익', '27E 순이익']:
        df_disp[col] = df_disp[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "N/A")
        
    st.dataframe(df_disp, use_container_width=True)
else:
    st.info("수집된 증권사 리포트가 없습니다.")

st.divider()

# --- 4. Historical PER / PBR / POR Band Charts ---
st.subheader("📈 Historical Valuation 밴드 차트 (3년)")
df_prices = get_daily_prices(ticker, years=3)

if not df_prices.empty and not df_financials.empty:
    try:
        # 최근 12개월(TTM) EPS, BPS 추정 (가장 최근 연도 데이터 사용)
        eps_str = str(df_financials.loc['EPS(원)'].iloc[1]) # 2024년 기준
        bps_str = str(df_financials.loc['BPS(원)'].iloc[1])
        
        eps = float(eps_str.replace(',', '')) if eps_str != 'NaN' else 0
        bps = float(bps_str.replace(',', '')) if bps_str != 'NaN' else 0
        
        tab1, tab2 = st.tabs(["PER 밴드", "PBR 밴드"])
        
        with tab1:
            if eps > 0:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_prices.index, y=df_prices['Close'], mode='lines', name='주가', line=dict(color='black', width=2)))
                
                multiples = [10, 15, 20, 25, 30]
                colors = ['#FF9999', '#FFCC99', '#FFFF99', '#CCFF99', '#99FF99']
                
                for mult, color in zip(multiples, colors):
                    fig.add_trace(go.Scatter(x=df_prices.index, y=[eps * mult] * len(df_prices), mode='lines', name=f'{mult}x', line=dict(color=color, dash='dash')))
                
                fig.update_layout(title="Historical PER Band (Trailing EPS 기준)", yaxis_title="주가 (원)", height=500)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("EPS 데이터가 부족하여 PER 밴드를 그릴 수 없습니다.")
                
        with tab2:
            if bps > 0:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_prices.index, y=df_prices['Close'], mode='lines', name='주가', line=dict(color='black', width=2)))
                
                multiples = [1.0, 2.0, 3.0, 4.0, 5.0]
                colors = ['#FF9999', '#FFCC99', '#FFFF99', '#CCFF99', '#99FF99']
                
                for mult, color in zip(multiples, colors):
                    fig.add_trace(go.Scatter(x=df_prices.index, y=[bps * mult] * len(df_prices), mode='lines', name=f'{mult}x', line=dict(color=color, dash='dash')))
                
                fig.update_layout(title="Historical PBR Band (Trailing BPS 기준)", yaxis_title="주가 (원)", height=500)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("BPS 데이터가 부족하여 PBR 밴드를 그릴 수 없습니다.")
    except Exception as e:
        st.error(f"차트 렌더링 중 에러가 발생했습니다: {e}")
else:
    st.info("주가 또는 재무 데이터가 부족합니다.")
