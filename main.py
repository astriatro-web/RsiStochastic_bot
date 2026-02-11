import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime

# 1. 환경 변수 설정
TOKEN = os.environ.get('SNIPER_TOKEN')
CHAT_ID = os.environ.get('MY_PRIVATE_ID')

def get_indicators(series):
    """지표 계산: RSI 14, Stochastic Slow 14,3,3"""
    if len(series) < 20: return 0.0, 0.0, 0.0, 0.0, 0.0
    
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
    
    return float(rsi.iloc[-1]), float(slow_k.iloc[-1]), float(slow_d.iloc[-1]), \
           float(slow_k.iloc[-2]), float(slow_d.iloc[-2])

def run_sniper():
    # 2. 감시 종목 리스트 (7종목 정예 + VIX)
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
    hour = (now.hour + 9) % 24  # KST 변환
    
    msg = f"🎯 *실시간 바닥 정밀 스캔*\n"
    msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')} (KST)\n"
    msg += f"💡 *기준: RSI 40 미만 & Stoch 골든크로스*\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    hit_details = [] 
    vix_val = 0

    for ticker, name in watch_list.items():
        try:
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            if df.empty: continue
            
            if isinstance(df.columns, pd.MultiIndex):
                series = df.xs('Close', axis=1, level=0).iloc[:, 0]
            else:
                series = df['Close']
            
            series = series.dropna()
            current_price = float(series.iloc[-1])

            if ticker == "^VIX":
                vix_val = current_price
                continue

            # 지표 계산 및 30일 지지선 추출
            rsi, k, d, pk, pd_val = get_indicators(series)
            support_price = float(series.tail(30).min())

            status = "💤 관망중"
            unit = "원" if ".KS" in ticker else "$"
            price_str = f"{current_price:,.0f}{unit}" if unit=="원" else f"{current_price:.2f}{unit}"
            support_str = f"{support_price:,.0f}{unit}" if unit=="원" else f"{support_price:.2f}{unit}"

            if rsi > 0:
                is_rsi_ok = rsi <= 40
                is_stoch_ok = (k <= 20) or (k > d and pk <= pd_val)
                
                if is_rsi_ok and is_stoch_ok:
                    status = "🔥 *[매수 적기]*"
                    # 요약 섹션에서 손절가 삭제
                    hit_details.append(f"🔥 *{name}*: {price_str}\n   (RSI:{rsi:.1f} / 지지:{support_str})")
                elif rsi <= 45 or k <= 25:
                    status = "⚠️ *[관심 진입]*"
                    hit_details.append(f"⚠️ *{name}*: {price_str}\n   (예상지지:{support_str})")

            # 전체 리포트 출력
            msg += f"📍 *{name}*\n"
            msg += f"- 현재가: {price_str}\n"
            msg += f"- RSI: *{rsi:.1f}* | Stoch: *{k:.1f}/{d:.1f}*\n"
            msg += f"- 지지선(30일): {support_str}\n"
            msg += f"- 상태: {status}\n\n"

        except Exception as e:
            print(f"Error {ticker}: {e}")

    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🌡️ 시장 공포(VIX): {vix_val:.1f}\n"
    
    if hit_details:
        msg += f"📢 *신호 및 전략 요약:*\n" + "\n".join(hit_details)
    else:
        msg += f"📢 포착된 신호 없음"

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
