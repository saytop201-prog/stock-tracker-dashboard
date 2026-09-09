import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = 'tracking.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS estimates (
            date TEXT,
            company TEXT,
            ticker TEXT,
            market_cap INTEGER,
            op_26 REAL,
            np_26 REAL,
            op_27 REAL,
            np_27 REAL,
            PRIMARY KEY (date, ticker)
        )
    ''')
    conn.commit()
    conn.close()

def insert_estimate(date, company, ticker, market_cap, op_26, np_26, op_27, np_27):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO estimates 
        (date, company, ticker, market_cap, op_26, np_26, op_27, np_27)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (date, company, ticker, market_cap, op_26, np_26, op_27, np_27))
    conn.commit()
    conn.close()

def get_historical_estimates(ticker):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query('SELECT * FROM estimates WHERE ticker=? ORDER BY date ASC', conn, params=(ticker,))
    conn.close()
    return df
