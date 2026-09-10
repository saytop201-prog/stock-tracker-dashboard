import os
import time
import json
import requests
import pandas as pd
import fitz
from bs4 import BeautifulSoup
from datetime import datetime
import google.generativeai as genai
from pykrx import stock

GEMINI_API_KEY = 'AQ.Ab8RN6K' + 'JrISe1gWRm1vLFbfem-T2ls05fMsL_kTVtRUFI1Bkog'
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

TARGET_STOCKS = {
    '마이크로컨텍솔': '098120', '티에스이': '131290', '티에프이': '425420', 'ISC': '095340',
    '디아이': '003160', '엑시콘': '092870', '인텍플러스': '064290', '이오테크닉스': '039030',
    '케이씨텍': '281820', '브이엠': '089970', '피에스케이': '319660', '테스': '095610',
    '엠케이전자': '033160', '티엘비': '356860', '심텍': '222800',
    '이엔에프테크놀로지': '102710', '티씨케이': '064760', '하나머티리얼즈': '166090', '엘티씨': '170920',
    'DB하이텍': '000990', '두산': '000150'
}

def get_latest_naver_report(ticker):
    url = f'https://finance.naver.com/research/company_list.naver?searchType=itemCode&itemCode={ticker}'
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.content, 'html.parser')
        file_td = soup.select('.file a')
        if not file_td:
            return None
        return file_td[0]['href']
    except Exception as e:
        print(f"Error fetching report list for {ticker}: {e}")
        return None

def download_pdf(url, filename):
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    with open(filename, 'wb') as f:
        f.write(res.content)

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"PDF 에러: {e}")
        return ""

def get_estimates(company, text):
    text_snippet = text[:35000]
    prompt = f"[{company}] 종목 리포트입니다. 리포트를 발행한 증권사명과, 2026년/2027년 예상 실적(컨센서스)을 찾아주세요. 단위는 억원입니다. 찾을 수 없는 데이터는 null로 처리. 반드시 JSON 포맷 출력: {{\n\"broker\": \"증권사명\",\n\"2026_op\": 숫자,\n\"2026_np\": 숫자,\n\"2027_op\": 숫자,\n\"2027_np\": 숫자\n}}\n[리포트]\n{text_snippet}"
    try:
        response = model.generate_content(prompt)
        res_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(res_text)
    except Exception as e:
        print(f"Gemini 에러: {e}")
        return {"broker": "Unknown", "2026_op": None, "2026_np": None, "2027_op": None, "2027_np": None}

def get_mcap(ticker):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={ticker}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        mcap_em = soup.select_one('#_market_sum')
        if mcap_em:
            mcap_str = mcap_em.text.replace(',', '').replace('\t', '').replace('\n', '').strip()
            if '조' in mcap_str:
                parts = mcap_str.split('조')
                tril = int(parts[0].strip())
                bil = int(parts[1].strip()) if len(parts)>1 and parts[1].strip() else 0
                return tril * 10000 + bil
            else:
                return int(mcap_str.strip())
        return None
    except:
        return None

def main():
    print("네이버 증권 리포트 1회성 초기화 스크립트 시작...", flush=True)
    os.makedirs('naver_reports', exist_ok=True)
    results = []
    
    import db_manager
    db_manager.init_db()

    for idx, (company, ticker) in enumerate(TARGET_STOCKS.items()):
        print(f"[{idx+1}/{len(TARGET_STOCKS)}] {company} ({ticker}) 분석 중...", flush=True)
        pdf_url = get_latest_naver_report(ticker)
        if not pdf_url:
            print(f"  -> 리포트 없음", flush=True)
            continue
            
        pdf_path = f"naver_reports/{ticker}.pdf"
        try:
            download_pdf(pdf_url, pdf_path)
            text = extract_text_from_pdf(pdf_path)
            est = get_estimates(company, text)
            mcap = get_mcap(ticker)
            
            broker = est.get('broker', 'Unknown')
            op26, np26 = est.get('2026_op'), est.get('2026_np')
            op27, np27 = est.get('2027_op'), est.get('2027_np')
            
            db_manager.insert_estimate(
                date=datetime.today().strftime("%Y-%m-%d"),
                broker=broker,
                company=company,
                ticker=ticker,
                market_cap=mcap,
                op_26=op26,
                np_26=np26,
                op_27=op27,
                np_27=np27
            )
            print(f"  -> 완료 [{broker}] (26E OP: {op26}, 27E OP: {op27})", flush=True)
        except Exception as e:
            print(f"  -> 에러 발생: {e}", flush=True)
            
        time.sleep(2) 
        
    print("데이터베이스(tracking.db) 저장 완료!", flush=True)

if __name__ == '__main__':
    main()
