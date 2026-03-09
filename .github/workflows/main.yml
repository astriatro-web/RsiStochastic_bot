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
    close, high, low = df['Close'], df['High'], df['Low']
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rsi = 100 - (100 / (1 + (gain / loss)))
    
    low_min, high_max = close.rolling(window=period).min(), close.rolling(window=period).max()
    fast_k = 100 * (close - low_min) / (high_max - low_min)
    slow_k = fast_k.rolling(window=3).mean()
    slow_d = slow_k.rolling(window=3).mean()

    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    up_move, down_move = high - high.shift(1), low.shift(1) - low
    plus_di = 100 * (pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=df.index).rolling(window=period).mean() / atr)
    minus_di = 100 * (pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=df.index).rolling(window=period).mean() / atr)
    adx = (100 * abs(plus_di - minus_di) / (plus_di + minus_di)).rolling(window=period).mean()
    
    return {"rsi": rsi, "slow_k": slow_k, "slow_d": slow_d, "adx": adx}

def get_consecutive_days(price_series, ma_series):
    under_ma = price_series < ma_series
    count = 0
    for val in under_ma[::-1]:
        if val: count += 1
        else: break
    return count

def run_sniper():
    watch_list = {"005930.KS": "🇰🇷 삼성", "000660.KS": "🇰🇷 하이닉스", "GOOGL": "🔍 구글", "IONQ": "⚛️ IONQ", "TEM": "🩺 TEM", "RKLB": "🚀 RKLB", "IREN": "⚡ IREN"}
    all_tickers = list(watch_list.keys()) + ["QLD", "SSO", "QQQ", "TQQQ", "^VIX", "USDKRW=X"]
    
    raw_data = yf.download(all_tickers, period="3y", interval="1d", progress=False, auto_adjust=True)
    close_df = raw_data['Close']
    
    msg = f"🤖 **통합 마켓 스나이퍼 리포트**\n"
    msg += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    # --- 1. ADX 횡보장 필터 및 지수 진단 ---
    qqq_df = raw_data.xs('QQQ', axis=1, level=1).dropna()
    q_ind = get_indicators(qqq_df)
    q_now, q_adx, q_rsi = qqq_df['Close'].iloc[-1], q_ind['adx'].iloc[-1], q_ind['rsi'].iloc[-1]
    q_ma120 = qqq_df['Close'].rolling(120).mean().iloc[-1]
    vix, rate = close_df["^VIX"].dropna().iloc[-1], close_df["USDKRW=X"].dropna().iloc[-1]

    if q_adx < 20: market_status = "💤 횡보 (추세 없음)"
    elif q_now > q_ma120: market_status = "📈 상승 추세"
    else: market_status = "📉 하락 추세"

    msg += f"🌡️ **시장 진단: {market_status}**\n"
    msg += f"• ADX: {q_adx:.1f} | RSI: {q_rsi:.1f}\n"
    msg += f"• 환율: {rate:,.1f}원 | VIX: {vix:.1f}\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    # --- 2. QLD & SSO 상세 (이평선 풀세트) ---
    for sym in ["QLD", "SSO"]:
        ser = close_df[sym].dropna()
        now, ma120_s = ser.iloc[-1], ser.rolling(120).mean()
        msg += f"📍 **{sym} 상세 (현재: ${now:.2f})**\n"
        if sym == "QLD": 
            msg += f"- 60일선: ${ser.rolling(60).mean().iloc[-1]:.2f} ({'📉' if now < ser.rolling(60).mean().iloc[-1] else '📈'})\n"
        msg += f"- 120일선: ${ma120_s.iloc[-1]:.2f} ({'📉' if now < ma120_s.iloc[-1] else '📈'})\n"
        msg += f"- 200일선: ${ser.rolling(200).mean().iloc[-1]:.2f} ({'📉' if now < ser.rolling(200).mean().iloc[-1] else '📈'})\n"
        msg += f"- 300일선: ${ser.rolling(300).mean().iloc[-1]:.2f}\n"
        
        if now < ma120_s.iloc[-1]:
            msg += f"👉 *🔥 매수 구간 ({get_consecutive_days(ser, ma120_s)}일차)*\n"
        msg += "\n"

    # --- 3. TQQQ 200일선 실시간 전략 ---
    tq_now = float(close_df["TQQQ"].dropna().iloc[-1])
    tq_sma200 = float(close_df["TQQQ"].rolling(window=200).mean().dropna().iloc[-1])
    tq_diff = ((tq_now / tq_sma200) - 1) * 100
    
    if tq_now < tq_sma200: tq_status, tq_guide = "🔴 [전량매도]", "SGOV로 대피하세요."
    elif tq_now <= tq_sma200 * 1.05: tq_status, tq_guide = "🟢 [매수구간]", "TQQQ 교체 시점입니다."
    else: tq_status, tq_guide = "🟠 [과열상황]", "추격 금지! 기존 유지."

    msg += f"🛡️ **TQQQ 200일 전략: {tq_status}**\n"
    msg += f"• 현재: ${tq_now:.2f} (200일선 대비 {tq_diff:+.2f}%)\n"
    msg += f"• 가이드: {tq_guide}\n"
    msg += f"━━━━━━━━━━━━━━━\n\n"

    # --- 4. 개별 종목 RSI 스캔 ---
    msg += f"🎯 **개별 종목 RSI 스캔**\n"
    for ticker, name in watch_list.items():
        try:
            t_df = raw_data.xs(ticker, axis=1, level=1).dropna()
            t_ind = get_indicators(t_df)
            curr, rsi = t_df['Close'].iloc[-1], t_ind['rsi'].iloc[-1]
            k, d = t_ind['slow_k'].iloc[-1], t_ind['slow_d'].iloc[-1]
            
            status = "🔥 [매수]" if (rsi <= 40 and k > d) else ("⚠️ [관심]" if rsi <= 45 else "💤 관망")
            unit = "원" if ".KS" in ticker else "$"
            msg += f"• {name}: {curr:,.0f}{unit} | RSI:{rsi:.1f} | {status}\n"
        except: continue

    msg += f"\n━━━━━━━━━━━━━━━"

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True})

if __name__ == "__main__":
    run_sniper()
