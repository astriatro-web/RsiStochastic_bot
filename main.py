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
    """지표 계산: RSI 및 Stochastic Slow 골든크로스 체크"""
    if len(series) < 20: return 0, 0, 0, 0, 0
    
    # RSI (14)
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Stochastic Slow (14, 3, 3)
    low_min = series.rolling(window=14).min()
    high_max = series.rolling(window=14).max()
    fast_k = 100 * (series - low_min) / (high_max - low_min)
    slow_k = fast_k.rolling(window=3).mean()
    slow_d = slow_k.rolling(window=3).mean()
    
    return rsi, slow_k, slow_d

def get_volume_support(df):
    """매물대 분석: 최근 60일 거래량 기반 최대 매물대 가격 산출"""
    # 최근 60일 데이터 사용
    data = df.tail(60)
    # 가격 구간을 10개로 나눔
    bins = 10
    hist, bin_edges = np.histogram(data['Close'], bins=bins, weights=data['Volume'])
    
    # 가장 거래량이 많이 터진 구간의 인덱스
    max_vol_idx = np.argmax(hist)
    # 해당 구간의 중간 가격을 지지선으로 반환
    support_price = (bin_edges[max_vol_idx] + bin_edges[max_vol_idx+1]) / 2
    return float(support_price)

def run_sniper():
    watch_list = {
        "005930.KS": "🇰🇷 삼성전자",
        "000660.KS": "🇰🇷 SK하이닉스",
        "GOOGL": "🔍 구글 (GOOGL)",
        "IONQ": "⚛️ 아이온큐 (IONQ)",
        "BMNR": "⛏️ 비트마인 (BMNR)", # 명칭 수정
        "RKLB": "🚀 로켓랩 (RKLB)",
        "IREN": "⚡ 아이렌 (IREN)",
        "^VIX": "🌡️ 공포지수"
    }

    now = datetime.now()
    msg = f"🎯 *실시간 매물대 & 바닥 정밀 스캔*\n"
    msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')} (KST)\n"
    msg += f"💡 *기준: 매물대 지지 + RSI 반등 + 스토 골든크로스*\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    hit_details = []
    vix_val = 0

    for ticker, name in watch_list.items():
        try:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty: continue
            
            # 데이터 추출 최적화
            if isinstance(df.columns, pd.MultiIndex):
                close_ser = df['Close'][ticker].dropna()
                vol_ser = df['Volume'][ticker].dropna()
            else:
                close_ser = df['Close'].dropna()
                vol_ser = df['Volume'].dropna()

            current_price = float(close_ser.iloc[-1])

            if ticker == "^VIX":
                vix_val = current_price
                continue

            # 지표 계산
            rsi_series, k_series, d_series = get_indicators(close_ser)
            rsi, k, d = rsi_series.iloc[-1], k_series.iloc[-1], d_series.iloc[-1]
            pk, pd_val = k_series.iloc[-2], d_series.iloc[-2]
            
            # 매물대 지지선 계산
            support_price = get_volume_support(df)

            # --- [수정된 확실한 매수 기준] ---
            # 1. RSI가 35 이하이거나, 45 이하이면서 전일보다 상승 (반등 신호)
            is_rsi_ok = (rsi <= 35) or (rsi <= 45 and rsi > rsi_series.iloc[-2])
            # 2. 스토캐스틱 골든크로스 (K가 D를 상향 돌파)
            is_stoch_ok = (pk <= pd_val and k > d) and k < 40 # 너무 고점은 제외
            # 3. 현재가가 매물대 지지선 근처 (+- 3% 이내)
            is_near_support = current_price <= support_price * 1.03
            
            status = "💤 관망중"
            unit = "원" if ".KS" in ticker else "$"
            p_fmt = f"{current_price:,.0f}{unit}" if unit=="원" else f"{current_price:.2f}{unit}"
            s_fmt = f"{support_price:,.0f}{unit}" if unit=="원" else f"{support_price:.2f}{unit}"

            if is_rsi_ok and is_stoch_ok:
                status = "🔥 *[매수 적기]*"
                hit_details.append(f"🔥 *{name}*\n   가: {p_fmt} (매물대:{s_fmt})\n   신호: RSI {rsi:.1f} / Stoch 골든!")
            elif rsi <= 40 or is_near_support:
                status = "⚠️ *[관심 진입]*"

            msg += f"📍 *{name}*\n"
            msg += f"- 현재가: {p_fmt}\n"
            msg += f"- RSI: *{rsi:.1f}* | Stoch: *{k:.1f}/{d:.1f}*\n"
            msg += f"- 핵심 매물대: {s_fmt}\n"
            msg += f"- 상태: {status}\n\n"

        except Exception as e:
            print(f"Error {ticker}: {e}")

    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🌡️ 시장 공포(VIX): {vix_val:.1f}\n"
    
    if hit_details:
        msg += f"📢 *오늘의 스나이퍼 픽:*\n" + "\n".join(hit_details)
    else:
        msg += f"📢 포착된 신호 없음"

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
