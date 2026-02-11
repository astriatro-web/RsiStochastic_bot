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
    # 감시 종목 리스트 (티커 수정 완료: BMNR)
    watch_list = {
        "005930.KS": "🇰🇷 삼성전자",
        "000660.KS": "🇰🇷 SK하이닉스",
        "IONQ": "⚛️ 아이온큐 (IONQ)",
        "BMNR": "⛏️ 비트마이닝 (BMNR)",
        "RKLB": "🚀 로켓랩 (RKLB)",
        "IREN": "⚡ 아이렌 (IREN)",
        "^VIX": "🌡️ 공포지수"
    }

    now = datetime.now()
    hour = (now.hour + 9) % 24

    if 5 <= hour <= 10:
        title_type = "☀️ 미장 마감 & 기상 리포트"
    elif 14 <= hour <= 16:
        title_type = "☕ 국장 마감 & 오후 전략"
    elif 22 <= hour <= 24:
        title_type = "🌙 미장 개장 & 야간 점검"
    else:
        title_type = "🔍 실시간 바닥 정밀 스캔"

    msg = f"🎯 *{title_type}*\n"
    msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')} (KST)\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    hit_count = 0
    vix_val = 0

    for ticker, name in watch_list.items():
        try:
            # BMNR 등 미장 종목 데이터를 위해 최근 1달치 로드
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

            # 바닥 판정 로직
            is_rsi_bottom = rsi <= 35
            is_stoch_bottom = k <= 20
            is_golden_cross = k > d and k_s.iloc[-2] <= d_s.iloc[-2]

            if is_rsi_bottom and (is_stoch_bottom or is_golden_cross):
                status = "🔥 *[강력매수]*"
                hit_count += 1
            elif rsi <= 40 or k <= 25:
                status = "⚠️ *[주의관찰]*"
            else:
                status = "💤 관망중"

            unit = "원" if ".KS" in ticker else "$"
            msg += f"📍 *{name}*\n"
            msg += f"- 현재가: {unit}{price:,.0f if unit=='원' else 2}\n"
            msg += f"- RSI: {rsi:.1f} | Stoch: {k:.1f}/{d:.1f}\n"
            msg += f"- 상태: {status}\n\n"

        except Exception as e:
            print(f"Error: {ticker} -> {e}")

    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🌡️ 시장 공포(VIX): {vix_val:.1f}\n"
    msg += f"📢 포착된 바닥 타점: *{hit_count}개*"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
