import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime

TOKEN = os.environ.get('SNIPER_TOKEN')
CHAT_ID = os.environ.get('MY_PRIVATE_ID')

def get_indicators(series):
    if len(series) < 20: return 0, 0, 0
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    low_min = series.rolling(window=14).min()
    high_max = series.rolling(window=14).max()
    fast_k = 100 * (series - low_min) / (high_max - low_min)
    slow_k = fast_k.rolling(window=3).mean()
    slow_d = slow_k.rolling(window=3).mean()
    return rsi, slow_k, slow_d

def run_sniper():
    # 감시 종목 리스트
    watch_list = {
        "005930.KS": "🇰🇷 삼성전자",
        "000660.KS": "🇰🇷 SK하이닉스",
        "RKLB": "🚀 로켓랩",
        "IREN": "⛏️ 아이렌",
        "^VIX": "🌡️ 공포지수"
    }

    # 헤더 설정
    now = datetime.now()
    now_hour = (now.hour + 9) % 24
    header = "🇰🇷 국장 마감 브리핑" if 14 <= now_hour <= 17 else "🇺🇸 미장 마감 브리핑"

    msg = f"🎯 *{header}*\n"
    msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')}\n"
    msg += f"🔍 *현재 감시 종목 현황*\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    hit_count = 0
    vix_val = 0

    for ticker, name in watch_list.items():
        try:
            df = yf.download(ticker, period="1mo", interval="1d", progress=False)
            if df.empty: continue
            
            series = df['Close']
            if ticker == "^VIX":
                vix_val = float(series.iloc[-1])
                continue

            rsi_s, k_s, d_s = get_indicators(series)
            rsi = float(rsi_s.iloc[-1])
            k = float(k_s.iloc[-1])
            d = float(d_s.iloc[-1])
            price = float(series.iloc[-1])

            # 매수 조건 판정
            is_rsi_bottom = rsi <= 35
            is_stoch_bottom = k <= 20
            is_golden_cross = k > d and k_s.iloc[-2] <= d_s.iloc[-2]

            # 상태 메시지 결정
            if is_rsi_bottom and (is_stoch_bottom or is_golden_cross):
                status = "🔥 *[강력매수]*"
                hit_count += 1
            elif rsi <= 40 or k <= 25:
                status = "⚠️ *[주의깊게 관찰]*"
            else:
                status = "💤 관망 중"

            unit = "원" if ".KS" in ticker else "$"
            msg += f"📍 *{name}*\n"
            msg += f"- 현재가: {price:,.0f if unit=='원' else 2}{unit}\n"
            msg += f"- RSI: {rsi:.1f} | Stoch: {k:.1f}/{d:.1f}\n"
            msg += f"- 상태: {status}\n\n"

        except Exception as e:
            print(f"Error: {ticker} -> {e}")

    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🌡️ 시장 공포(VIX): {vix_val:.1f}\n"
    msg += f"📢 포착된 반등 신호: *{hit_count}개*"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
