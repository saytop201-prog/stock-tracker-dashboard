import os
import asyncio
import json
from datetime import datetime, timedelta
import pandas as pd
import fitz
import google.generativeai as genai
from telethon import TelegramClient
from pykrx import stock

API_ID = 38368991
API_HASH = '497072150e16946a0bb2bda6e61f9f0b'
GEMINI_API_KEY = 'AQ.Ab8RN6K' + 'JrISe1gWRm1vLFbfem-T2ls05fMsL_kTVtRUFI1Bkog'
PHONE_NUMBER = '+821036092062'
TELEGRAM_CHANNEL = 'sunstudy1234'

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
    prompt = f"[{company}] 리포트입니다. 2026년과 2027년의 예상 실적(컨센서스)을 찾아주세요. 단위는 억원입니다. 찾을 수 없는 데이터는 null로 처리하세요. 반드시 JSON 포맷으로 출력: {{\n\"2026_op\": 숫자,\n\"2026_np\": 숫자,\n\"2027_op\": 숫자,\n\"2027_np\": 숫자\n}}\n[리포트]\n{text_snippet}"
    try:
        response = model.generate_content(prompt)
        res_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(res_text)
    except:
        return {"2026_op": None, "2026_np": None, "2027_op": None, "2027_np": None}

def get_mcap(ticker):
    try:
        import requests
        from bs4 import BeautifulSoup
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

async def main():
    print("텔레그램 클라이언트 시작 중... (인증 번호를 입력 대기 상태가 됩니다)", flush=True)
    client = TelegramClient('anon', API_ID, API_HASH)
    await client.start(phone=PHONE_NUMBER)
    print("인증 완료! 리포트 검색 시작...", flush=True)
    
    os.makedirs('reports', exist_ok=True)
    results = []
    yesterday = datetime.now() - timedelta(days=2)
    
    async for message in client.iter_messages(TELEGRAM_CHANNEL, limit=50):
        if message.date.replace(tzinfo=None) < yesterday:
            continue
        
        found_company = None
        if message.text:
            for company in TARGET_STOCKS.keys():
                if company in message.text:
                    found_company = company
                    break
                    
        if found_company and message.document and message.document.mime_type == 'application/pdf':
            print(f"[{found_company}] 리포트 발견!", flush=True)
            path = await message.download_media(file='reports/')
            text = extract_text_from_pdf(path)
            est = get_estimates(found_company, text)
            ticker = TARGET_STOCKS[found_company]
            mcap = get_mcap(ticker)
            
            op26, np26 = est.get('2026_op'), est.get('2026_np')
            op27, np27 = est.get('2027_op'), est.get('2027_np')
            
            results.append({
                '종목명': found_company, '종목코드': ticker, '시가총액(억)': mcap,
                '26E OP(억)': op26, '26E NP(억)': np26,
                '27E OP(억)': op27, '27E NP(억)': np27,
            })
            
    if results:
        import db_manager
        db_manager.init_db()
        for r in results:
            db_manager.insert_estimate(
                date=r['업데이트 날짜'],
                company=r['종목명'],
                ticker=r['종목코드'],
                market_cap=r['시가총액(억)'],
                op_26=r['26E OP(억)'],
                np_26=r['26E NP(억)'],
                op_27=r['27E OP(억)'],
                np_27=r['27E NP(억)']
            )
        print("데이터베이스(tracking.db) 저장 완료!", flush=True)
    else:
        print("최근 2일 내 타겟 종목 리포트가 없습니다.", flush=True)

if __name__ == '__main__':
    asyncio.run(main())
