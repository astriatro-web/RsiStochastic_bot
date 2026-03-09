import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
from datetime import datetime

# 1. 환경 변수 설정
TOKEN = os.environ.get('SNIPER_TOKEN')
CHAT_ID = os.environ.get('MY_PRIVATE_ID')

def get_indicators(df, period=14):
    """지표 계산: RSI, Stochastic, ADX"""
    if len(df) < 30: return None
    close = df['Close']
    high = df['High']
    low = df['Low']
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Stochastic Slow
    low_min = close.rolling(window=period).min()
    high_max = close.rolling(window=period).max()
    fast_k = 100 * (close - low_min) / (high_max - low_min)
    slow_k = fast_k.rolling(window=3).mean()
    slow_d = slow_k.rolling(window=3).mean()

    # ADX
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(window=period).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(window=period).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return {"rsi": rsi, "slow_k": slow_k, "slow_d": slow_d, "adx": adx}

def get_consecutive_days(price_series, ma_series):
    """연속 하락 일수 계산"""
    under_ma = price_series < ma_series
    count = 0
    for val in under_ma[::-1]:
        if val: count += 1
        else: break
    return count

def run_sniper():
    watch_list = {
        "005930.KS": "🇰🇷 삼성전자", "000660.KS": "🇰🇷 SK하이닉스",
        "GOOGL": "🔍 구글", "IONQ": "⚛️ 아이온큐", "TEM": "🩺 템퍼스AI",
        "RKLB": "🚀 로켓랩", "IREN": "⚡ 아이렌"
    }
    index_list = ["QLD", "SSO", "QQQ", "TQQQ", "^VIX", "USDKRW=X"]
    all_tickers = list(watch_list.keys()) + index_list

    raw_data = yf.download(all_tickers, period="3y", interval="1d", progress=False, auto_adjust=True)
    close_df = raw_data['Close']
    
    msg = f"🤖 **통합 마켓 리포트** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n"
    msg += f"━━━━━━━━━━━━━━━\n"

    # --- PART 1. 지수 및 시장 진단 ---
    qqq_df = raw_data.xs('QQQ', axis=1, level=1).dropna()
    ind = get_indicators(qqq_df)
    q_now, q_adx, q_rsi = qqq_df['Close'].iloc[-1], ind['adx'].iloc[-1], ind['rsi'].iloc[-1]
    q_ma20 = qqq_df['Close'].rolling(20).mean().iloc[-1]
    q_ma120 = qqq_df['Close'].rolling(120).mean().iloc[-1]
    vix = close_df["^VIX"].dropna().iloc[-1]
    rate = close_df["USDKRW=X"].dropna().iloc[-1]

    if q_adx < 20: status = "💤 횡보"
    elif q_now > q_ma120: status = "📈 상승"
    else: status = "📉 하락"

    high_bet = "⚠️ 금지"
    if q_adx < 20 and q_rsi < 40: high_bet = "✅ 적극 가능 (박스권 하단)"
    elif q_now > q_ma120 and q_now < q_ma20: high_bet = "🟡 보통 (눌림목)"

    msg += f"🌡️ 시장진단: {status} | ADX: {q_adx:.1f}\n"
    msg += f"💵 환율: {rate:,.1f}원 | VIX: {vix:.1f} | RSI: {q_rsi:.1f}\n"
    msg += f"🛡️ 고배팅: {high_bet}\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    # --- PART 2. QLD & SSO 상세 (이평선 풀세트) ---
    for sym in ["QLD", "SSO"]:
        ser = close_df[sym].dropna()
        now = ser.iloc[-1]
        ma60 = ser.rolling(60).mean().iloc[-1]
        ma120_s = ser.rolling(120).mean()
        ma120, ma200, ma300 = ma120_s.iloc[-1], ser.rolling(200).mean().iloc[-1], ser.rolling(300).mean().iloc[-1]
        
        msg += f"📍 **{sym} 상세 (현재: ${now:.2f})**\n"
        if sym == "QLD": msg += f"- 60일선: ${ma60:.2f} ({'📉' if now < ma60 else '📈'})\n"
        msg += f"- 120일선: ${ma120:.2f} ({'📉' if now < ma120 else '📈'})\n"
        msg += f"- 200일선: ${ma200:.2f} ({'📉' if now < ma200 else '📈'})\n"
        msg += f"- 300일선: ${ma300:.2f} ({'📉' if now < ma300 else '📈'})\n"
        
        if now < ma120: msg += f"👉 *🔥 매수 구간 ({get_consecutive_days(ser, ma120_s)}일차)*\n"
        msg += "\n"

    # --- PART 3. 개별 종목 스캔 ---
    msg += f"━━━━━━━━━━━━━━━\n🎯 **종목별 RSI 스캔**\n"
    for ticker, name in watch_list.items():
        try:
            t_df = raw_data.xs(ticker, axis=1, level=1).dropna()
            t_ind = get_indicators(t_df)
            curr, rsi = t_df['Close'].iloc[-1], t_ind['rsi'].iloc[-1]
            k, d = t_ind['slow_k'].iloc[-1], t_ind['slow_d'].iloc[-1]
            
            sig = "🔥 [매수]" if (rsi <= 40 and k > d) else ("⚠️ [관심]" if rsi <= 45 else "💤 관망")
            unit = "원" if ".KS" in ticker else "$"
            msg += f"• {name}: {curr:,.0f}{unit} | RSI:{rsi:.1f} | {sig}\n"
        except: continue

    msg += f"\n🚀 TQQQ 특공대: {'🔥 진입!' if q_rsi < 35 and vix > 28 else '💤 없음'}"

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
