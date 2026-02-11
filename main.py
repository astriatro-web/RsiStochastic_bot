import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime

# 환경 변수 설정
TOKEN = os.environ.get('SNIPER_TOKEN')
CHAT_ID = os.environ.get('MY_PRIVATE_ID')

def get_indicators(series):
    """지표 계산: RSI 14, Stochastic Slow 14,3,3"""
    if len(series) < 20: return 0.0, 0.0, 0.0, 0.0, 0.0
    
    # RSI 계산
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Stochastic Slow 계산
    low_min = series.rolling(window=14).min()
    high_max = series.rolling(window=14).max()
    fast_k = 100 * (series - low_min) / (high_max - low_min)
    slow_k = fast_k.rolling(window=3).mean()
    slow_d = slow_k.rolling(window=3).mean()
    
    # 현재값과 이전값(골든크로스 확인용) 추출
    return float(rsi.iloc[-1]), float(slow_k.iloc[-1]), float(slow_d.iloc[-1]), \
           float(slow_k.iloc[-2]), float(slow_d.iloc[-2])

def run_sniper():
    # 1. 감시 종목 리스트 (7종목 + VIX)
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

    # 2. 시간대 및 제목 설정
    now = datetime.now()
    hour = (now.hour + 9) % 24  # UTC -> KST 변환
    
    title_type = "🔍 실시간 바닥 정밀 스캔"
    if 5 <= hour <= 10: title_type = "☀️ 미장 마감 & 기상 리포트"
    elif 14 <= hour <= 16: title_type = "☕ 국장 마감 & 오후 전략"
    elif 22 <= hour <= 24: title_type = "🌙 미장 개장 & 야간 점검"

    msg = f"🎯 *{title_type}*\n"
    msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')} (KST)\n"
    msg += f"💡 *기준: RSI 40 미만 & Stoch 골든크로스*\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    hit_details = [] 
    vix_val = 0

    # 3. 종목별 루프
    for ticker, name in watch_list.items():
        try:
            # 데이터 수집 (안전한 멀티인덱스 대응)
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

            # 지표 계산 결과
            rsi, k, d, pk, pd_val = get_indicators(series)

            # 4. 판정 로직 (RSI 40 완화 적용)
            status = "💤 관망중"
            unit = "원" if ".KS" in ticker else "$"
            price_str = f"{current_price:,.0f}{unit}" if unit=="원" else f"{current_price:.2f}{unit}"

            if rsi > 0:
                is_rsi_ok = rsi <= 40
                is_stoch_ok = (k <= 20) or (k > d and pk <= pd_val)
                
                if is_rsi_ok and is_stoch_ok:
                    status = "🔥 *[매수 적기]*"
                    # 요약 섹션용 상세 정보 저장
                    hit_details.append(f"👉 *{name}*: {price_str} (RSI:{rsi:.1f} / K:{k:.1f})")
                elif rsi <= 45 or k <= 25:
                    status = "⚠️ *[관심 진입]*"

            # 개별 종목 디스플레이
            msg += f"📍 *{name}*\n"
            msg += f"- 현재가: {price_str}\n"
            msg += f"- RSI: *{rsi:.1f}*\n"
            msg += f"- Stoch: *K {k:.1f} / D {d:.1f}*\n"
            msg += f"- 상태: {status}\n\n"

        except Exception as e:
            print(f"Error {ticker}: {e}")

    # 5. 하단 요약 및 전송
    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🌡️ 시장 공포(VIX): {vix_val:.1f}\n"
    
    if hit_details:
        msg += f"📢 *매수 신호 포착 ({len(hit_details)}개):*\n"
        msg += "\n".join(hit_details)
    else:
        msg += f"📢 포착된 신호 없음"

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
