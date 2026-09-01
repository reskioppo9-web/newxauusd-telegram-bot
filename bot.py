import os
import requests
import pandas as pd
# =========================================================
# XAUUSD AI-STYLE V1.6.1
# STRUCTURE PHASE + DYNAMIC TRIGGER + SMART FILTER
# =========================================================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TWELVE_DATA_API_KEY = os.environ["TWELVE_DATA_API_KEY"]
SYMBOL = "XAU/USD"
# =========================================================
# DATA
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
# TIMEFRAME TREND
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
# SWING DETECTION
# =========================================================
def find_swings(df, lookback=3):
    closed = df.iloc[:-1].copy()
    highs = []
    lows = []
    for i in range(
        lookback,
        len(closed) - lookback
    ):
        high = closed.iloc[i]["high"]
        low = closed.iloc[i]["low"]
        left_high = closed.iloc[
            i - lookback:i
        ]["high"]
        right_high = closed.iloc[
            i + 1:i + 1 + lookback
        ]["high"]
        left_low = closed.iloc[
            i - lookback:i
        ]["low"]
        right_low = closed.iloc[
            i + 1:i + 1 + lookback
        ]["low"]
        if (
            high > left_high.max()
            and high > right_high.max()
        ):
            highs.append(
                {
                    "index": i,
                    "price": high
                }
            )
        if (
            low < left_low.min()
            and low < right_low.min()
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
    highs, lows = find_swings(df)
    high_type = "NONE"
    low_type = "NONE"
    if len(highs) >= 2:
        previous_high = highs[-2]["price"]
        latest_high = highs[-1]["price"]
        if latest_high > previous_high:
            high_type = "HH"
        elif latest_high < previous_high:
            high_type = "LH"
    if len(lows) >= 2:
        previous_low = lows[-2]["price"]
        latest_low = lows[-1]["price"]
        if latest_low > previous_low:
            low_type = "HL"
        elif latest_low < previous_low:
            low_type = "LL"
    if (
        high_type == "HH"
        and low_type == "HL"
    ):
        structure = "BULLISH"
    elif (
        high_type == "LH"
        and low_type == "LL"
    ):
        structure = "BEARISH"
    elif (
        high_type != "NONE"
        and low_type != "NONE"
    ):
        structure = "MIXED"
    elif high_type in ["HH", "HL"]:
        structure = "BULLISH"
    elif low_type == "LL":
        structure = "BEARISH"
    elif high_type == "LH":
        structure = "BEARISH"
    else:
        structure = "NEUTRAL"
    return {
        "structure": structure,
        "high": high_type,
        "low": low_type,
        "highs": highs,
        "lows": lows
    }
# =========================================================
# STRUCTURE PHASE
# =========================================================
def detect_structure_phase(
    structure,
    bos_choch
):
    current_structure = structure["structure"]
    bos = bos_choch["bos"]
    choch = bos_choch["choch"]
    if choch == "BULLISH CHoCH":
        return "BULLISH TRANSITION"
    if choch == "BEARISH CHoCH":
        return "BEARISH TRANSITION"
    if (
        current_structure == "BULLISH"
        and bos == "BULLISH BOS"
    ):
        return "BULLISH CONTINUATION"
    if (
        current_structure == "BEARISH"
        and bos == "BEARISH BOS"
    ):
        return "BEARISH CONTINUATION"
    if current_structure == "BULLISH":
        return "BULLISH"
    if current_structure == "BEARISH":
        return "BEARISH"
    if current_structure == "MIXED":
        return "MIXED"
    return "NEUTRAL"
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
    if len(highs) >= 1:
        last_high = highs[-1]["price"]
        if current["close"] > last_high:
            if structure["structure"] == "BULLISH":
                bos = "BULLISH BOS"
            elif structure["structure"] in [
                "BEARISH",
                "MIXED"
            ]:
                choch = "BULLISH CHoCH"
    if len(lows) >= 1:
        last_low = lows[-1]["price"]
        if current["close"] < last_low:
            if structure["structure"] == "BEARISH":
                bos = "BEARISH BOS"
            elif structure["structure"] in [
                "BULLISH",
                "MIXED"
            ]:
                choch = "BEARISH CHoCH"
    return {
        "bos": bos,
        "choch": choch
    }
# =========================================================
# CANDLE
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
    if candle_range <= 0:
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
        and previous["close"] < previous["open"]
        and current["close"] >= previous["open"]
        and current["open"] <= previous["close"]
    )
    bearish_engulfing = (
        current["close"] < current["open"]
        and previous["close"] > previous["open"]
        and current["close"] <= previous["open"]
        and current["open"] >= previous["close"]
    )
    bullish_pin = (
        lower_wick >= body * 2
        and lower_wick > upper_wick
        and current["close"] > current["open"]
    )
    bearish_pin = (
        upper_wick >= body * 2
        and upper_wick > lower_wick
        and current["close"] < current["open"]
    )
    strong_bullish = (
        current["close"] > current["open"]
        and body >= candle_range * 0.65
    )
    strong_bearish = (
        current["close"] < current["open"]
        and body >= candle_range * 0.65
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
    bullish = (
        current["low"] < previous_low
        and current["close"] > previous_low
    )
    bearish = (
        current["high"] > previous_high
        and current["close"] < previous_high
    )
    if bullish:
        return "BULLISH LIQUIDITY SWEEP"
    if bearish:
        return "BEARISH LIQUIDITY SWEEP"
    return "NONE"
# =========================================================
# SMART SUPPORT / RESISTANCE
# =========================================================
def smart_levels(df, atr):
    closed = df.iloc[:-1].copy()
    price = closed.iloc[-1]["close"]
    highs, lows = find_swings(
        df,
        lookback=3
    )
    min_distance = atr * 1.5
    supports = []
    resistances = []
    for swing in lows:
        level = swing["price"]
        if (
            level < price
            and price - level >= min_distance
        ):
            supports.append(level)
    for swing in highs:
        level = swing["price"]
        if (
            level > price
            and level - price >= min_distance
        ):
            resistances.append(level)
    if supports:
        support = max(supports)
    else:
        support = price - (
            atr * 3
        )
    if resistances:
        resistance = min(resistances)
    else:
        resistance = price + (
            atr * 3
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
# EXHAUSTION
# =========================================================
def detect_exhaustion(m30):
    rsi = m30["rsi"]
    if rsi >= 75:
        return "EXTREME OVERBOUGHT"
    if rsi >= 70:
        return "OVERBOUGHT"
    if rsi <= 25:
        return "EXTREME OVERSOLD"
    if rsi <= 30:
        return "OVERSOLD"
    return "NONE"
# =========================================================
# COUNTER-TREND ANALYSIS
# =========================================================
def analyze_counter_trend(
    direction,
    candle,
    sweep
):
    warnings = []
    if direction == "SELL":
        if candle.startswith("BULLISH"):
            warnings.append(
                "Bullish counter-momentum"
            )
        if sweep == "BULLISH LIQUIDITY SWEEP":
            warnings.append(
                "Bullish liquidity sweep"
            )
    elif direction == "BUY":
        if candle.startswith("BEARISH"):
            warnings.append(
                "Bearish counter-momentum"
            )
        if sweep == "BEARISH LIQUIDITY SWEEP":
            warnings.append(
                "Bearish liquidity sweep"
            )
    return warnings
# =========================================================
# SCORE
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
    buy = 0
    sell = 0
    # H4
    if h4["trend"] == "BULLISH":
        buy += 15
    elif h4["trend"] == "BEARISH":
        sell += 15
    # H1
    if h1["trend"] == "BULLISH":
        buy += 20
    elif h1["trend"] == "BEARISH":
        sell += 20
    # M30
    if m30["trend"] == "BULLISH":
        buy += 15
    elif m30["trend"] == "BEARISH":
        sell += 15
    # M15
    if m15["trend"] == "BULLISH":
        buy += 10
    elif m15["trend"] == "BEARISH":
        sell += 10
    # RSI
    if (
        m30["rsi"] > 50
        and m30["rsi"] < 70
    ):
        buy += 10
    elif (
        m30["rsi"] < 50
        and m30["rsi"] > 30
    ):
        sell += 10
    # STRUCTURE
    if structure["structure"] == "BULLISH":
        buy += 10
    elif structure["structure"] == "BEARISH":
        sell += 10
    # BOS
    if bos_choch["bos"] == "BULLISH BOS":
        buy += 10
    elif bos_choch["bos"] == "BEARISH BOS":
        sell += 10
    # CHoCH
    if bos_choch["choch"] == "BULLISH CHoCH":
        buy += 8
    elif bos_choch["choch"] == "BEARISH CHoCH":
        sell += 8
    # CANDLE
    if candle.startswith("BULLISH"):
        buy += 5
    elif candle.startswith("BEARISH"):
        sell += 5
    # LIQUIDITY
    if sweep == "BULLISH LIQUIDITY SWEEP":
        buy += 5
    elif sweep == "BEARISH LIQUIDITY SWEEP":
        sell += 5
    # BREAKOUT
    if breakout == "BULLISH BREAKOUT":
        buy += 5
    elif breakout == "BEARISH BREAKOUT":
        sell += 5
    if buy > sell:
        direction = "BUY"
        score = buy
    elif sell > buy:
        direction = "SELL"
        score = sell
    else:
        direction = "NEUTRAL"
        score = max(
            buy,
            sell
        )
    return {
        "direction": direction,
        "score": min(score, 100),
        "buy": buy,
        "sell": sell
    }
# =========================================================
# ENTRY QUALITY
# =========================================================
def calculate_entry_quality(
    direction,
    m30,
    exhaustion,
    counter_warnings,
    breakout
):
    quality = 100
    reasons = []
    if exhaustion == "EXTREME OVERBOUGHT":
        quality -= 25
        reasons.append(
            "Extreme overbought"
        )
    elif exhaustion == "OVERBOUGHT":
        quality -= 15
        reasons.append(
            "Overbought"
        )
    elif exhaustion == "EXTREME OVERSOLD":
        quality -= 25
        reasons.append(
            "Extreme oversold"
        )
    elif exhaustion == "OVERSOLD":
        quality -= 15
        reasons.append(
            "Oversold"
        )
    if counter_warnings:
        quality -= (
            10 * len(counter_warnings)
        )
        reasons.extend(
            counter_warnings
        )
    if breakout != "NONE":
        quality += 5
    quality = max(
        0,
        min(
            quality,
            100
        )
    )
    return quality, reasons
# =========================================================
# DYNAMIC NEXT TRIGGER
# =========================================================
def get_next_trigger(
    structure,
    bos_choch,
    structure_phase,
    direction
):
    choch = bos_choch["choch"]
    bos = bos_choch["bos"]
    # CHoCH already happened
    if choch == "BULLISH CHoCH":
        return (
            "🟢 BUY CONTINUATION\n"
            "➡️ Wait for bullish retest\n"
            "➡️ Hold above broken structure\n"
            "➡️ Bullish confirmation"
        )
    if choch == "BEARISH CHoCH":
        return (
            "🔴 SELL CONTINUATION\n"
            "➡️ Wait for bearish retest\n"
            "➡️ Hold below broken structure\n"
            "➡️ Bearish confirmation"
        )
    # BOS already confirmed
    if bos == "BULLISH BOS":
        return (
            "🟢 BUY CONTINUATION\n"
            "➡️ Retest breakout area\n"
            "➡️ Bullish rejection\n"
            "➡️ Continuation"
        )
    if bos == "BEARISH BOS":
        return (
            "🔴 SELL CONTINUATION\n"
            "➡️ Retest breakout area\n"
            "➡️ Bearish rejection\n"
            "➡️ Continuation"
        )
    # Existing structure
    if structure["structure"] == "BULLISH":
        return (
            "🟢 BUY\n"
            "➡️ Bullish CHoCH / BOS\n"
            "➡️ Break HH\n"
            "➡️ Retest"
        )
    if structure["structure"] == "BEARISH":
        return (
            "🔴 SELL\n"
            "➡️ Bearish CHoCH / BOS\n"
            "➡️ Break LL\n"
            "➡️ Retest"
        )
    if structure["structure"] == "MIXED":
        return (
            "🟢 BUY: bullish CHoCH + break HH + retest\n"
            "🔴 SELL: bearish CHoCH + break LL + retest"
        )
    return (
        "Wait for clear BOS / CHoCH"
    )
# =========================================================
# DECISION FILTER
# =========================================================
def make_decision(
    score_result,
    m30,
    structure,
    bos_choch,
    entry_quality,
    exhaustion
):
    direction = score_result["direction"]
    score = score_result["score"]
    reasons = []
    # MIXED
    if structure["structure"] == "MIXED":
        reasons.append(
            "Market structure mixed"
        )
        return (
            "WAIT",
            reasons
        )
    # BUY
    if direction == "BUY":
        if (
            structure["structure"] == "BEARISH"
            and bos_choch["choch"]
            != "BULLISH CHoCH"
        ):
            reasons.append(
                "Market structure bearish"
            )
            return (
                "WAIT",
                reasons
            )
        if m30["rsi"] > 70:
            reasons.append(
                "RSI overbought"
            )
            return (
                "WAIT",
                reasons
            )
    # SELL
    if direction == "SELL":
        if (
            structure["structure"] == "BULLISH"
            and bos_choch["choch"]
            != "BEARISH CHoCH"
        ):
            reasons.append(
                "Market structure bullish"
            )
            return (
                "WAIT",
                reasons
            )
        if m30["rsi"] < 30:
            reasons.append(
                "RSI oversold"
            )
            return (
                "WAIT",
                reasons
            )
    # Entry quality
    if entry_quality < 60:
        reasons.append(
            f"Entry quality low ({entry_quality}/100)"
        )
        return (
            "WAIT",
            reasons
        )
    # Extreme exhaustion
    if exhaustion in [
        "EXTREME OVERBOUGHT",
        "EXTREME OVERSOLD"
    ]:
        reasons.append(
            exhaustion
        )
        return (
            "WAIT",
            reasons
        )
    # Score
    if score < 70:
        reasons.append(
            "Confidence below 70"
        )
        return (
            "WAIT",
            reasons
        )
    if score >= 85:
        return (
            f"STRONG {direction}",
            reasons
        )
    return (
        direction,
        reasons
    )
# =========================================================
# ANALYSIS
# =========================================================
def create_analysis(
    direction,
    structure,
    structure_phase,
    bos_choch,
    candle,
    sweep,
    breakout,
    exhaustion,
    counter_warnings
):
    reasons = []
    # Structure
    if structure["structure"] == "BULLISH":
        reasons.append(
            "bullish market structure"
        )
    elif structure["structure"] == "BEARISH":
        reasons.append(
            "bearish market structure"
        )
    elif structure["structure"] == "MIXED":
        reasons.append(
            "mixed market structure"
        )
    # Phase
    if structure_phase not in [
        "BULLISH",
        "BEARISH",
        "NEUTRAL"
    ]:
        reasons.append(
            structure_phase.lower()
        )
    # BOS / CHoCH
    if bos_choch["bos"] != "NONE":
        reasons.append(
            bos_choch["bos"]
        )
    if bos_choch["choch"] != "NONE":
        reasons.append(
            bos_choch["choch"]
        )
    # Candle
    if candle != "NONE":
        if direction == "SELL" and candle.startswith("BULLISH"):
            reasons.append(
                "bullish counter-momentum"
            )
        elif direction == "BUY" and candle.startswith("BEARISH"):
            reasons.append(
                "bearish counter-momentum"
            )
        else:
            reasons.append(
                candle.lower()
            )
    # Liquidity
    if sweep != "NONE":
        if (
            direction == "SELL"
            and sweep == "BULLISH LIQUIDITY SWEEP"
        ):
            reasons.append(
                "bullish liquidity sweep"
            )
        elif (
            direction == "BUY"
            and sweep == "BEARISH LIQUIDITY SWEEP"
        ):
            reasons.append(
                "bearish liquidity sweep"
            )
        else:
            reasons.append(
                sweep.lower()
            )
    # Breakout
    if breakout != "NONE":
        reasons.append(
            breakout.lower()
        )
    # Exhaustion
    if exhaustion != "NONE":
        reasons.append(
            exhaustion.lower()
        )
    if not reasons:
        return (
            "Belum ada konfirmasi kuat."
        )
    return (
        " | ".join(reasons)
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
    response.raise_for_status()
    print(
        "✅ Telegram message sent!"
    )
# =========================================================
# MAIN
# =========================================================
def main():
    print(
        "================================"
    )
    print(
        "🤖 XAUUSD AI-STYLE V1.6.1"
    )
    print(
        "================================"
    )
    # -----------------------------------------------------
    # TIMEFRAMES
    # -----------------------------------------------------
    h4 = analyze_timeframe("4h")
    h1 = analyze_timeframe("1h")
    m30 = analyze_timeframe("30min")
    m15 = analyze_timeframe("15min")
    # -----------------------------------------------------
    # M30 ANALYSIS
    # -----------------------------------------------------
    m30_df = get_data(
        "30min",
        250
    )
    structure = detect_market_structure(
        m30_df
    )
    bos_choch = detect_bos_choch(
        m30_df,
        structure
    )
    structure_phase = detect_structure_phase(
        structure,
        bos_choch
    )
    candle = candle_confirmation(
        m30_df
    )
    sweep = detect_liquidity_sweep(
        m30_df
    )
    breakout = detect_breakout(
        m30_df
    )
    support, resistance = smart_levels(
        m30_df,
        m30["atr"]
    )
    exhaustion = detect_exhaustion(
        m30
    )
    # -----------------------------------------------------
    # SCORE
    # -----------------------------------------------------
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
    direction = score_result["direction"]
    score = score_result["score"]
    # -----------------------------------------------------
    # COUNTER TREND
    # -----------------------------------------------------
    counter_warnings = analyze_counter_trend(
        direction,
        candle,
        sweep
    )
    # -----------------------------------------------------
    # ENTRY QUALITY
    # -----------------------------------------------------
    entry_quality, quality_reasons = calculate_entry_quality(
        direction,
        m30,
        exhaustion,
        counter_warnings,
        breakout
    )
    # -----------------------------------------------------
    # DECISION
    # -----------------------------------------------------
    signal, rejection_reasons = make_decision(
        score_result,
        m30,
        structure,
        bos_choch,
        entry_quality,
        exhaustion
    )
    # -----------------------------------------------------
    # TRADE PLAN
    # -----------------------------------------------------
    entry = m30["price"]
    atr = m30["atr"]
    sl = None
    tp1 = None
    tp2 = None
    rr1 = None
    rr2 = None
    valid_trade = signal in [
        "BUY",
        "SELL",
        "STRONG BUY",
        "STRONG SELL"
    ]
    if valid_trade:
        if direction == "BUY":
            sl = entry - (
                1.5 * atr
            )
            tp1 = entry + (
                2.25 * atr
            )
            tp2 = entry + (
                3.75 * atr
            )
        elif direction == "SELL":
            sl = entry + (
                1.5 * atr
            )
            tp1 = entry - (
                2.25 * atr
            )
            tp2 = entry - (
                3.75 * atr
            )
        risk = abs(
            entry - sl
        )
        rr1 = abs(
            tp1 - entry
        ) / risk
        rr2 = abs(
            tp2 - entry
        ) / risk
        if rr1 < 1.5:
            valid_trade = False
            signal = "WAIT"
            rejection_reasons.append(
                "TP1 RR below 1:1.5"
            )
    # -----------------------------------------------------
    # NEXT TRIGGER
    # -----------------------------------------------------
    next_trigger = get_next_trigger(
        structure,
        bos_choch,
        structure_phase,
        direction
    )
    # -----------------------------------------------------
    # ANALYSIS
    # -----------------------------------------------------
    analysis = create_analysis(
        direction,
        structure,
        structure_phase,
        bos_choch,
        candle,
        sweep,
        breakout,
        exhaustion,
        counter_warnings
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
        warning_text = ""
        if quality_reasons:
            warning_text = (
                "\n⚠️ ENTRY WARNING\n"
                + "\n".join(
                    f"• {x}"
                    for x in quality_reasons
                )
                + "\n"
            )
        message = (
            "🤖 XAUUSD AI-STYLE V1.6.1\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"{emoji} {signal}\n"
            f"📊 Confidence : {score}/100\n"
            f"🎯 Entry Quality : {entry_quality}/100\n\n"
            "📈 MULTI-TIMEFRAME\n"
            f"H4  : {h4['trend']}\n"
            f"H1  : {h1['trend']}\n"
            f"M30 : {m30['trend']}\n"
            f"M15 : {m15['trend']}\n\n"
            "🏗 MARKET STRUCTURE\n"
            f"Structure : {structure['structure']}\n"
            f"High : {structure['high']}\n"
            f"Low : {structure['low']}\n"
            f"Phase : {structure_phase}\n\n"
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
            "🧱 SMART LEVELS\n"
            f"Support : {support:.2f}\n"
            f"Resistance : {resistance:.2f}\n\n"
            "🛡 SMART FILTER\n"
            f"Exhaustion : {exhaustion}\n"
            f"Entry Quality : {entry_quality}/100\n"
            f"{warning_text}\n"
            "🎯 TRADE PLAN\n"
            f"Entry : {entry:.2f}\n"
            f"SL : {sl:.2f}\n"
            f"TP1 : {tp1:.2f}\n"
            f"TP2 : {tp2:.2f}\n\n"
            "📐 RISK / REWARD\n"
            f"TP1 : 1:{rr1:.2f}\n"
            f"TP2 : 1:{rr2:.2f}\n\n"
            "🎯 NEXT TRIGGER\n"
            f"{next_trigger}\n\n"
            "🤖 ANALYSIS\n"
            f"{analysis}\n\n"
            f"⏱ Candle : {m30['time']}\n\n"
            "⚠️ Signal only — manage your risk."
        )
    else:
        reason_text = "\n".join(
            f"• {x}"
            for x in rejection_reasons
        )
        if not reason_text:
            reason_text = (
                "• Konfirmasi belum cukup kuat"
            )
        message = (
            "🤖 XAUUSD AI-STYLE V1.6.1\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"⚪ {signal}\n"
            f"📊 Confidence : {score}/100\n"
            f"🎯 Entry Quality : {entry_quality}/100\n\n"
            "📈 MULTI-TIMEFRAME\n"
            f"H4  : {h4['trend']}\n"
            f"H1  : {h1['trend']}\n"
            f"M30 : {m30['trend']}\n"
            f"M15 : {m15['trend']}\n\n"
            "🏗 MARKET STRUCTURE\n"
            f"Structure : {structure['structure']}\n"
            f"High : {structure['high']}\n"
            f"Low : {structure['low']}\n"
            f"Phase : {structure_phase}\n\n"
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
            "🧱 SMART LEVELS\n"
            f"Support : {support:.2f}\n"
            f"Resistance : {resistance:.2f}\n\n"
            "🛡 SMART FILTER\n"
            f"Exhaustion : {exhaustion}\n"
            f"Entry Quality : {entry_quality}/100\n"
            f"{reason_text}\n\n"
            "🎯 NEXT TRIGGER\n"
            f"{next_trigger}\n\n"
            "🤖 ANALYSIS\n"
            f"{analysis}\n\n"
            f"⏱ Candle : {m30['time']}\n\n"
            "⏳ Menunggu setup berkualitas."
        )
    print(message)
    send_telegram(message)
    print(
        "================================"
    )
    print(
        "✅ V1.6.1 FINISHED"
    )
    print(
        "================================"
    )
# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    main()