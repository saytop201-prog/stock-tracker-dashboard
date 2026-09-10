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
    'DB하이텍': '000990', '티에프이': '425420', '마이크로컨텍솔': '098120', '디아이': '131290', 'ISC': '095340',
    '디아이티': '003160', '엑시콘': '092870', '인텍플러스': '064290', '네오셈': '253590', '에이팩트': '200470',
    '오로스테크놀로지': '322310', '넥스틴': '348210', '파크시스템스': '140860', '기가비스': '420770',
    '엠로': '058970', '에스피지': '058610', '유일로보틱스': '388720', '에스비비테크': '389500',
    '원익IPS': '240810', '피에스케이': '319660', '테스': '095610',
    '엠케이전자': '033160', '티엘비': '356860', '심텍': '222800',
    '이엔에프테크놀로지': '102710', '티씨케이': '064760', '하나머티리얼즈': '166090', '원익머트리얼즈': '104830',
    '월덱스': '101160', '케이엔제이': '272110', '동진쎄미켐': '005290', '솔브레인': '357780'
}

st.set_page_config(page_title="소부장 트래킹 대시보드", layout="wide")



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
        
        # TFE(425420) 하드코딩 2027/2028 FnGuide 실적 연동
        if ticker == '425420':
            col_27 = [2085, 510, 467, 24.48, 22.40, 23.15, 24.07, None, None, 3713, 14.38, 18018, 2.96, None, None, None]
            col_28 = [2704, 699, 591, 25.85, 21.86, 23.55, 21.24, None, None, 4787, 11.16, 22836, 2.34, None, None, None]
            df_annual['2027.12(E)'] = col_27[:len(df_annual)]
            df_annual['2028.12(E)'] = col_28[:len(df_annual)]
            
        # DB하이텍(000990) 하드코딩 2027/2028 FnGuide 실적 연동
        elif ticker == '000990':
            col_27 = [18585, 5525, 4930, 29.73, 26.53, 17.89, 21.48, None, None, 11303, 9.86, 69879, 1.60, None, None, None]
            col_28 = [20130, 7010, 5880, 34.82, 29.21, 17.98, 23.35, None, None, 13481, 8.27, 83850, 1.33, None, None, None]
            df_annual['2027.12(E)'] = col_27[:len(df_annual)]
            df_annual['2028.12(E)'] = col_28[:len(df_annual)]
            
        return df_annual
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_daily_prices(ticker, years=3):
    start_date = datetime.datetime.now() - datetime.timedelta(days=365 * years)
    df = fdr.DataReader(ticker, start_date)
    return df

@st.cache_data(ttl=3600)
def get_current_market_data(ticker):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={ticker}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        mcap_str = soup.select_one('#_market_sum').text.replace('\t', '').replace('\n', '').replace(',', '')
        mcap = int(mcap_str) if mcap_str.isdigit() else None
        
        # 주가
        price_str = soup.select_one('.no_today .blind').text.replace(',', '')
        price = int(price_str) if price_str.isdigit() else None
        return mcap, price
    except:
        return None, None

st.title("📈 반도체 소부장 트래킹 대시보드")
st.sidebar.header("종목 선택")
selected_company = st.sidebar.selectbox("종목을 선택하세요", list(TARGET_STOCKS.keys()))
ticker = TARGET_STOCKS[selected_company]

st.header(f"[{ticker}] {selected_company}")
kst = datetime.timezone(datetime.timedelta(hours=9))
now_str = datetime.datetime.now(kst).strftime("%Y-%m-%d %H:%M")
st.markdown(f"**🕒 Market data as of: {now_str} KST**")

df_estimates = db_manager.get_historical_estimates(ticker)
df_brokers = db_manager.get_estimates_by_broker(ticker)
df_financials = get_historical_financials(ticker)

mcap, current_price = get_current_market_data(ticker)

# --- 1. Top Summary Cards (NTM & 분리된 컨센서스) ---
op26_mkt, op27_mkt, eps26_mkt, eps27_mkt = None, None, None, None
op28_single, eps28_single = None, None

if not df_financials.empty:
    try:
        for col in df_financials.columns:
            if '2026' in col and '(E)' in col:
                op26_mkt = float(str(df_financials.loc['영업이익', col]).replace(',', ''))
                eps26_mkt = float(str(df_financials.loc['EPS(원)', col]).replace(',', ''))
            if '2027' in col and '(E)' in col:
                op27_mkt = float(str(df_financials.loc['영업이익', col]).replace(',', ''))
                eps27_mkt = float(str(df_financials.loc['EPS(원)', col]).replace(',', ''))
            if '2028' in col and '(E)' in col:
                op28_single = float(str(df_financials.loc['영업이익', col]).replace(',', ''))
                eps28_single = float(str(df_financials.loc['EPS(원)', col]).replace(',', ''))
    except:
        pass

# NTM 계산 (일할 계산)
ntm_eps, ntm_op = None, None
if pd.notnull(eps26_mkt) and pd.notnull(eps27_mkt) and pd.notnull(op26_mkt) and pd.notnull(op27_mkt):
    today = datetime.datetime.now(kst).date()
    end_of_year = datetime.date(today.year, 12, 31)
    days_in_year = 365 if today.year % 4 != 0 else 366
    days_left = (end_of_year - today).days
    w_cur = days_left / days_in_year
    w_next = 1.0 - w_cur
    
    ntm_eps = (eps26_mkt * w_cur) + (eps27_mkt * w_next)
    ntm_op = (op26_mkt * w_cur) + (op27_mkt * w_next)

col1, col2, col3, col4 = st.columns(4)
col1.metric("시가총액", f"{mcap:,.0f} 억" if pd.notnull(mcap) else "N/A")
col2.metric("NTM 영업이익 (시장 컨센서스)", f"{ntm_op:,.0f} 억" if pd.notnull(ntm_op) else "N/A")
col3.metric("NTM EPS (시장 컨센서스)", f"{ntm_eps:,.0f} 원" if pd.notnull(ntm_eps) else "N/A")

ntm_per = round(current_price / ntm_eps, 2) if pd.notnull(current_price) and pd.notnull(ntm_eps) and ntm_eps > 0 else "N/A"
ntm_por = round(mcap / ntm_op, 2) if pd.notnull(mcap) and pd.notnull(ntm_op) and ntm_op > 0 else "N/A"
col4.metric("NTM PER / POR", f"{ntm_per}배 / {ntm_por}배")

if pd.notnull(op28_single):
    st.caption("※ 2028E 실적(영업이익 699억)은 오래된 단일 기관 추정치이므로 신뢰도가 낮습니다.")

st.divider()

# --- 2. Historical Key Financials & YoY Growth ---
col_fin, col_yoy = st.columns([2, 1])
with col_fin:
    st.subheader("📊 Historical & Forecast Financials")
    if not df_financials.empty:
        st.dataframe(df_financials, use_container_width=True)
    else:
        st.info("데이터를 불러올 수 없습니다.")

with col_yoy:
    st.subheader("🚀 영업이익 YoY(%) 상승률")
    if not df_financials.empty:
        try:
            op_25_str = str(df_financials.loc['영업이익'].iloc[2])
            op_25 = float(op_25_str.replace(',', '')) if op_25_str not in ['NaN', 'nan', '-'] else None
            
            yoy_data = []
            if pd.notnull(op_25) and pd.notnull(op26_mkt) and op_25 > 0:
                yoy_26 = ((op26_mkt / op_25) - 1) * 100
                yoy_data.append({"연도": "2026E", "영업이익(억)": round(op26_mkt), "YoY (%)": f"+{yoy_26:.1f}%" if yoy_26 > 0 else f"{yoy_26:.1f}%"})
            if pd.notnull(op26_mkt) and pd.notnull(op27_mkt) and op26_mkt > 0:
                yoy_27 = ((op27_mkt / op26_mkt) - 1) * 100
                yoy_data.append({"연도": "2027E", "영업이익(억)": round(op27_mkt), "YoY (%)": f"+{yoy_27:.1f}%" if yoy_27 > 0 else f"{yoy_27:.1f}%"})
            if pd.notnull(op27_mkt) and pd.notnull(op28_single) and op27_mkt > 0:
                yoy_28 = ((op28_single / op27_mkt) - 1) * 100
                yoy_data.append({"연도": "2028E", "영업이익(억)": round(op28_single), "YoY (%)": f"+{yoy_28:.1f}%" if yoy_28 > 0 else f"{yoy_28:.1f}%"})
                
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
if not df_brokers.empty:
    n_brokers = len(df_brokers)
    title_text = f"🏢 증권사별 리포트 컨센서스 (최근 공개 추정치, N={n_brokers})" if n_brokers == 1 else f"🏢 증권사별 리포트 컨센서스 (단순 평균, N={n_brokers})"
    st.subheader(title_text)
    
    if n_brokers > 1:
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
    else:
        df_disp = df_brokers.copy()
        
    df_disp.columns = ['증권사', '목표주가(원)', '26E 영업이익', '26E 순이익', '27E 영업이익', '27E 순이익', '업데이트 일자']
    
    for col in ['목표주가(원)', '26E 영업이익', '26E 순이익', '27E 영업이익', '27E 순이익']:
        df_disp[col] = df_disp[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "-")
        
    st.dataframe(df_disp, use_container_width=True)
else:
    st.subheader("🏢 증권사별 리포트 컨센서스")
    st.info("수집된 증권사 리포트가 없습니다.")

st.divider()

def get_historical_metrics(df_price, df_fin, forward_12m=True):
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
        next_y_str = str(date.year + 1)
        month = date.month
        
        cur_eps = year_eps.get(y_str)
        cur_bps = year_bps.get(y_str)
        next_eps = year_eps.get(next_y_str)
        next_bps = year_bps.get(next_y_str)
        
        # NTM (Next Twelve Months) 일할 계산
        if forward_12m:
            days_in_year = 365 if date.year % 4 != 0 else 366
            end_of_year = datetime.date(date.year, 12, 31)
            days_left = (end_of_year - date.date()).days
            w_cur = days_left / days_in_year
            w_next = 1.0 - w_cur
            
            if pd.notnull(cur_eps) and pd.notnull(next_eps):
                eps_series[date] = (cur_eps * w_cur) + (next_eps * w_next)
            elif pd.notnull(cur_eps):
                eps_series[date] = cur_eps
            elif pd.notnull(year_eps.get(str(date.year - 1))):
                eps_series[date] = year_eps.get(str(date.year - 1))
                
            if pd.notnull(cur_bps) and pd.notnull(next_bps):
                bps_series[date] = (cur_bps * w_cur) + (next_bps * w_next)
            elif pd.notnull(cur_bps):
                bps_series[date] = cur_bps
            elif pd.notnull(year_bps.get(str(date.year - 1))):
                bps_series[date] = year_bps.get(str(date.year - 1))
        else:
            if pd.notnull(cur_eps):
                eps_series[date] = cur_eps
            elif pd.notnull(year_eps.get(str(date.year - 1))):
                eps_series[date] = year_eps.get(str(date.year - 1))
                
            if pd.notnull(cur_bps):
                bps_series[date] = cur_bps
            elif pd.notnull(year_bps.get(str(date.year - 1))):
                bps_series[date] = year_bps.get(str(date.year - 1))
                
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
    fig.update_layout(title="Historical PER Band (12M Fwd EPS 기준)", xaxis_title="날짜", yaxis_title="주가 (원)")
    return fig

def plot_pbr_band(df, bps_series, pbr_multiples=[1, 2, 3, 4, 5]):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='주가', line=dict(color='black', width=2)))
    colors = ['#FF9999', '#FFCC99', '#FFFF99', '#CCFF99', '#99FF99']
    for pbr, color in zip(pbr_multiples, colors):
        fig.add_trace(go.Scatter(x=df.index, y=bps_series * pbr, name=f'{pbr}x', line=dict(color=color, dash='dash')))
    fig.update_layout(title="Historical PBR Band (12M Fwd BPS 기준)", xaxis_title="날짜", yaxis_title="주가 (원)")
    return fig

# --- 4. Forward EPS 기반 고정 PER/PBR 적정주가 밴드 ---
st.subheader("📈 Forward EPS 기반 고정 PER/PBR 적정주가 밴드 & Z-Score (12M FWD, 최근 3년)")
st.warning("⚠️ Valuation confidence: Low to Medium | 사유: 컨센서스 N=2, 선행 Multiple 이력 약 1년")

df_prices = get_daily_prices(ticker, years=3)

if not df_prices.empty and not df_financials.empty:
    try:
        eps_series, bps_series = get_historical_metrics(df_prices, df_financials)
        
        tab1, tab2 = st.tabs(["PER 밴드", "PBR 밴드"])
        
        with tab1:
            if eps_series.mean() > 0:
                st.plotly_chart(plot_per_band(df_prices, eps_series), use_container_width=True)
                
                per_history = (df_prices['Close'] / eps_series).dropna()
                if not per_history.empty:
                    current_per = per_history.iloc[-1]
                    per_median = per_history.median()
                    per_mad = (per_history - per_median).abs().median()
                    
                    robust_z = (current_per - per_median) / (1.4826 * per_mad) if per_mad > 0 else 0
                    percentile = (per_history < current_per).mean() * 100
                    median_premium = (current_per / per_median - 1) * 100
                    
                    st.info(f"💡 **NTM PER 지표**: 현재 **{current_per:.1f}x** | 역사적 중앙값 대비 **{median_premium:+.1f}%**\n\n"
                            f"**Percentile: {percentile:.1f}%** (과거 어느 위치인지) | **Robust Z-Score: {robust_z:+.2f}**")
            else:
                st.info("EPS 데이터가 부족하여 PER 밴드를 그릴 수 없습니다.")
                
        with tab2:
            if bps_series.mean() > 0:
                st.plotly_chart(plot_pbr_band(df_prices, bps_series), use_container_width=True)
                
                pbr_history = (df_prices['Close'] / bps_series).dropna()
                if not pbr_history.empty:
                    current_pbr = pbr_history.iloc[-1]
                    pbr_median = pbr_history.median()
                    pbr_mad = (pbr_history - pbr_median).abs().median()
                    
                    robust_z_pbr = (current_pbr - pbr_median) / (1.4826 * pbr_mad) if pbr_mad > 0 else 0
                    percentile_pbr = (pbr_history < current_pbr).mean() * 100
                    median_premium_pbr = (current_pbr / pbr_median - 1) * 100
                    
                    st.info(f"💡 **NTM PBR 지표**: 현재 **{current_pbr:.1f}x** | 역사적 중앙값 대비 **{median_premium_pbr:+.1f}%**\n\n"
                            f"**Percentile: {percentile_pbr:.1f}%** (과거 어느 위치인지) | **Robust Z-Score: {robust_z_pbr:+.2f}**")
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
    현재 컨센서스(2027E EPS 3,660원)는 추정 기관 수가 적어 신사업 가정에 매우 민감합니다. 만약 해당 컨센서스에 아직 미반영된 마이크론향 SOCAMM 및 광통신(CPO) 테스트 소켓 매출 순증을 가정할 경우, EPS 추가 상향 시나리오는 다음과 같습니다.
    * **Base 시나리오 (+8.7% 업사이드)**: 기존 사업 실적 + 신사업 순증 200억 추가 ➡️ **조정 EPS 3,977원**
    * **Bull 시나리오 (+20.8% 업사이드)**: 기존 사업 실적 + 신사업 순증 400억 추가 ➡️ **조정 EPS 4,422원**
    
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
            
            # 수학적 상관계수 검증 (NaN 제거)
            df_board_corr = df_chart[['기간', 'Board_매입', 'Board_매출_Shifted']].dropna()
            r_board = df_board_corr['Board_매입'].corr(df_board_corr['Board_매출_Shifted']) if not df_board_corr.empty else 0
            rho_board = df_board_corr['Board_매입'].corr(df_board_corr['Board_매출_Shifted'], method='spearman') if not df_board_corr.empty else 0
            n_board = len(df_board_corr)
            
            df_socket_corr = df_chart[['기간', 'Socket_매입', 'socket_rev']].dropna()
            r_socket = df_socket_corr['Socket_매입'].corr(df_socket_corr['socket_rev']) if not df_socket_corr.empty else 0
            n_socket = len(df_socket_corr)
            
            st.markdown("#### 🎯 제품별 매입-매출 선행지표 상관관계 분석")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Board: +1Q Lag (매입이 1분기 선행)
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=df_board_corr['기간'], y=df_board_corr['Board_매입'], name='Board 매입 (당분기)', line=dict(color='blue', width=3)))
                fig1.add_trace(go.Scatter(x=df_board_corr['기간'], y=df_board_corr['Board_매출_Shifted'], name='Board 매출 (+1Q 후행)', line=dict(color='red', width=3, dash='dot')))
                fig1.update_layout(title=f"[+1분기 Lag] Board 매입 vs 다음분기 매출<br><sup>Pearson r = {r_board:.2f} | Spearman ρ = {rho_board:.2f} (N={n_board})</sup>", yaxis_title="금액 (백만원)")
                st.plotly_chart(fig1, use_container_width=True)
                
            with col2:
                # Socket: 0Q Lag (동분기 동행)
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df_socket_corr['기간'], y=df_socket_corr['Socket_매입'], name='Socket 매입 (당분기)', line=dict(color='green', width=3)))
                fig2.add_trace(go.Scatter(x=df_socket_corr['기간'], y=df_socket_corr['socket_rev'], name='Socket 매출 (당분기)', line=dict(color='orange', width=3, dash='dot')))
                fig2.update_layout(title=f"[0분기 Lag] Socket 매입 vs 당분기 매출<br><sup>Pearson r = {r_socket:.2f} (N={n_socket}) | 신뢰도: Low</sup>", yaxis_title="금액 (백만원)")
                st.plotly_chart(fig2, use_container_width=True)
                st.caption("⚠️ [Low Confidence 사유] 2025년 이전 Socket 매출은 별도재무제표 기준, 이후는 연결 기준이 혼합되어 있어 우상향 상관관계가 과장됐을 가능성이 큽니다.")
                
            st.info("💡 위 데이터는 매일 아침 6시 최신 분기/사업보고서의 '사업의 내용'을 AI(Gemini)가 스크래핑하여 단일 분기로 자동 환산합니다.")
    except Exception as e:
        st.error(f"DART 데이터 렌더링 중 에러: {e}")

    # --- 6. 다음분기 실적 체크리스트 ---
    st.markdown("""
    <br>

    ### 📋 다음분기 실적 체크리스트 (가동률 대체지표)
    회사가 신규공장 및 Socket 증설(월 25K → 50K)에 대한 실제 가동률을 공개하지 않으므로, 다음분기 실적 발표 시 아래 대체지표들을 통해 램프업 상황을 검증해야 합니다.

    | 지표 | 🟢 긍정적 신호 (가동률 상승/정상화) | 🔴 부정적 신호 (램프업 지연/고정비 부담) |
    |---|---|---|
    | **분기 Test Socket 매출** | 120억~150억원 이상 유지 | 100억원 미만 재하락 |
    | **Socket 수출** | 전년 대비 고성장 지속 | 증가세 급격히 둔화 |
    | **원재료 Socket 매입** | 자체생산용 구매 증가 | 상품 Socket만 증가 |
    | **상품 Socket 비중** | 자체 생산과 균형 | 상품 비중만 지속 상승 |
    | **재고자산** | 매출과 함께 원활히 회전 | 매출 정체 속 재고만 급증 |
    | **영업이익률** | 18% 이상 유지 | 15% 이하로 하락 |
    | **건설중인자산** | 본계정(기계장치 등) 대체 후 감소 | 다시 큰 폭으로 증가 |
    | **기계장치** | 증가 후 매출 동반 상승 | 기계장치만 늘어나고 매출 정체 |
    | **감가상각비** | 매출 증가로 비용 흡수 | 마진 하락의 주 요인으로 작용 |
    
    > **💡 Valuation 핵심 포인트**: 신공장 건설과 Socket 설비 도입(약 248.5억)은 사실상 완료되었습니다. 현재 차입금 차감 후 순유동성이 풍부해 일반 유상증자 위험은 낮으나, 26년 3분기~27년 상반기에 **Socket 매출·수출·마진이 월 50K CAPA 확대를 정당화하는 속도로 증가하는지** 확인하는 것이 핵심입니다.
    """)
