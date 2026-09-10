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
            broker TEXT,
            company TEXT,
            ticker TEXT,
            tp REAL,
            market_cap INTEGER,
            rev_26 REAL,
            op_26 REAL,
            np_26 REAL,
            rev_27 REAL,
            op_27 REAL,
            np_27 REAL,
            PRIMARY KEY (date, ticker, broker)
        )
    ''')
    conn.commit()
    conn.close()

def insert_estimate(date, broker, company, ticker, market_cap, op_26, np_26, op_27, np_27):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO estimates 
        (date, broker, company, ticker, market_cap, op_26, np_26, op_27, np_27)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (date, broker, company, ticker, market_cap, op_26, np_26, op_27, np_27))
    conn.commit()
    conn.close()

def get_historical_estimates(ticker):
    conn = sqlite3.connect(DB_NAME)
    # Average across all brokers for a specific date
    query = '''
        SELECT date, 
               AVG(market_cap) as market_cap,
               AVG(op_26) as op_26, 
               AVG(np_26) as np_26, 
               AVG(op_27) as op_27, 
               AVG(np_27) as np_27
        FROM estimates 
        WHERE ticker = ? 
        GROUP BY date
        ORDER BY date ASC
    '''
    df = pd.read_sql_query(query, conn, params=(ticker,))
    conn.close()
    return df

def get_estimates_by_broker(ticker):
    conn = sqlite3.connect(DB_NAME)
    # Get the latest estimate from each broker
    query = '''
        SELECT broker, tp, op_26, np_26, op_27, np_27, date
        FROM estimates
        WHERE ticker = ?
        ORDER BY date DESC
    '''
    df = pd.read_sql_query(query, conn, params=(ticker,))
    conn.close()
    
    if not df.empty:
        # Drop duplicates to keep only the latest per broker
        df = df.drop_duplicates(subset=['broker'], keep='first')
    return df
