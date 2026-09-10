import os
import requests
from bs4 import BeautifulSoup
import OpenDartReader
import google.generativeai as genai
import json
import sqlite3

API_KEY = 'c7701951d3927d434089d60e4a0590dc56dc047c'
GEMINI_API_KEY = 'AQ.Ab8RN6K' + 'JrISe1gWRm1vLFbfem-T2ls05fMsL_kTVtRUFI1Bkog'

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

safety_settings = [
    {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
    {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
    {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
    {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'}
]

def init_db():
    conn = sqlite3.connect('tracking.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tfe_dart_v2 (
            rcept_no TEXT UNIQUE,
            report_nm TEXT,
            board_parts_krw INTEGER,
            pcb_krw INTEGER,
            raw_socket_krw INTEGER,
            prod_socket_krw INTEGER,
            cok_rev INTEGER,
            board_rev INTEGER,
            socket_rev INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def main():
    init_db()
    dart = OpenDartReader(API_KEY)
    
    # 최근 2년치 보고서 검색
    try:
        df_reports = dart.list('425420', start='20240101', kind='A')
    except:
        print("DART 검색 실패")
        return
        
    if df_reports is None or df_reports.empty:
        return
        
    conn = sqlite3.connect('tracking.db')
    c = conn.cursor()
    
    # 저장된 rcept_no 가져오기
    c.execute("SELECT rcept_no FROM tfe_dart_v2")
    saved_rcepts = [row[0] for row in c.fetchall()]
    
    for _, row in df_reports.iterrows():
        rcept_no = row['rcept_no']
        report_nm = row['report_nm']
        
        if rcept_no in saved_rcepts:
            continue
            
        print(f"새로운 보고서 발견: {report_nm} ({rcept_no})")
        
        try:
            docs = dart.sub_docs(rcept_no)
            # II. 사업의 내용 추출
            biz_doc = docs[docs['title'].str.contains('II.')].iloc[0]
            res = requests.get(biz_doc['url'])
            soup = BeautifulSoup(res.text, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)[:45000]
            
            prompt = """
            아래는 반도체 테스트 기업 '티에프이'의 보고서 '사업의 내용' 텍스트입니다.
            1. 원재료 매입 현황 표에서 '당기 누적' 매입액을 찾으세요. (품목: BOARD PARTS, PCB, 원재료 SOCKET, 상품 SOCKET)
            2. 주요 제품 매출 현황 표에서 '당기 누적' 매출액을 찾으세요. (품목: COK, Board, Test Socket)
            금액 단위는 반드시 '백만원' 기준 숫자로 반환해주세요. (천원 단위라면 1000으로 나누어 정수로 기재)
            해당 항목이 없거나 '기타'에 뭉뚱그려져 구분할 수 없으면 null 로 기재하세요.
            {
                "board_parts_krw": 숫자,
                "pcb_krw": 숫자,
                "raw_socket_krw": 숫자,
                "prod_socket_krw": 숫자,
                "cok_rev": 숫자,
                "board_rev": 숫자,
                "socket_rev": 숫자
            }
            [텍스트 시작]
            """ + text
            
            response = model.generate_content(prompt, safety_settings=safety_settings)
            res_text = response.text.strip().replace('```json', '').replace('```', '')
            data = json.loads(res_text)
            print(f'Parsed {rcept_no}: {data}')
            
            c.execute('''
                INSERT OR IGNORE INTO tfe_dart_v2 (rcept_no, report_nm, board_parts_krw, pcb_krw, raw_socket_krw, prod_socket_krw, cok_rev, board_rev, socket_rev)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (rcept_no, report_nm, data.get('board_parts_krw'), data.get('pcb_krw'), data.get('raw_socket_krw'), data.get('prod_socket_krw'), data.get('cok_rev'), data.get('board_rev'), data.get('socket_rev')))
            conn.commit()
            print(f"-> 파싱 및 저장 완료: {data}")
            
        except Exception as e:
            print(f"-> 에러 발생: {e}")
            
    conn.close()

if __name__ == '__main__':
    main()
