import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime

TOKEN = os.environ.get('SNIPER_TOKEN')
CHAT_ID = os.environ.get('MY_PRIVATE_ID')

def get_indicators(series):
    # 데이터가 부족하면 0으로 반환하지 않고 계산 가능한 만큼 최대한 계산
    if len(series) < 15: return 0.0, 0.0, 0.0
    
    # RSI 계산 (정확도 향상)
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Stochastic Slow (바닥 확인용)
    low_min = series.rolling(window=14).min()
    high_max = series.rolling(window=14).max()
    fast_k = 100 * (series - low_min) / (high_max - low_min)
    slow_k = fast_k.rolling(window=3).mean()
    slow_d = slow_k.rolling(window=3).mean()
    
    # 마지막 값이 NaN일 경우를 대비해 처리
    return float(rsi.iloc[-1]), float(slow_k.iloc[-1]), float(slow_d.iloc[-1]), slow_k.iloc[-2], slow_d.iloc[-2]

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
    
    title_type = "🔍 실시간 바닥 정밀 스캔"
    if 5 <= hour <= 10: title_type = "☀️ 미장 마감 & 기상 리포트"
    elif 14 <= hour <= 16: title_type = "☕ 국장 마감 & 오후 전략"
    elif 22 <= hour <= 24: title_type = "🌙 미장 개장 & 야간 점검"

    msg = f"🎯 *{title_type}*\n"
    msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')} (KST)\n"
    msg += f"💡 기준: RSI 50 미만 & Stoch 골든크로스\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    hit_names = []
    vix_val = 0

    for ticker, name in watch_list.items():
        try:
            # 기간을 3개월로 늘려 계산 안정성 확보
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            if df.empty: continue
            
            series = df['Close']
            if isinstance(series, pd.DataFrame): # 멀티인덱스 방어
                series = series[ticker]
            series = series.dropna()

            if ticker == "^VIX":
                vix_val = float(series.iloc[-1])
                continue

            # 지표 계산 결과값 받기
            rsi, k, d, prev_k, prev_d = get_indicators(series)

            # 판정 로직 (RSI 50 미만 + 스토캐스틱 조건)
            is_rsi_active = rsi <= 50 and rsi > 0
            is_stoch_bottom = k <= 20 and k > 0
            is_golden_cross = k > d and prev_k <= prev_d

            if is_rsi_active and (is_stoch_bottom or is_golden_cross):
                status = "🔥 *[매수 적기]*"
                hit_names.append(name)
            elif (0 < rsi <= 55) or (0 < k <= 30):
                status = "⚠️ *[관심 진입]*"
            else:
                status = "💤 관망중"

            unit = "원" if ".KS" in ticker else "$"
            msg += f"📍 *{name}*\n"
            msg += f"- 현재가: {unit}{series.iloc[-1]:,.0f if unit=='원' else 2}\n"
            msg += f"- RSI: *{rsi:.1f}* | Stoch: *{k:.1f}/{d:.1f}*\n"
            msg += f"- 상태: {status}\n\n"

        except Exception as e:
            print(f"Error {ticker}: {e}")

    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🌡️ 시장 공포(VIX): {vix_val:.1f}\n"
    
    if hit_names:
        msg += f"📢 *매수 신호 포착 ({len(hit_names)}개):*\n👉 " + ", ".join(hit_names)
    else:
        msg += f"📢 포착된 매수 신호 없음"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
