import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
from datetime import datetime

# 1. 환경 변수 설정 (기존 설정 유지)
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
    
    bins = 15
    hist, bin_edges = np.histogram(data['Close'], bins=bins, weights=data['Volume'])
    sorted_indices = np.argsort(hist)[::-1]
    
    support = None
    resistance = None
    
    for idx in sorted_indices:
        price_level = (bin_edges[idx] + bin_edges[idx+1]) / 2
        if price_level < current_price and support is None:
            support = price_level
        elif price_level > current_price and resistance is None:
            resistance = price_level
        if support and resistance: break
            
    return support, resistance

def get_tqqq_strategy():
    """TQQQ 200일선 매매 전략 (실시간 시세 반영 버전)"""
    try:
        ticker_obj = yf.Ticker("TQQQ")
        
        # 200일선 계산을 위한 과거 데이터 (일봉)
        df = ticker_obj.history(period="2y", interval="1d")
        if df.empty: return ""
        
        # 실시간에 가까운 최신 가격 가져오기
        current_price = ticker_obj.fast_info['last_price']
        
        # 200일 이동평균선(SMA) 계산
        sma200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        threshold = sma200 * 1.05  # 과열 기준선

        title = "🛡️ *TQQQ 200일선 실시간 전략*"
        diff_pct = ((current_price / sma200) - 1) * 100
        info = f"• **현재가: ${current_price:.2f}**\n• 200일선: ${sma200:.2f} ({diff_pct:+.2f}%)\n"
        
        if current_price < sma200:
            status = "🔴 *[하락 상황: 전량 매도]*"
            guide = "위험 회피 및 현금 보존! TQQQ/SPYM 전량 매도 후 SGOV로 전환하세요."
        elif sma200 <= current_price <= threshold:
            status = "🟢 *[집중 투자: 매수 구간]*"
            guide = "수익 극대화 구간! SGOV -> TQQQ 교체 (하루 뒤 실행 권장)."
        else:
            status = "🟠 *[과열 상황: 수익 즐기기]*"
            guide = "추격 매수 금지! 기존 TQQQ 유지, 신규 자금은 SPYM 매수."

        res = f"{title}\n{status}\n{info}{guide}\n"
        res += "⚠️ *매수 즉시 평단 -5% 스탑로스 설정 필수!*\n\n"
        return res
    except Exception as e:
        return f"TQQQ 전략 계산 에러: {e}\n\n"

def run_sniper():
    # 종목 리스트
    watch_list = {
        "005930.KS": "🇰🇷 삼성전자",
        "000660.KS": "🇰🇷 SK하이닉스",
        "GOOGL": "🔍 구글 (GOOGL)",
        "IONQ": "⚛️ 아이온큐 (IONQ)",
        "TEM": "🩺 템퍼스AI (TEM)",
        "RKLB": "🚀 로켓랩 (RKLB)",
        "IREN": "⚡ 아이렌 (IREN)",
        "^VIX": "🌡️ 공포지수"
    }

    now = datetime.now()
    # 통합 메시지 시작
    msg = f"🤖 **통합 마켓 리포트**\n"
    msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')} (KST)\n\n"
    
    # 1. TQQQ 전략 리포트 추가
    msg += get_tqqq_strategy()
    
    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🎯 *실시간 RSI & 매물대 스캔*\n\n"

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

            # 지표 계산
            rsi_series, k_series, d_series = get_indicators(close_ser)
            if rsi_series is None: continue
            
            rsi, k, d = rsi_series.iloc[-1], k_series.iloc[-1], d_series.iloc[-1]
            pk, pd_val = k_series.iloc[-2], d_series.iloc[-2]
            
            # 매물대 분석용 데이터 전처리
            target_df = df if not isinstance(df.columns, pd.MultiIndex) else df.xs(ticker, axis=1, level=1)
            support, resistance = analyze_volume_profile(target_df)

            # 매수 신호 로직
            is_rsi_ok = (rsi <= 35) or (rsi <= 45 and rsi > rsi_series.iloc[-2])
            is_stoch_ok = (pk <= pd_val and k > d) and k < 40
            is_near_support = support and (current_price <= support * 1.03)
            
            unit = "원" if ".KS" in ticker else "$"
            p_fmt = f"{current_price:,.0f}{unit}" if unit=="원" else f"{current_price:.2f}{unit}"
            
            # 상태 판단
            if is_rsi_ok and is_stoch_ok and is_near_support:
                status = "🔥 *[강력 매수]*"
            elif is_rsi_ok and is_stoch_ok:
                status = "✅ *[기술적 반등]*"
            elif rsi <= 40 or is_near_support:
                status = "⚠️ *[관심 진입]*"
            else:
                status = "💤 관망중"

            msg += f"📍 *{name}*\n"
            msg += f"- 현재가: {p_fmt} | RSI: *{rsi:.1f}*\n"
            msg += f"- 상태: {status}\n\n"

        except Exception as e:
            print(f"Error {ticker}: {e}")

    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🌡️ 시장 공포(VIX): {vix_val:.1f}\n"
    msg += f"📢 신호에 따라 대응하세요."

    # 텔레그램 발송
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
