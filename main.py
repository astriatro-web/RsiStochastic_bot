import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime

# 설정: 깃허브 Secrets와 정확히 일치해야 함
TOKEN = os.environ.get('SNIPER_TOKEN')
CHAT_ID = os.environ.get('MY_PRIVATE_ID')

def get_indicators(series):
    if len(series) < 20: return 0, 0, 0
    # RSI
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    # Stochastic
    low_min = series.rolling(window=14).min()
    high_max = series.rolling(window=14).max()
    fast_k = 100 * (series - low_min) / (high_max - low_min)
    slow_k = fast_k.rolling(window=3).mean()
    slow_d = slow_k.rolling(window=3).mean()
    return rsi, slow_k, slow_d

def run_sniper():
    watch_list = {
        "005930.KS": "🇰🇷 삼성전자",
        "000660.KS": "🇰🇷 SK하이닉스",
        "RKLB": "🚀 로켓랩",
        "IREN": "⛏️ 아이렌",
        "^VIX": "🌡️ 공포지수"
    }

    msg = f"🎯 *[스나이퍼 리포트]*\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n━━━━━━━━━━━━━━━\n\n"
    hit_count = 0

    for ticker, name in watch_list.items():
        try:
            # 데이터를 하나씩 가져와서 에러 방지
            df = yf.download(ticker, period="1mo", interval="1d", progress=False)
            if df.empty: continue
            
            series = df['Close']
            if ticker == "^VIX":
                vix_val = float(series.iloc[-1])
                continue

            rsi_s, k_s, d_s = get_indicators(series)
            rsi, k, d = float(rsi_s.iloc[-1]), float(k_s.iloc[-1]), float(d_s.iloc[-1])
            price = float(series.iloc[-1])

            is_bottom = rsi <= 35 and (k <= 20 or k > d)
            status = "🔥 매수신호" if is_bottom else "💤 관망"
            if is_bottom: hit_count += 1

            unit = "원" if ".KS" in ticker else "$"
            msg += f"📍 *{name}*\n- {price:,.0f if unit=='원' else 2}{unit} (RSI:{rsi:.1f})\n- 상태: {status}\n\n"
        except Exception as e:
            print(f"Error loading {ticker}: {e}")

    msg += f"━━━━━━━━━━━━━━━\n📢 포착 신호: {hit_count}개"
    
    # 텔레그램 전송
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    res = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    print(f"Telegram response: {res.status_code}")

if __name__ == "__main__":
    run_sniper()
