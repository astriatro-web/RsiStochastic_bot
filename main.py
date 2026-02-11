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
    watch_list = {
        "005930.KS": "🇰🇷 삼성전자",
        "000660.KS": "🇰🇷 SK하이닉스",
        "GOOGL": "🔍 구글 (GOOGL)",
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
    msg += f"💡 기준: RSI 50 미만 & Stoch 골든크로스\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    hit_names = []  # 매수 신호 포착된 종목명을 담을 리스트
    vix_val = 0

    for ticker, name in watch_list.items():
        try:
            df = yf.download(ticker, period="2mo", interval="1d", progress=False)
            if df.empty: continue
            
            if isinstance(df.columns, pd.MultiIndex):
                series = df['Close'][ticker]
            else:
                series = df['Close']
                
            if ticker == "^VIX":
                vix_val = float(series.iloc[-1])
                continue

            rsi_s, k_s, d_s = get_indicators(series)
            rsi = float(rsi_s.iloc[-1])
            k = float(k_s.iloc[-1])
            d = float(d_s.iloc[-1])
            price = float(series.iloc[-1])

            is_rsi_active = rsi <= 50 
            is_stoch_bottom = k <= 20
            is_golden_cross = k > d and k_s.iloc[-2] <= d_s.iloc[-2]

            if is_rsi_active and (is_stoch_bottom or is_golden_cross):
                status = "🔥 *[매수 적기]*"
                hit_names.append(name) # 종목명 추가
            elif rsi <= 55 or k <= 30:
                status = "⚠️ *[관심 진입]*"
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
    
    # [수정] 포착된 종목이 있으면 목록으로 보여줌
    if hit_names:
        msg += f"📢 *매수 신호 포착 ({len(hit_names)}개):*\n"
        msg += f"👉 " + ", ".join(hit_names)
    else:
        msg += f"📢 포착된 매수 신호 없음"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
