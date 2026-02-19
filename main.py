import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
from datetime import datetime

# 환경 변수 설정
TOKEN = os.environ.get('SNIPER_TOKEN')
CHAT_ID = os.environ.get('MY_PRIVATE_ID')

def get_indicators(series):
    """지표 계산: RSI 및 Stochastic Slow"""
    if len(series) < 20: return None, None, None
    
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

def analyze_volume_profile(df):
    """매물대 분석: 지지선과 저항선 추출"""
    data = df.tail(60)
    current_price = float(data['Close'].iloc[-1])
    
    # 가격 구간을 15개로 더 세분화하여 분석
    bins = 15
    hist, bin_edges = np.histogram(data['Close'], bins=bins, weights=data['Volume'])
    
    # 거래량 순으로 구간 정렬
    sorted_indices = np.argsort(hist)[::-1]
    
    support = None
    resistance = None
    
    for idx in sorted_indices:
        price_level = (bin_edges[idx] + bin_edges[idx+1]) / 2
        # 현재가보다 아래에 있는 최대 매물대를 지지선으로 설정
        if price_level < current_price and support is None:
            support = price_level
        # 현재가보다 위에 있는 최대 매물대를 저항선으로 설정
        elif price_level > current_price and resistance is None:
            resistance = price_level
            
        if support and resistance: break
            
    return support, resistance

def run_sniper():
    watch_list = {
        "005930.KS": "🇰🇷 삼성전자",
        "000660.KS": "🇰🇷 SK하이닉스",
        "GOOGL": "🔍 구글 (GOOGL)",
        "IONQ": "⚛️ 아이온큐 (IONQ)",
        "BMNR": "⛏️ 비트마인 (BMNR)",
        "RKLB": "🚀 로켓랩 (RKLB)",
        "IREN": "⚡ 아이렌 (IREN)",
        "^VIX": "🌡️ 공포지수"
    }

    now = datetime.now()
    msg = f"🎯 *실시간 매물대 & 바닥 정밀 스캔*\n"
    msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')} (KST)\n"
    msg += f"💡 *기준: 매물대 지지 + RSI 반등 + Stoch 골든크로스*\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    vix_val = 0

    for ticker, name in watch_list.items():
        try:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty: continue
            
            # 멀티 인덱스 대응
            if isinstance(df.columns, pd.MultiIndex):
                close_ser = df['Close'][ticker].dropna()
            else:
                close_ser = df['Close'].dropna()

            current_price = float(close_ser.iloc[-1])

            if ticker == "^VIX":
                vix_val = current_price
                continue

            # 지표 및 매물대 분석
            rsi_series, k_series, d_series = get_indicators(close_ser)
            rsi, k, d = rsi_series.iloc[-1], k_series.iloc[-1], d_series.iloc[-1]
            pk, pd_val = k_series.iloc[-2], d_series.iloc[-2]
            
            support, resistance = analyze_volume_profile(df if not isinstance(df.columns, pd.MultiIndex) else df.xs(ticker, axis=1, level=1))

            # 매수 신호 로직
            is_rsi_ok = (rsi <= 35) or (rsi <= 45 and rsi > rsi_series.iloc[-2])
            is_stoch_ok = (pk <= pd_val and k > d) and k < 40
            is_near_support = support and (current_price <= support * 1.03)
            
            unit = "원" if ".KS" in ticker else "$"
            p_fmt = f"{current_price:,.0f}{unit}" if unit=="원" else f"{current_price:.2f}{unit}"
            s_fmt = f"{support:,.0f}{unit}" if support else "N/A"
            r_fmt = f"{resistance:,.0f}{unit}" if resistance else "N/A"
            if unit == "$":
                s_fmt = f"{support:.2f}{unit}" if support else "N/A"
                r_fmt = f"{resistance:.2f}{unit}" if resistance else "N/A"

            if is_rsi_ok and is_stoch_ok and is_near_support:
                status = "🔥 *[강력 매수 적기]*"
            elif is_rsi_ok and is_stoch_ok:
                status = "✅ *[기술적 반등 지점]*"
            elif rsi <= 40 or is_near_support:
                status = "⚠️ *[관심 진입]*"
            else:
                status = "💤 관망중"

            msg += f"📍 *{name}*\n"
            msg += f"- 현재가: {p_fmt}\n"
            msg += f"- RSI: *{rsi:.1f}* | Stoch: *{k:.1f}/{d:.1f}*\n"
            msg += f"- 지지(매물): {s_fmt}\n"
            msg += f"- 저항(매물): {r_fmt}\n"
            msg += f"- 상태: {status}\n\n"

        except Exception as e:
            print(f"Error {ticker}: {e}")

    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🌡️ 시장 공포(VIX): {vix_val:.1f}\n"
    msg += f"📢 포착된 신호에 따라 대응하세요."

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
