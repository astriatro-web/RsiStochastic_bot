import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime

# 설정: 깃허브 Secrets와 매칭
TOKEN = os.environ.get('SNIPER_TOKEN')
CHAT_ID = os.environ.get('MY_PRIVATE_ID')

def get_indicators(series, rsi_period=14, stoch_period=14, k_period=3, d_period=3):
    # RSI 계산
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    # Stochastic (Slow) 계산
    low_min = series.rolling(window=stoch_period).min()
    high_max = series.rolling(window=stoch_period).max()
    fast_k = 100 * (series - low_min) / (high_max - low_min)
    slow_k = fast_k.rolling(window=k_period).mean()
    slow_d = slow_k.rolling(window=d_period).mean()
    
    return rsi, slow_k, slow_d

def run_sniper():
    # 사용자 지정 정예 종목 (국장/미장)
    watch_list = {
        "005930.KS": "🇰🇷 삼성전자",
        "000660.KS": "🇰🇷 SK하이닉스",
        "RKLB": "🚀 로켓랩 (RKLB)",
        "IREN": "⛏️ 아이렌 (IREN)",
        "^VIX": "🌡️ 공포지수"
    }

    data = yf.download(list(watch_list.keys()), period="2y", interval="1d", progress=False)['Close']
    vix = data["^VIX"].iloc[-1]
    
    # 시간대 판별 (한국 시간 기준)
    now_hour = (datetime.now().hour + 9) % 24 
    header = "🇰🇷 국장 마감 브리핑" if 14 <= now_hour <= 17 else "🇺🇸 미장 마감 브리핑"

    msg = f"🎯 *{header} (RSI+Stoch)*\n"
    msg += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    hit_count = 0
    for ticker, name in watch_list.items():
        if ticker == "^VIX": continue
        
        series = data[ticker].dropna()
        rsi_series, k_series, d_series = get_indicators(series)
        
        price = series.iloc[-1]
        rsi = rsi_series.iloc[-1]
        k = k_series.iloc[-1]
        d = d_series.iloc[-1]
        
        # [매수 조건]
        # 1. RSI 35 이하 (과매도)
        # 2. Stochastic K, D가 모두 20 이하 (바닥권) 또는 K가 D를 상향 돌파 (골든크로스)
        is_rsi_bottom = rsi <= 35
        is_stoch_bottom = k <= 20 and d <= 20
        is_golden_cross = k > d and k_series.iloc[-2] <= d_series.iloc[-2]
        
        status = "💤 관망"
        if is_rsi_bottom and (is_stoch_bottom or is_golden_cross):
            status = "🔥 [강력 매수 신호] 바닥 반등!"
            hit_count += 1
        elif is_rsi_bottom or is_stoch_bottom:
            status = "⚠️ [주의] 바닥권 진입 중"

        unit = "원" if ".KS" in ticker else "$"
        msg += f"📍 *{name}*\n"
        msg += f"- 현재가: {unit}{price:,.0f if unit=='원' else 2}\n"
        msg += f"- RSI: {rsi:.1f} | K: {k:.1f} / D: {d:.1f}\n"
        msg += f"👉 결과: *{status}*\n\n"

    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🌡️ 시장 공포(VIX): {vix:.1f}\n"
    msg += f"📢 포착된 바닥 타점: {hit_count}개"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
