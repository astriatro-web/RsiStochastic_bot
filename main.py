import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime

TOKEN = os.environ.get('SNIPER_TOKEN')
CHAT_ID = os.environ.get('MY_PRIVATE_ID')

def get_indicators(series):
    # 데이터 부족 시 방어 로직
    if len(series) < 15: return 0.0, 0.0, 0.0, 0.0, 0.0
    
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
    
    # 마지막 및 이전 값 추출 (NaN 방지)
    try:
        curr_rsi = float(rsi.iloc[-1])
        curr_k = float(slow_k.iloc[-1])
        curr_d = float(slow_d.iloc[-1])
        prev_k = float(slow_k.iloc[-2])
        prev_d = float(slow_d.iloc[-2])
        return curr_rsi, curr_k, curr_d, prev_k, prev_d
    except:
        return 0.0, 0.0, 0.0, 0.0, 0.0

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
    msg = f"🎯 *[보강] 실시간 바닥 스캔*\n📅 {now.strftime('%Y-%m-%d %H:%M')} (KST)\n━━━━━━━━━━━━━━━\n\n"

    hit_names = []
    vix_val = 0

    for ticker, name in watch_list.items():
        try:
            # 데이터 로드 (auto_adjust 등 안전 옵션 추가)
            df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
            if df.empty: continue
            
            # 데이터 추출 (가장 확실한 방법)
            series = df['Close']
            if isinstance(series, pd.DataFrame): 
                series = series.iloc[:, 0] # 첫 번째 열 강제 선택
            series = series.dropna()

            if ticker == "^VIX":
                vix_val = float(series.iloc[-1])
                continue

            # 지표 계산
            rsi, k, d, pk, pd_val = get_indicators(series)

            # 판정 로직 (RSI 50 미만 + 스토캐스틱)
            status = "💤 관망중"
            if rsi > 0: # 데이터가 정상일 때만 판정
                if rsi <= 50 and (k <= 20 or (k > d and pk <= pd_val)):
                    status = "🔥 *[매수 적기]*"
                    hit_names.append(name)
                elif rsi <= 55 or k <= 30:
                    status = "⚠️ *[관심 진입]*"

            unit = "원" if ".KS" in ticker else "$"
            price = float(series.iloc[-1])
            
            # 리포트 작성 (수치 강제 출력)
            msg += f"📍 *{name}*\n"
            msg += f"- 현재가: {unit}{price:,.0f if unit=='원' else 2}\n"
            msg += f"- RSI: *{rsi:.1f}*\n"
            msg += f"- Stoch: *K {k:.1f} / D {d:.1f}*\n"
            msg += f"- 상태: {status}\n\n"

        except Exception as e:
            print(f"Error {ticker}: {e}")

    msg += f"━━━━━━━━━━━━━━━\n🌡️ VIX: {vix_val:.1f}\n"
    if hit_names:
        msg += f"📢 *신호 포착: " + ", ".join(hit_names) + "*"
    else:
        msg += f"📢 포착된 신호 없음"

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
