import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
from datetime import datetime

# 1. 환경 변수 로드
TOKEN = os.environ.get('SNIPER_TOKEN')
CHAT_ID = os.environ.get('MY_PRIVATE_ID')

def get_indicators(df, period=14):
    """지표 계산: RSI, Stochastic, ADX (에러 방지 로직 포함)"""
    if df is None or len(df) < 30: return None
    
    close = df['Close']
    high = df['High'] if 'High' in df.columns else close
    low = df['Low'] if 'Low' in df.columns else close
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    # Stochastic Slow
    low_min = close.rolling(window=period).min()
    high_max = close.rolling(window=period).max()
    fast_k = 100 * (close - low_min) / (high_max - low_min + 1e-9)
    slow_k = fast_k.rolling(window=3).mean()
    slow_d = slow_k.rolling(window=3).mean()

    # ADX
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_di = 100 * (pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=df.index).rolling(window=period).mean() / (atr + 1e-9))
    minus_di = 100 * (pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=df.index).rolling(window=period).mean() / (atr + 1e-9))
    adx = (100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)).rolling(window=period).mean()
    
    return {"rsi": rsi, "slow_k": slow_k, "slow_d": slow_d, "adx": adx}

def get_consecutive_days(price_series, ma_series):
    """지정 이평선 하방 유지 일수 계산"""
    under_ma = price_series < ma_series
    count = 0
    for val in under_ma[::-1]:
        if val: count += 1
        else: break
    return count

def run_sniper():
    try:
        watch_list = {
            "005930.KS": "🇰🇷 삼성전자", "000660.KS": "🇰🇷 SK하이닉스",
            "GOOGL": "🔍 구글", "IONQ": "⚛️ 아이온큐", "TEM": "🩺 템퍼스AI",
            "RKLB": "🚀 로켓랩", "IREN": "⚡ 아이렌"
        }
        index_list = ["QLD", "SSO", "QQQ", "TQQQ", "^VIX", "USDKRW=X"]
        all_tickers = list(watch_list.keys()) + index_list
        
        # 데이터 다운로드
        raw_data = yf.download(all_tickers, period="3y", interval="1d", progress=False, auto_adjust=True)
        
        # 멀티인덱스 대응 데이터 추출 함수
        def get_df(ticker):
            try:
                return raw_data.xs(ticker, axis=1, level=1)
            except:
                return raw_data[ticker] if ticker in raw_data.columns else None

        msg = f"🤖 **통합 마켓 스나이퍼 리포트**\n"
        msg += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        msg += f"━━━━━━━━━━━━━━━\n\n"

        # --- 1. ADX 횡보장 필터 및 지수 진단 ---
        qqq_df = get_df('QQQ').dropna()
        q_ind = get_indicators(qqq_df)
        q_now, q_adx, q_rsi = qqq_df['Close'].iloc[-1], q_ind['adx'].iloc[-1], q_ind['rsi'].iloc[-1]
        q_ma120 = qqq_df['Close'].rolling(120).mean().iloc[-1]
        vix = get_df('^VIX')['Close'].iloc[-1]
        rate = get_df('USDKRW=X')['Close'].iloc[-1]

        market_status = "💤 횡보 (추세 없음)" if q_adx < 20 else ("📈 상승 추세" if q_now > q_ma120 else "📉 하락 추세")

        msg += f"🌡️ **시장 진단: {market_status}**\n"
        msg += f"• ADX: {q_adx:.1f} | RSI: {q_rsi:.1f}\n"
        msg += f"• 환율: {rate:,.1f}원 | VIX: {vix:.1f}\n"
        msg += f"━━━━━━━━━━━━━━━\n\n"

        # --- 2. QLD & SSO 상세 (이평선 풀세트) ---
        for sym in ["QLD", "SSO"]:
            df_sym = get_df(sym).dropna()
            ser = df_sym['Close']
            now = ser.iloc[-1]
            ma60 = ser.rolling(60).mean().iloc[-1]
            ma120_s = ser.rolling(120).mean()
            ma120, ma200, ma300 = ma120_s.iloc[-1], ser.rolling(200).mean().iloc[-1], ser.rolling(300).mean().iloc[-1]
            
            msg += f"📍 **{sym} 상세 (현재: ${now:.2f})**\n"
            if sym == "QLD": 
                msg += f"- 60일선: ${ma60:.2f} ({'📉' if now < ma60 else '📈'})\n"
            msg += f"- 120일선: ${ma120:.2f} ({'📉' if now < ma120 else '📈'})\n"
            msg += f"- 200일선: ${ma200:.2f} | 300일선: ${ma300:.2f}\n"
            
            if now < ma120:
                msg += f"👉 *🔥 매수 구간 ({get_consecutive_days(ser, ma120_s)}일차)*\n"
            msg += "\n"

        # --- 3. TQQQ 200일선 실시간 전략 ---
        tq_df = get_df('TQQQ').dropna()
        tq_now = tq_df['Close'].iloc[-1]
        tq_sma200 = tq_df['Close'].rolling(200).mean().iloc[-1]
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
                t_df = get_df(ticker).dropna()
                t_ind = get_indicators(t_df)
                curr, rsi = t_df['Close'].iloc[-1], t_ind['rsi'].iloc[-1]
                k, d = t_ind['slow_k'].iloc[-1], t_ind['slow_d'].iloc[-1]
                
                status = "🔥 [매수]" if (rsi <= 40 and k > d) else ("⚠️ [관심]" if rsi <= 45 else "💤 관망")
                unit = "원" if ".KS" in ticker else "$"
                msg += f"• {name}: {curr:,.0f}{unit} | RSI:{rsi:.1f} | {status}\n"
            except: continue

        msg += f"\n━━━━━━━━━━━━━━━"
        
        # 메시지 전송
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

    except Exception as e:
        error_msg = f"❌ 실행 에러 발생: {str(e)}"
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": error_msg})
        raise e

if __name__ == "__main__":
    run_sniper()
