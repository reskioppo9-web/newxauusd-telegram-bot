import os
import requests
import pandas as pd
# =========================================================
# CONFIG
# =========================================================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TWELVE_DATA_API_KEY = os.environ["TWELVE_DATA_API_KEY"]
SYMBOL = "XAU/USD"
# =========================================================
# GET MARKET DATA
# =========================================================
def get_data(interval, outputsize=250):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY
    }
    response = requests.get(
        url,
        params=params,
        timeout=20
    )
    response.raise_for_status()
    data = response.json()
    if "values" not in data:
        raise Exception(
            f"Twelve Data error: {data}"
        )
    df = pd.DataFrame(data["values"])
    df["datetime"] = pd.to_datetime(
        df["datetime"]
    )
    df = df.sort_values(
        "datetime"
    ).reset_index(drop=True)
    for col in [
        "open",
        "high",
        "low",
        "close"
    ]:
        df[col] = pd.to_numeric(
            df[col]
        )
    return df
# =========================================================
# INDICATORS
# =========================================================
def calculate_rsi(df, length=14):
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(
        alpha=1 / length,
        adjust=False
    ).mean()
    avg_loss = loss.ewm(
        alpha=1 / length,
        adjust=False
    ).mean()
    rs = avg_gain / avg_loss
    return 100 - (
        100 / (1 + rs)
    )
def calculate_atr(df, length=14):
    previous_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = abs(
        df["high"] - previous_close
    )
    tr3 = abs(
        df["low"] - previous_close
    )
    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)
    return true_range.ewm(
        alpha=1 / length,
        adjust=False
    ).mean()
def add_indicators(df):
    df["ema20"] = df["close"].ewm(
        span=20,
        adjust=False
    ).mean()
    df["ema50"] = df["close"].ewm(
        span=50,
        adjust=False
    ).mean()
    df["rsi"] = calculate_rsi(df)
    df["atr"] = calculate_atr(df)
    return df
# =========================================================
# TIMEFRAME ANALYSIS
# =========================================================
def analyze_timeframe(interval):
    df = get_data(
        interval,
        250
    )
    df = add_indicators(df)
    # Candle terakhir yang SUDAH CLOSE
    latest = df.iloc[-2]
    price = latest["close"]
    ema20 = latest["ema20"]
    ema50 = latest["ema50"]
    rsi = latest["rsi"]
    atr = latest["atr"]
    if (
        price > ema20
        and ema20 > ema50
    ):
        trend = "BULLISH"
    elif (
        price < ema20
        and ema20 < ema50
    ):
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"
    return {
        "trend": trend,
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "atr": atr,
        "time": latest["datetime"]
    }
# =========================================================
# SUPPORT / RESISTANCE
# =========================================================
def get_support_resistance(df):
    # Menggunakan candle yang sudah close
    closed = df.iloc[:-1].copy()
    recent = closed.tail(80)
    support = recent["low"].nsmallest(5).mean()
    resistance = recent["high"].nlargest(5).mean()
    return support, resistance
# =========================================================
# SCORING ENGINE
# =========================================================
def calculate_score(h4, h1, m30, m15):
    buy_score = 0
    sell_score = 0
    # -------------------------
    # H4
    # -------------------------
    if h4["trend"] == "BULLISH":
        buy_score += 20
    elif h4["trend"] == "BEARISH":
        sell_score += 20
    # -------------------------
    # H1
    # -------------------------
    if h1["trend"] == "BULLISH":
        buy_score += 25
    elif h1["trend"] == "BEARISH":
        sell_score += 25
    # -------------------------
    # M30
    # -------------------------
    if m30["trend"] == "BULLISH":
        buy_score += 20
    elif m30["trend"] == "BEARISH":
        sell_score += 20
    # RSI M30
    if m30["rsi"] > 50:
        buy_score += 10
    elif m30["rsi"] < 50:
        sell_score += 10
    # -------------------------
    # M15
    # -------------------------
    if m15["trend"] == "BULLISH":
        buy_score += 15
    elif m15["trend"] == "BEARISH":
        sell_score += 15
    # RSI M15
    if m15["rsi"] > 50:
        buy_score += 10
    elif m15["rsi"] < 50:
        sell_score += 10
    # -------------------------
    # FINAL
    # -------------------------
    if buy_score >= sell_score:
        direction = "BUY"
        score = buy_score
    else:
        direction = "SELL"
        score = sell_score
    # Cap score at 100
    score = min(score, 100)
    # Minimum threshold
    if score >= 80:
        signal = f"STRONG {direction}"
    elif score >= 65:
        signal = direction
    else:
        signal = "WAIT"
    return {
        "direction": direction,
        "score": score,
        "signal": signal
    }
# =========================================================
# ANALYSIS TEXT
# =========================================================
def create_analysis(
    h4,
    h1,
    m30,
    m15,
    score_result
):
    direction = score_result["direction"]
    score = score_result["score"]
    if score_result["signal"] == "WAIT":
        return (
            "Market belum memiliki "
            "konfirmasi yang cukup kuat."
        )
    if direction == "BUY":
        reasons = []
        if h4["trend"] == "BULLISH":
            reasons.append(
                "H4 bullish"
            )
        if h1["trend"] == "BULLISH":
            reasons.append(
                "H1 bullish"
            )
        if m30["trend"] == "BULLISH":
            reasons.append(
                "M30 bullish"
            )
        if m15["trend"] == "BULLISH":
            reasons.append(
                "M15 bullish"
            )
        if m30["rsi"] > 50:
            reasons.append(
                "momentum M30 positif"
            )
        return (
            "Bias bullish didukung oleh "
            + ", ".join(reasons)
            + "."
        )
    else:
        reasons = []
        if h4["trend"] == "BEARISH":
            reasons.append(
                "H4 bearish"
            )
        if h1["trend"] == "BEARISH":
            reasons.append(
                "H1 bearish"
            )
        if m30["trend"] == "BEARISH":
            reasons.append(
                "M30 bearish"
            )
        if m15["trend"] == "BEARISH":
            reasons.append(
                "M15 bearish"
            )
        if m30["rsi"] < 50:
            reasons.append(
                "momentum M30 negatif"
            )
        return (
            "Bias bearish didukung oleh "
            + ", ".join(reasons)
            + "."
        )
# =========================================================
# TELEGRAM
# =========================================================
def send_telegram(message):
    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )
    response = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        },
        timeout=20
    )
    print(
        f"Telegram HTTP status: "
        f"{response.status_code}"
    )
    print(
        f"Telegram response: "
        f"{response.text}"
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise Exception(
            f"Telegram error: {result}"
        )
    print(
        "✅ Telegram message sent!"
    )
# =========================================================
# MAIN
# =========================================================
def main():
    print(
        "===================================="
    )
    print(
        "🤖 XAUUSD AI-STYLE SCANNER V1.1"
    )
    print(
        "===================================="
    )
    # -------------------------
    # Multi timeframe
    # -------------------------
    print("Loading H4...")
    h4 = analyze_timeframe("4h")
    print("Loading H1...")
    h1 = analyze_timeframe("1h")
    print("Loading M30...")
    m30 = analyze_timeframe("30min")
    print("Loading M15...")
    m15 = analyze_timeframe("15min")
    # -------------------------
    # Support / Resistance
    # -------------------------
    m30_df = get_data(
        "30min",
        250
    )
    support, resistance = (
        get_support_resistance(
            m30_df
        )
    )
    # -------------------------
    # Score
    # -------------------------
    score_result = calculate_score(
        h4,
        h1,
        m30,
        m15
    )
    signal = score_result["signal"]
    score = score_result["score"]
    direction = score_result["direction"]
    # -------------------------
    # Entry / SL / TP
    # -------------------------
    entry = m30["price"]
    atr = m30["atr"]
    sl = None
    tp1 = None
    tp2 = None
    if signal != "WAIT":
        if direction == "BUY":
            sl = entry - (
                1.5 * atr
            )
            tp1 = entry + (
                1.0 * atr
            )
            tp2 = entry + (
                2.0 * atr
            )
        else:
            sl = entry + (
                1.5 * atr
            )
            tp1 = entry - (
                1.0 * atr
            )
            tp2 = entry - (
                2.0 * atr
            )
    # -------------------------
    # RR
    # -------------------------
    if sl is not None:
        risk = abs(
            entry - sl
        )
        reward1 = abs(
            tp1 - entry
        )
        reward2 = abs(
            tp2 - entry
        )
        rr1 = reward1 / risk
        rr2 = reward2 / risk
    else:
        rr1 = None
        rr2 = None
    # -------------------------
    # Analysis
    # -------------------------
    analysis = create_analysis(
        h4,
        h1,
        m30,
        m15,
        score_result
    )
    # =====================================================
    # TELEGRAM MESSAGE
    # =====================================================
    if signal == "WAIT":
        message = (
            "🤖 XAUUSD AI-STYLE SCANNER\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "⚪ SIGNAL: WAIT\n"
            f"📊 Score: {score}/100\n\n"
            "📈 MULTI-TIMEFRAME\n"
            f"H4  : {h4['trend']}\n"
            f"H1  : {h1['trend']}\n"
            f"M30 : {m30['trend']}\n"
            f"M15 : {m15['trend']}\n\n"
            "📊 M30 INDICATORS\n"
            f"Price : {m30['price']:.2f}\n"
            f"EMA20 : {m30['ema20']:.2f}\n"
            f"EMA50 : {m30['ema50']:.2f}\n"
            f"RSI : {m30['rsi']:.2f}\n"
            f"ATR : {m30['atr']:.2f}\n\n"
            "🧱 KEY LEVELS\n"
            f"Support : {support:.2f}\n"
            f"Resistance : {resistance:.2f}\n\n"
            "🤖 ANALYSIS\n"
            f"{analysis}\n\n"
            f"⏱ Candle M30 : {m30['time']}\n\n"
            "⚠️ Signal only — manage your risk."
        )
    else:
        emoji = (
            "🟢"
            if direction == "BUY"
            else "🔴"
        )
        message = (
            "🤖 XAUUSD AI-STYLE SCANNER\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"{emoji} {signal}\n"
            f"📊 Score: {score}/100\n\n"
            "📈 MULTI-TIMEFRAME\n"
            f"H4  : {h4['trend']}\n"
            f"H1  : {h1['trend']}\n"
            f"M30 : {m30['trend']}\n"
            f"M15 : {m15['trend']}\n\n"
            "📊 M30 INDICATORS\n"
            f"Price : {m30['price']:.2f}\n"
            f"EMA20 : {m30['ema20']:.2f}\n"
            f"EMA50 : {m30['ema50']:.2f}\n"
            f"RSI : {m30['rsi']:.2f}\n"
            f"ATR : {m30['atr']:.2f}\n\n"
            "🧱 KEY LEVELS\n"
            f"Support : {support:.2f}\n"
            f"Resistance : {resistance:.2f}\n\n"
            "🎯 TRADE PLAN\n"
            f"Entry : {entry:.2f}\n"
            f"SL : {sl:.2f}\n"
            f"TP1 : {tp1:.2f}\n"
            f"TP2 : {tp2:.2f}\n\n"
            "📐 RISK / REWARD\n"
            f"TP1 : 1:{rr1:.2f}\n"
            f"TP2 : 1:{rr2:.2f}\n\n"
            "🤖 ANALYSIS\n"
            f"{analysis}\n\n"
            f"⏱ Candle M30 : {m30['time']}\n\n"
            "⚠️ Signal only — manage your risk."
        )
    print(message)
    send_telegram(message)
    print(
        "===================================="
    )
    print(
        "✅ SCANNER FINISHED"
    )
    print(
        "===================================="
    )
if __name__ == "__main__":
    main()