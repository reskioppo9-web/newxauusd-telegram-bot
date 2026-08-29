import os
import requests
import pandas as pd
# =========================================================
# XAUUSD AI-STYLE SCANNER V1.3
# MARKET STRUCTURE
# =========================================================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TWELVE_DATA_API_KEY = os.environ["TWELVE_DATA_API_KEY"]
SYMBOL = "XAU/USD"
# =========================================================
# MARKET DATA
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
    latest = df.iloc[-2]
    price = latest["close"]
    ema20 = latest["ema20"]
    ema50 = latest["ema50"]
    rsi = latest["rsi"]
    atr = latest["atr"]
    if price > ema20 and ema20 > ema50:
        trend = "BULLISH"
    elif price < ema20 and ema20 < ema50:
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
# SWING DETECTION
# =========================================================
def find_swings(df, lookback=2):
    closed = df.iloc[:-1].copy()
    highs = []
    lows = []
    for i in range(
        lookback,
        len(closed) - lookback
    ):
        high = closed.iloc[i]["high"]
        low = closed.iloc[i]["low"]
        left_highs = closed.iloc[
            i - lookback:i
        ]["high"]
        right_highs = closed.iloc[
            i + 1:i + 1 + lookback
        ]["high"]
        left_lows = closed.iloc[
            i - lookback:i
        ]["low"]
        right_lows = closed.iloc[
            i + 1:i + 1 + lookback
        ]["low"]
        if (
            high > left_highs.max()
            and high > right_highs.max()
        ):
            highs.append(
                {
                    "index": i,
                    "price": high
                }
            )
        if (
            low < left_lows.min()
            and low < right_lows.min()
        ):
            lows.append(
                {
                    "index": i,
                    "price": low
                }
            )
    return highs, lows
# =========================================================
# MARKET STRUCTURE
# =========================================================
def detect_market_structure(df):
    highs, lows = find_swings(
        df,
        lookback=2
    )
    structure = "NEUTRAL"
    last_high_type = "NONE"
    last_low_type = "NONE"
    # -------------------------
    # HIGH STRUCTURE
    # -------------------------
    if len(highs) >= 2:
        previous_high = highs[-2]["price"]
        latest_high = highs[-1]["price"]
        if latest_high > previous_high:
            last_high_type = "HH"
        else:
            last_high_type = "LH"
    # -------------------------
    # LOW STRUCTURE
    # -------------------------
    if len(lows) >= 2:
        previous_low = lows[-2]["price"]
        latest_low = lows[-1]["price"]
        if latest_low > previous_low:
            last_low_type = "HL"
        else:
            last_low_type = "LL"
    # -------------------------
    # FINAL STRUCTURE
    # -------------------------
    if (
        last_high_type == "HH"
        and last_low_type == "HL"
    ):
        structure = "BULLISH"
    elif (
        last_high_type == "LH"
        and last_low_type == "LL"
    ):
        structure = "BEARISH"
    elif last_high_type == "HH":
        structure = "BULLISH"
    elif last_low_type == "HL":
        structure = "BULLISH"
    elif last_high_type == "LH":
        structure = "BEARISH"
    elif last_low_type == "LL":
        structure = "BEARISH"
    return {
        "structure": structure,
        "high": last_high_type,
        "low": last_low_type,
        "highs": highs,
        "lows": lows
    }
# =========================================================
# BOS / CHoCH
# =========================================================
def detect_bos_choch(
    df,
    structure
):
    closed = df.iloc[:-1].copy()
    current = closed.iloc[-1]
    highs = structure["highs"]
    lows = structure["lows"]
    bos = "NONE"
    choch = "NONE"
    if len(highs) >= 2:
        previous_swing_high = (
            highs[-2]["price"]
        )
        latest_swing_high = (
            highs[-1]["price"]
        )
        if (
            current["close"]
            > latest_swing_high
        ):
            if structure["structure"] == "BULLISH":
                bos = "BULLISH BOS"
            else:
                choch = "BULLISH CHoCH"
    if len(lows) >= 2:
        previous_swing_low = (
            lows[-2]["price"]
        )
        latest_swing_low = (
            lows[-1]["price"]
        )
        if (
            current["close"]
            < latest_swing_low
        ):
            if structure["structure"] == "BEARISH":
                bos = "BEARISH BOS"
            else:
                choch = "BEARISH CHoCH"
    return {
        "bos": bos,
        "choch": choch
    }
# =========================================================
# CANDLE CONFIRMATION
# =========================================================
def candle_confirmation(df):
    closed = df.iloc[:-1].copy()
    current = closed.iloc[-1]
    previous = closed.iloc[-2]
    body = abs(
        current["close"]
        - current["open"]
    )
    candle_range = (
        current["high"]
        - current["low"]
    )
    if candle_range == 0:
        return "NONE"
    upper_wick = (
        current["high"]
        - max(
            current["open"],
            current["close"]
        )
    )
    lower_wick = (
        min(
            current["open"],
            current["close"]
        )
        - current["low"]
    )
    bullish_engulfing = (
        current["close"] > current["open"]
        and previous["close"]
        < previous["open"]
        and current["close"]
        >= previous["open"]
        and current["open"]
        <= previous["close"]
    )
    bearish_engulfing = (
        current["close"] < current["open"]
        and previous["close"]
        > previous["open"]
        and current["close"]
        <= previous["open"]
        and current["open"]
        >= previous["close"]
    )
    bullish_pin = (
        lower_wick >= body * 2
        and lower_wick > upper_wick
        and current["close"]
        > current["open"]
    )
    bearish_pin = (
        upper_wick >= body * 2
        and upper_wick > lower_wick
        and current["close"]
        < current["open"]
    )
    strong_bullish = (
        current["close"]
        > current["open"]
        and body
        >= candle_range * 0.65
    )
    strong_bearish = (
        current["close"]
        < current["open"]
        and body
        >= candle_range * 0.65
    )
    if bullish_engulfing:
        return "BULLISH ENGULFING"
    if bearish_engulfing:
        return "BEARISH ENGULFING"
    if bullish_pin:
        return "BULLISH REJECTION"
    if bearish_pin:
        return "BEARISH REJECTION"
    if strong_bullish:
        return "BULLISH MOMENTUM"
    if strong_bearish:
        return "BEARISH MOMENTUM"
    return "NONE"
# =========================================================
# LIQUIDITY SWEEP
# =========================================================
def detect_liquidity_sweep(df):
    closed = df.iloc[:-1].copy()
    current = closed.iloc[-1]
    previous = closed.iloc[-6:-1]
    previous_high = previous["high"].max()
    previous_low = previous["low"].min()
    bullish_sweep = (
        current["low"] < previous_low
        and current["close"]
        > previous_low
    )
    bearish_sweep = (
        current["high"] > previous_high
        and current["close"]
        < previous_high
    )
    if bullish_sweep:
        return "BULLISH LIQUIDITY SWEEP"
    if bearish_sweep:
        return "BEARISH LIQUIDITY SWEEP"
    return "NONE"
# =========================================================
# SUPPORT / RESISTANCE
# =========================================================
def get_support_resistance(df):
    closed = df.iloc[:-1].copy()
    recent = closed.tail(80)
    support = (
        recent["low"]
        .nsmallest(5)
        .mean()
    )
    resistance = (
        recent["high"]
        .nlargest(5)
        .mean()
    )
    return support, resistance
# =========================================================
# BREAKOUT
# =========================================================
def detect_breakout(df):
    closed = df.iloc[:-1].copy()
    current = closed.iloc[-1]
    previous = closed.iloc[-6:-1]
    previous_high = previous["high"].max()
    previous_low = previous["low"].min()
    if current["close"] > previous_high:
        return "BULLISH BREAKOUT"
    if current["close"] < previous_low:
        return "BEARISH BREAKOUT"
    return "NONE"
# =========================================================
# SCORING ENGINE V1.3
# =========================================================
def calculate_score(
    h4,
    h1,
    m30,
    m15,
    structure,
    bos_choch,
    candle,
    sweep,
    breakout
):
    buy_score = 0
    sell_score = 0
    # -------------------------
    # H4 = 15
    # -------------------------
    if h4["trend"] == "BULLISH":
        buy_score += 15
    elif h4["trend"] == "BEARISH":
        sell_score += 15
    # -------------------------
    # H1 = 20
    # -------------------------
    if h1["trend"] == "BULLISH":
        buy_score += 20
    elif h1["trend"] == "BEARISH":
        sell_score += 20
    # -------------------------
    # M30 = 15
    # -------------------------
    if m30["trend"] == "BULLISH":
        buy_score += 15
    elif m30["trend"] == "BEARISH":
        sell_score += 15
    # -------------------------
    # M15 = 10
    # -------------------------
    if m15["trend"] == "BULLISH":
        buy_score += 10
    elif m15["trend"] == "BEARISH":
        sell_score += 10
    # -------------------------
    # RSI = 10
    # -------------------------
    if m30["rsi"] > 50:
        buy_score += 10
    elif m30["rsi"] < 50:
        sell_score += 10
    # -------------------------
    # MARKET STRUCTURE = 10
    # -------------------------
    if structure["structure"] == "BULLISH":
        buy_score += 10
    elif structure["structure"] == "BEARISH":
        sell_score += 10
    # -------------------------
    # BOS / CHoCH = 5
    # -------------------------
    if bos_choch["bos"] == "BULLISH BOS":
        buy_score += 5
    elif bos_choch["bos"] == "BEARISH BOS":
        sell_score += 5
    if bos_choch["choch"] == "BULLISH CHoCH":
        buy_score += 5
    elif bos_choch["choch"] == "BEARISH CHoCH":
        sell_score += 5
    # -------------------------
    # CANDLE = 5
    # -------------------------
    if candle.startswith("BULLISH"):
        buy_score += 5
    elif candle.startswith("BEARISH"):
        sell_score += 5
    # -------------------------
    # LIQUIDITY = 5
    # -------------------------
    if sweep == "BULLISH LIQUIDITY SWEEP":
        buy_score += 5
    elif sweep == "BEARISH LIQUIDITY SWEEP":
        sell_score += 5
    # -------------------------
    # BREAKOUT = 5
    # -------------------------
    if breakout == "BULLISH BREAKOUT":
        buy_score += 5
    elif breakout == "BEARISH BREAKOUT":
        sell_score += 5
    # -------------------------
    # FINAL
    # -------------------------
    if buy_score >= sell_score:
        direction = "BUY"
        score = buy_score
    else:
        direction = "SELL"
        score = sell_score
    score = min(
        score,
        100
    )
    if score >= 85:
        signal = f"STRONG {direction}"
    elif score >= 70:
        signal = direction
    elif score >= 55:
        signal = "WATCH"
    else:
        signal = "WAIT"
    return {
        "direction": direction,
        "score": score,
        "signal": signal,
        "buy_score": buy_score,
        "sell_score": sell_score
    }
# =========================================================
# ANALYSIS
# =========================================================
def create_analysis(
    direction,
    structure,
    bos_choch,
    candle,
    sweep,
    breakout
):
    reasons = []
    if direction == "BUY":
        if structure["structure"] == "BULLISH":
            reasons.append(
                "bullish market structure"
            )
        if bos_choch["bos"] == "BULLISH BOS":
            reasons.append(
                "bullish BOS"
            )
        if bos_choch["choch"] == "BULLISH CHoCH":
            reasons.append(
                "bullish CHoCH"
            )
        if candle.startswith("BULLISH"):
            reasons.append(
                candle.lower()
            )
        if sweep == "BULLISH LIQUIDITY SWEEP":
            reasons.append(
                "bullish liquidity sweep"
            )
        if breakout == "BULLISH BREAKOUT":
            reasons.append(
                "bullish breakout"
            )
    else:
        if structure["structure"] == "BEARISH":
            reasons.append(
                "bearish market structure"
            )
        if bos_choch["bos"] == "BEARISH BOS":
            reasons.append(
                "bearish BOS"
            )
        if bos_choch["choch"] == "BEARISH CHoCH":
            reasons.append(
                "bearish CHoCH"
            )
        if candle.startswith("BEARISH"):
            reasons.append(
                candle.lower()
            )
        if sweep == "BEARISH LIQUIDITY SWEEP":
            reasons.append(
                "bearish liquidity sweep"
            )
        if breakout == "BEARISH BREAKOUT":
            reasons.append(
                "bearish breakout"
            )
    if not reasons:
        return (
            "Belum terdapat "
            "konfirmasi price action yang kuat."
        )
    return (
        "Konfirmasi utama: "
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
        f"Telegram status: "
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
        "🤖 XAUUSD AI-STYLE SCANNER V1.3"
    )
    print(
        "===================================="
    )
    # -------------------------
    # TIMEFRAMES
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
    # M30 DATA
    # -------------------------
    m30_df = get_data(
        "30min",
        250
    )
    # -------------------------
    # STRUCTURE
    # -------------------------
    structure = detect_market_structure(
        m30_df
    )
    bos_choch = detect_bos_choch(
        m30_df,
        structure
    )
    # -------------------------
    # OTHER PRICE ACTION
    # -------------------------
    candle = candle_confirmation(
        m30_df
    )
    sweep = detect_liquidity_sweep(
        m30_df
    )
    breakout = detect_breakout(
        m30_df
    )
    support, resistance = (
        get_support_resistance(
            m30_df
        )
    )
    # -------------------------
    # SCORE
    # -------------------------
    score_result = calculate_score(
        h4,
        h1,
        m30,
        m15,
        structure,
        bos_choch,
        candle,
        sweep,
        breakout
    )
    signal = score_result["signal"]
    score = score_result["score"]
    direction = score_result["direction"]
    # -------------------------
    # TRADE PLAN
    # -------------------------
    entry = m30["price"]
    atr = m30["atr"]
    sl = None
    tp1 = None
    tp2 = None
    if signal in [
        "BUY",
        "SELL",
        "STRONG BUY",
        "STRONG SELL"
    ]:
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
        rr1 = abs(
            tp1 - entry
        ) / risk
        rr2 = abs(
            tp2 - entry
        ) / risk
    else:
        rr1 = None
        rr2 = None
    # -------------------------
    # ANALYSIS
    # -------------------------
    analysis = create_analysis(
        direction,
        structure,
        bos_choch,
        candle,
        sweep,
        breakout
    )
    # =====================================================
    # MESSAGE
    # =====================================================
    if signal in [
        "BUY",
        "SELL",
        "STRONG BUY",
        "STRONG SELL"
    ]:
        emoji = (
            "🟢"
            if direction == "BUY"
            else "🔴"
        )
        message = (
            "🤖 XAUUSD AI-STYLE V1.3\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"{emoji} {signal}\n"
            f"📊 Score : {score}/100\n\n"
            "📈 MULTI-TIMEFRAME\n"
            f"H4  : {h4['trend']}\n"
            f"H1  : {h1['trend']}\n"
            f"M30 : {m30['trend']}\n"
            f"M15 : {m15['trend']}\n\n"
            "🏗 MARKET STRUCTURE\n"
            f"Structure : {structure['structure']}\n"
            f"High : {structure['high']}\n"
            f"Low : {structure['low']}\n\n"
            "⚡ BOS / CHoCH\n"
            f"BOS : {bos_choch['bos']}\n"
            f"CHoCH : {bos_choch['choch']}\n\n"
            "💧 LIQUIDITY\n"
            f"{sweep}\n\n"
            "⚡ BREAKOUT\n"
            f"{breakout}\n\n"
            "🕯 CANDLE\n"
            f"{candle}\n\n"
            "📊 INDICATORS\n"
            f"Price : {m30['price']:.2f}\n"
            f"EMA20 : {m30['ema20']:.2f}\n"
            f"EMA50 : {m30['ema50']:.2f}\n"
            f"RSI : {m30['rsi']:.2f}\n"
            f"ATR : {m30['atr']:.2f}\n\n"
            "🧱 LEVELS\n"
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
            f"⏱ M30 Candle : {m30['time']}\n\n"
            "⚠️ Signal only — manage your risk."
        )
    else:
        message = (
            "🤖 XAUUSD AI-STYLE V1.3\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"⚪ {signal}\n"
            f"📊 Score : {score}/100\n\n"
            "📈 MULTI-TIMEFRAME\n"
            f"H4  : {h4['trend']}\n"
            f"H1  : {h1['trend']}\n"
            f"M30 : {m30['trend']}\n"
            f"M15 : {m15['trend']}\n\n"
            "🏗 MARKET STRUCTURE\n"
            f"Structure : {structure['structure']}\n"
            f"High : {structure['high']}\n"
            f"Low : {structure['low']}\n\n"
            "⚡ BOS / CHoCH\n"
            f"BOS : {bos_choch['bos']}\n"
            f"CHoCH : {bos_choch['choch']}\n\n"
            "💧 LIQUIDITY\n"
            f"{sweep}\n\n"
            "⚡ BREAKOUT\n"
            f"{breakout}\n\n"
            "🕯 CANDLE\n"
            f"{candle}\n\n"
            "📊 INDICATORS\n"
            f"Price : {m30['price']:.2f}\n"
            f"EMA20 : {m30['ema20']:.2f}\n"
            f"EMA50 : {m30['ema50']:.2f}\n"
            f"RSI : {m30['rsi']:.2f}\n"
            f"ATR : {m30['atr']:.2f}\n\n"
            "🧱 LEVELS\n"
            f"Support : {support:.2f}\n"
            f"Resistance : {resistance:.2f}\n\n"
            "🤖 ANALYSIS\n"
            f"{analysis}\n\n"
            f"⏱ M30 Candle : {m30['time']}\n\n"
            "⏳ Menunggu konfirmasi price action."
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