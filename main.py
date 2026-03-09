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

    # ADX (추세 강도)
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
    
    return {
        "rsi": rsi, "slow_k": slow_k, "slow_d": slow_d, "adx": adx
    }

def analyze_volume_profile(df):
    """매물대 분석"""
    data = df.tail(60)
    current_price = float(data['Close'].iloc[-1])
    bins = 15
    hist, bin_edges = np.histogram(data['Close'], bins=bins, weights=data['Volume'])
    sorted_indices = np.argsort(hist)[::-1]
    support, resistance = None, None
    for idx in sorted_indices:
        price_level = (bin_edges[idx] + bin_edges[idx+1]) / 2
        if price_level < current_price and support is None: support = price_level
        elif price_level > current_price and resistance is None: resistance = price_level
        if support and resistance: break
    return support, resistance

def get_consecutive_days(price_series, ma_series):
    """연속 하락 일수 계산"""
    under_ma = price_series < ma_series
    count = 0
    for val in under_ma[::-1]:
        if val: count += 1
        else: break
    return count

def run_sniper():
    # 1. 데이터 통합 다운로드
    watch_list = {
        "005930.KS": "🇰🇷 삼성전자", "000660.KS": "🇰🇷 SK하이닉스",
        "GOOGL": "🔍 구글", "IONQ": "⚛️ 아이온큐", "TEM": "🩺 템퍼스AI",
        "RKLB": "🚀 로켓랩", "IREN": "⚡ 아이렌"
    }
    index_list = ["QLD", "SSO", "QQQ", "TQQQ", "^VIX", "USDKRW=X"]
    all_tickers = list(watch_list.keys()) + index_list

    raw_data = yf.download(all_tickers, period="2y", interval="1d", progress=False, auto_adjust=True)
    close_df = raw_data['Close']
    
    now = datetime.now()
    msg = f"🤖 **통합 마켓 리포트**\n"
    msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')} (KST)\n\n"

    # --- PART 1. QLD/TQQQ 지수 전략 (횡보장 필터 포함) ---
    qqq_df = raw_data.xs('QQQ', axis=1, level=1).dropna()
    qqq_indicators = get_indicators(qqq_df)
    qqq_now = qqq_df['Close'].iloc[-1]
    qqq_ma120 = qqq_df['Close'].rolling(120).mean().iloc[-1]
    qqq_adx = qqq_indicators['adx'].iloc[-1]
    qqq_rsi = qqq_indicators['rsi'].iloc[-1]
    vix_now = close_df["^VIX"].dropna().iloc[-1]
    rate_now = close_df["USDKRW=X"].dropna().iloc[-1]

    # 시장 상태 진단
    if qqq_adx < 20: market_status = "💤 횡보 (추세 없음)"
    elif qqq_now > qqq_ma120: market_status = "📈 상승 추세"
    else: market_status = "📉 하락 추세"

    high_bet = "⚠️ 금지"
    if qqq_adx >= 20 and qqq_now > qqq_ma120:
        if qqq_now < qqq_df['Close'].rolling(20).mean().iloc[-1]: high_bet = "✅ 적극 가능 (눌림목)"
    elif qqq_adx < 20 and qqq_rsi < 40: high_bet = "✅ 적극 가능 (박스권 하단)"

    msg += f"📊 **[지수 진단: {market_status}]**\n"
    msg += f"• ADX: {qqq_adx:.1f} | RSI: {qqq_rsi:.1f}\n"
    msg += f"• 환율: {rate_now:,.1f}원 | VIX: {vix_now:.1f}\n"
    msg += f"• **고배팅 가능여부: {high_bet}**\n\n"

    # QLD 상세 (60, 120, 200, 300)
    qld_ser = close_df["QLD"].dropna()
    qld_ma120_s = qld_ser.rolling(120).mean()
    msg += f"📍 **QLD 상세** (현재: ${qld_ser.iloc[-1]:.2f})\n"
    msg += f"- 120일선: ${qld_ma120_s.iloc[-1]:.2f} ({get_consecutive_days(qld_ser, qld_ma120_s)}일차)\n"
    msg += f"- 200일선: ${qld_ser.rolling(200).mean().iloc[-1]:.2f}\n\n"

    # --- PART 2. 개별 종목 스캔 ---
    msg += f"━━━━━━━━━━━━━━━\n🎯 **실시간 종목 스캔**\n\n"
    for ticker, name in watch_list.items():
        try:
            target_df = raw_data.xs(ticker, axis=1, level=1).dropna()
            ind = get_indicators(target_df)
            curr = target_df['Close'].iloc[-1]
            rsi, k, d = ind['rsi'].iloc[-1], ind['slow_k'].iloc[-1], ind['slow_d'].iloc[-1]
            pk, pd_val = ind['slow_k'].iloc[-2], ind['slow_d'].iloc[-2]
            
            support, _ = analyze_volume_profile(target_df)
            is_rsi_ok = (rsi <= 40)
            is_stoch_ok = (pk <= pd_val and k > d) and k < 40
            
            if is_rsi_ok and is_stoch_ok: status = "🔥 [강력 매수]"
            elif rsi <= 45: status = "⚠️ [관심 진입]"
            else: status = "💤 관망"

            unit = "원" if ".KS" in ticker else "$"
            msg += f"📍 *{name}*\n- {curr:,.0f}{unit} | RSI: {rsi:.1f} | {status}\n"
        except: continue

    msg += f"\n🚀 TQQQ 신호: {'🔥 특공대 진입!' if qqq_rsi < 35 and vix_now > 28 else '💤 신호없음'}"

    # 텔레그램 발송
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_sniper()
