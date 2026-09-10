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
            op_25_str = str(df_financials.loc['영업이익'].iloc[2])
            op_25 = float(op_25_str.replace(',', '')) if op_25_str not in ['NaN', 'nan', '-'] else None
            
            avg_op26 = df_brokers['op_26'].mean()
            avg_op27 = df_brokers['op_27'].mean()
            
            yoy_data = []
            if pd.notnull(op_25) and pd.notnull(avg_op26) and op_25 > 0:
                yoy_26 = ((avg_op26 / op_25) - 1) * 100
                yoy_data.append({"연도": "2026E", "영업이익(억)": round(avg_op26), "YoY (%)": f"+{yoy_26:.1f}%" if yoy_26 > 0 else f"{yoy_26:.1f}%"})
            if pd.notnull(avg_op26) and pd.notnull(avg_op27) and avg_op26 > 0:
                yoy_27 = ((avg_op27 / avg_op26) - 1) * 100
                yoy_data.append({"연도": "2027E", "영업이익(억)": round(avg_op27), "YoY (%)": f"+{yoy_27:.1f}%" if yoy_27 > 0 else f"{yoy_27:.1f}%"})
                
            if yoy_data:
                st.dataframe(pd.DataFrame(yoy_data), use_container_width=True)
            else:
                st.info("비교할 2025년 영업이익 데이터가 부족하거나 적자입니다.")
        except Exception as e:
            st.error(f"YoY 계산 중 에러 발생: {e}")
    else:
        st.info("추정치 데이터가 없습니다.")

st.divider()

# --- 3. 증권사별 미래 컨센서스 비교 ---
st.subheader("🏢 증권사별 2026E / 2027E 컨센서스")
if not df_brokers.empty:
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
        # 가치 평가 밴드의 기준은 2025E(미래 예상치)를 최우선으로, 없으면 2024년 사용
        eps_str_25 = str(df_financials.loc['EPS(원)'].iloc[2])
        bps_str_25 = str(df_financials.loc['BPS(원)'].iloc[2])
        
        eps_str = eps_str_25 if eps_str_25 not in ['NaN', 'nan', '-'] else str(df_financials.loc['EPS(원)'].iloc[1])
        bps_str = bps_str_25 if bps_str_25 not in ['NaN', 'nan', '-'] else str(df_financials.loc['BPS(원)'].iloc[1])
        
        eps = float(eps_str.replace(',', '')) if eps_str not in ['NaN', 'nan', '-'] else 0
        bps = float(bps_str.replace(',', '')) if bps_str not in ['NaN', 'nan', '-'] else 0
        
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

# --- 5. 개별 종목 Deep Dive (티에프이 전용) ---
if ticker == '425420':
    st.divider()
    st.subheader("🕵️‍♂️ [Deep Dive] 티에프이 핵심 투자 아이디어 & 트래킹 지표")
    
    st.markdown("""
    #### 1. 핵심 투자 포인트: "고객사 다변화 및 선행지표(매입액)의 폭발적 증가"
    * **고객 집중도 완화**: A+B사(삼성 등 주력고객) 매출 비중이 25.1Q 81.0%에서 26.2Q 65.9%로 낮아지며 기타/해외 고객 비중이 증가했습니다.
    * **원재료 매입의 역대급 스파이크**: 26.2Q 'Board Parts'와 'PCB' 매입액이 전분기 대비 약 +63.9% 폭증했습니다. 매입액은 다음 분기 매출을 설명하는 가장 강력한 선행지표(상관계수 0.91)입니다.

    #### 2. 🔮 2026년 3분기 실적 추정 (Base 시나리오)
    * **예상 매출**: **370억 ~ 400억원 (중심값 390억원)**
    * **예상 영업이익**: **약 70억원 (OPM 18.0%)**
    * **근거**: 26.2Q 역대급 원재료 매입액(172.5억)에 과거 평균 매출 전환율(2.61배)을 곱하면 450억원이 산출되나, 재고자산 증가(QoQ +35.8%)를 보수적으로 감안하여 하향 조정한 수치입니다. (Board 매출의 폭발적 증가 예상)

    #### 3. 🚀 2027년 EPS 전망 및 SOCAMM·CPO 업사이드
    현재 시장 컨센서스(2027년 EPS 3,660원)는 보수적입니다. 마이크론향 SOCAMM 및 광통신(CPO) 테스트 소켓 매출이 가시화될 경우 EPS 상향이 기대됩니다.
    * **Base 시나리오 (+8.7% 업사이드)**: 신사업 매출 200억 추가 ➡️ **조정 EPS 3,977원**
    * **Bull 시나리오 (+20.8% 업사이드)**: 신사업 매출 400억 추가 ➡️ **조정 EPS 4,422원**
    
    이 핵심 데이터들을 직접 추적하려면 매 분기 발표되는 **[전자공시시스템(DART) - 분기보고서 / 반기보고서 / 사업보고서]**를 열어보셔야 합니다.
    """)
    
    try:
        import sqlite3
        conn = sqlite3.connect('tracking.db')
        df_dart_raw = pd.read_sql_query("SELECT rcept_no, report_nm, board_parts_krw, pcb_krw, socket_krw, samsung_rev, other_rev FROM tfe_dart", conn)
        conn.close()
        
        if not df_dart_raw.empty:
            df_dart_raw['year'] = df_dart_raw['report_nm'].str.extract(r'(\d{4})').astype(int)
            df_dart_raw['month'] = df_dart_raw['report_nm'].str.extract(r'\.(\d{2})\)').astype(int)
            df_dart_raw.sort_values(['year', 'month'], inplace=True)
            
            metric_cols = ['board_parts_krw', 'pcb_krw', 'socket_krw', 'samsung_rev', 'other_rev']
            standalone_records = []
            
            for year, group in df_dart_raw.groupby('year'):
                cums = {m: group[group['month'] == m].iloc[0] for m in group['month']}
                
                if 3 in cums:
                    rec = {'기간': f'{year} 1Q'}
                    for c in metric_cols: rec[c] = cums[3][c]
                    standalone_records.append(rec)
                if 6 in cums and 3 in cums:
                    rec = {'기간': f'{year} 2Q'}
                    for c in metric_cols: rec[c] = cums[6][c] - cums[3][c]
                    standalone_records.append(rec)
                if 9 in cums and 6 in cums:
                    rec = {'기간': f'{year} 3Q'}
                    for c in metric_cols: rec[c] = cums[9][c] - cums[6][c]
                    standalone_records.append(rec)
                if 12 in cums and 9 in cums:
                    rec = {'기간': f'{year} 4Q'}
                    for c in metric_cols: rec[c] = cums[12][c] - cums[9][c]
                    standalone_records.append(rec)
                if 12 in cums and 9 not in cums and 6 in cums:
                    rec = {'기간': f'{year} 2H(3Q+4Q)'}
                    for c in metric_cols: rec[c] = cums[12][c] - cums[6][c]
                    standalone_records.append(rec)
                if 12 in cums and 9 not in cums and 6 not in cums and 3 in cums:
                    rec = {'기간': f'{year} 2Q~4Q'}
                    for c in metric_cols: rec[c] = cums[12][c] - cums[3][c]
                    standalone_records.append(rec)
                    
            df_standalone = pd.DataFrame(standalone_records)
            
            st.markdown("#### 📊 [자동 업데이트] 전자공시 원재료 및 고객사 매출 트래킹 (단일 분기 환산)")
            
            df_table = df_standalone.copy()
            df_table.columns = ['기간', 'Board Parts 매입(백만)', 'PCB 매입(백만)', 'Socket 매입(백만)', '삼성전자 매출(백만)', '기타 매출(백만)']
            
            for col in df_table.columns[1:]:
                df_table[col] = df_table[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "-")
                
            st.dataframe(df_table, use_container_width=True)
            
            # 차트 그릴 때는 왜곡을 막기 위해 순수 분기(1Q, 2Q, 3Q, 4Q) 데이터만 필터링
            df_chart = df_standalone[df_standalone['기간'].str.contains('Q$')].copy()
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig1 = go.Figure()
                fig1.add_trace(go.Bar(x=df_chart['기간'], y=df_chart['board_parts_krw'], name='Board Parts'))
                fig1.add_trace(go.Bar(x=df_chart['기간'], y=df_chart['pcb_krw'], name='PCB'))
                fig1.add_trace(go.Bar(x=df_chart['기간'], y=df_chart['socket_krw'], name='Socket'))
                fig1.update_layout(title="원재료 분기별 매입액 추이", barmode='group', yaxis_title="금액 (백만원)")
                st.plotly_chart(fig1, use_container_width=True)
                
            with col2:
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(x=df_chart['기간'], y=df_chart['samsung_rev'], name='삼성전자'))
                fig2.add_trace(go.Bar(x=df_chart['기간'], y=df_chart['other_rev'], name='기타 고객사'))
                fig2.update_layout(title="고객사 분기별 매출액 추이", barmode='group', yaxis_title="금액 (백만원)")
                st.plotly_chart(fig2, use_container_width=True)
                
            st.info("💡 위 데이터는 DART API와 AI(Gemini)를 통해 매일 아침 6시 최신 분기/사업보고서의 '사업의 내용'을 스크래핑하여 단일 분기로 환산됩니다.")
    except Exception as e:
        st.error(f"DART 표 렌더링 중 에러: {e}")
