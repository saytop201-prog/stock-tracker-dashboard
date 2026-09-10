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
        if st.session_state.get("password", "") == "0000": 
            st.session_state["password_correct"] = True
            if "password" in st.session_state:
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
st.subheader("🏢 증권사별 리포트 컨센서스 (목표주가 및 미래 실적)")
if not df_brokers.empty:
    avg_row = pd.DataFrame([{
        'broker': '평균 (Average)',
        'tp': df_brokers['tp'].mean(),
        'op_26': df_brokers['op_26'].mean(),
        'np_26': df_brokers['np_26'].mean(),
        'op_27': df_brokers['op_27'].mean(),
        'np_27': df_brokers['np_27'].mean(),
        'date': '-'
    }])
    df_disp = pd.concat([df_brokers, avg_row], ignore_index=True)
    df_disp.columns = ['증권사', '목표주가(원)', '26E 영업이익', '26E 순이익', '27E 영업이익', '27E 순이익', '업데이트 일자']
    
    for col in ['목표주가(원)', '26E 영업이익', '26E 순이익', '27E 영업이익', '27E 순이익']:
        df_disp[col] = df_disp[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "N/A")
        
    st.dataframe(df_disp, use_container_width=True)
else:
    st.info("수집된 증권사 리포트가 없습니다.")

st.divider()

def get_historical_metrics(df_price, df_fin):
    eps_series = pd.Series(index=df_price.index, dtype=float)
    bps_series = pd.Series(index=df_price.index, dtype=float)
    
    year_eps = {}
    year_bps = {}
    for col in df_fin.columns:
        if '20' in col:
            year_str = col[:4]
            try:
                e_val = str(df_fin.loc['EPS(원)', col]).replace(',', '')
                b_val = str(df_fin.loc['BPS(원)', col]).replace(',', '')
                year_eps[year_str] = float(e_val) if e_val not in ['NaN', 'nan', '-', ''] else None
                year_bps[year_str] = float(b_val) if b_val not in ['NaN', 'nan', '-', ''] else None
            except:
                pass
                
    for date in df_price.index:
        y_str = str(date.year)
        if y_str in year_eps and pd.notnull(year_eps[y_str]):
            eps_series[date] = year_eps[y_str]
        else:
            prev_y = str(date.year - 1)
            if prev_y in year_eps and pd.notnull(year_eps[prev_y]):
                eps_series[date] = year_eps[prev_y]
                
        if y_str in year_bps and pd.notnull(year_bps[y_str]):
            bps_series[date] = year_bps[y_str]
        else:
            prev_y = str(date.year - 1)
            if prev_y in year_bps and pd.notnull(year_bps[prev_y]):
                bps_series[date] = year_bps[prev_y]
                
    eps_series.ffill(inplace=True)
    bps_series.ffill(inplace=True)
    eps_series.bfill(inplace=True)
    bps_series.bfill(inplace=True)
    
    return eps_series, bps_series

def plot_per_band(df, eps_series, per_multiples=[10, 15, 20, 25, 30]):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='주가', line=dict(color='black', width=2)))
    colors = ['#FF9999', '#FFCC99', '#FFFF99', '#CCFF99', '#99FF99']
    for per, color in zip(per_multiples, colors):
        fig.add_trace(go.Scatter(x=df.index, y=eps_series * per, name=f'{per}x', line=dict(color=color, dash='dash')))
    fig.update_layout(title="Historical PER Band (Trailing EPS 기준)", xaxis_title="날짜", yaxis_title="주가 (원)")
    return fig

def plot_pbr_band(df, bps_series, pbr_multiples=[1, 2, 3, 4, 5]):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='주가', line=dict(color='black', width=2)))
    colors = ['#FF9999', '#FFCC99', '#FFFF99', '#CCFF99', '#99FF99']
    for pbr, color in zip(pbr_multiples, colors):
        fig.add_trace(go.Scatter(x=df.index, y=bps_series * pbr, name=f'{pbr}x', line=dict(color=color, dash='dash')))
    fig.update_layout(title="Historical PBR Band (Trailing BPS 기준)", xaxis_title="날짜", yaxis_title="주가 (원)")
    return fig

# --- 4. Historical PER / PBR / POR Band Charts ---
st.subheader("📈 Historical Valuation 밴드 차트 & Z-Score (3년)")
df_prices = get_daily_prices(ticker, years=3)

if not df_prices.empty and not df_financials.empty:
    try:
        eps_series, bps_series = get_historical_metrics(df_prices, df_financials)
        
        tab1, tab2 = st.tabs(["PER 밴드", "PBR 밴드"])
        
        with tab1:
            if eps_series.mean() > 0:
                st.plotly_chart(plot_per_band(df_prices, eps_series), use_container_width=True)
                
                per_history = df_prices['Close'] / eps_series
                current_per = per_history.iloc[-1]
                per_mean = per_history.mean()
                per_std = per_history.std()
                if per_std > 0:
                    per_z = (current_per - per_mean) / per_std
                    st.info(f"💡 현재 PER: **{current_per:.1f}x** | 3년 평균 PER: **{per_mean:.1f}x** | **표준편차(Z-Score): {per_z:+.2f} 시그마**")
            else:
                st.info("EPS 데이터가 부족하여 PER 밴드를 그릴 수 없습니다.")
                
        with tab2:
            if bps_series.mean() > 0:
                st.plotly_chart(plot_pbr_band(df_prices, bps_series), use_container_width=True)
                
                pbr_history = df_prices['Close'] / bps_series
                current_pbr = pbr_history.iloc[-1]
                pbr_mean = pbr_history.mean()
                pbr_std = pbr_history.std()
                if pbr_std > 0:
                    pbr_z = (current_pbr - pbr_mean) / pbr_std
                    st.info(f"💡 현재 PBR: **{current_pbr:.1f}x** | 3년 평균 PBR: **{pbr_mean:.1f}x** | **표준편차(Z-Score): {pbr_z:+.2f} 시그마**")
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
        df_dart_raw = pd.read_sql_query("SELECT rcept_no, report_nm, board_parts_krw, pcb_krw, raw_socket_krw, prod_socket_krw, cok_rev, board_rev, socket_rev FROM tfe_dart_v2", conn)
        conn.close()
        
        if not df_dart_raw.empty:
            df_dart_raw['year'] = df_dart_raw['report_nm'].str.extract(r'(\d{4})').astype(int)
            df_dart_raw['month'] = df_dart_raw['report_nm'].str.extract(r'\.(\d{2})\)').astype(int)
            df_dart_raw.sort_values(['year', 'month'], inplace=True)
            
            metric_cols = ['board_parts_krw', 'pcb_krw', 'raw_socket_krw', 'prod_socket_krw', 'cok_rev', 'board_rev', 'socket_rev']
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
            df_standalone['Board_매입'] = df_standalone['board_parts_krw'] + df_standalone['pcb_krw']
            df_standalone['Socket_매입'] = df_standalone['raw_socket_krw'] + df_standalone['prod_socket_krw']
            
            st.markdown("#### 📊 [자동 업데이트] 전자공시 제품별 원재료 매입 및 매출 트래킹 (단일 분기 환산)")
            
            df_table = df_standalone[['기간', 'Board_매입', 'Socket_매입', 'cok_rev', 'board_rev', 'socket_rev']].copy()
            df_table.columns = ['기간', 'Board 매입(백만)', 'Socket 매입(백만)', 'COK 매출(백만)', 'Board 매출(백만)', 'Socket 매출(백만)']
            
            for col in df_table.columns[1:]:
                df_table[col] = df_table[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "-")
                
            st.dataframe(df_table, use_container_width=True)
            
            # 순수 분기 데이터만 차트용으로 필터링
            df_chart = df_standalone[df_standalone['기간'].str.contains('Q$')].copy().reset_index(drop=True)
            
            # Lag 반영 로직
            df_chart['Board_매출_Shifted'] = df_chart['board_rev'].shift(-1)
            
            st.markdown("#### 🎯 제품별 매입-매출 선행지표 상관관계 분석")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Board: +1Q Lag (매입이 1분기 선행)
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=df_chart['기간'], y=df_chart['Board_매입'], name='Board 매입 (당분기)', line=dict(color='blue', width=3)))
                fig1.add_trace(go.Scatter(x=df_chart['기간'], y=df_chart['Board_매출_Shifted'], name='Board 매출 (+1Q 후행)', line=dict(color='red', width=3, dash='dot')))
                fig1.update_layout(title="[+1분기 Lag] Board 매입 vs 다음분기 매출 상관관계", yaxis_title="금액 (백만원)")
                st.plotly_chart(fig1, use_container_width=True)
                
            with col2:
                # Socket: 0Q Lag (동행)
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df_chart['기간'], y=df_chart['Socket_매입'], name='Socket 매입 (당분기)', line=dict(color='purple', width=3)))
                fig2.add_trace(go.Scatter(x=df_chart['기간'], y=df_chart['socket_rev'], name='Socket 매출 (당분기)', line=dict(color='orange', width=3, dash='dot')))
                fig2.update_layout(title="[0분기 Lag] Socket 매입 vs 당분기 매출 상관관계", yaxis_title="금액 (백만원)")
                st.plotly_chart(fig2, use_container_width=True)
                
            st.info("💡 위 데이터는 매일 아침 6시 최신 분기/사업보고서의 '사업의 내용'을 AI(Gemini)가 스크래핑하여 단일 분기로 자동 환산합니다.")
    except Exception as e:
        st.error(f"DART 표 렌더링 중 에러: {e}")
