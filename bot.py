import os
import requests
import pandas as pd

# =========================================================
# XAUUSD AI-STYLE V1.6.2
# STRICT ENTRY ENGINE
# TREND + STRUCTURE + TRIGGER + ENTRY QUALITY
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
# RSI
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


# =========================================================
# ATR
# =========================================================

def calculate_atr(df, length=14):

    previous_close = df["close"].shift(1)

    tr1 = (
        df["high"]
        - df["low"]
    )

    tr2 = abs(
        df["high"]
        - previous_close
    )

    tr3 = abs(
        df["low"]
        - previous_close
    )

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    return true_range.ewm(
        alpha=1 / length,
        adjust=False
    ).mean()


# =========================================================
# INDICATORS
# =========================================================

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
# TIMEFRAME
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
# SWINGS
# =========================================================

def find_swings(
    df,
    lookback=3
):

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

            highs.append({
                "index": i,
                "price": high
            })

        if (
            low < left_low.min()
            and low < right_low.min()
        ):

            lows.append({
                "index": i,
                "price": low
            })

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

    elif high_type in [
        "HH",
        "HL"
    ]:

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
# LIQUIDITY
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
# SMART LEVELS
# =========================================================

def smart_levels(
    df,
    atr
):

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
# DISTANCE FROM EMA20
# =========================================================

def detect_entry_distance(m30):

    price = m30["price"]

    ema20 = m30["ema20"]

    atr = m30["atr"]

    distance = abs(
        price - ema20
    )

    if atr <= 0:
        return "NORMAL", 0

    ratio = distance / atr

    if ratio >= 2.0:
        return "EXTENDED", ratio

    if ratio >= 1.5:
        return "FAR", ratio

    return "NORMAL", ratio


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
# ENTRY QUALITY V1.6.2
# =========================================================

def calculate_entry_quality(
    direction,
    m30,
    structure,
    bos_choch,
    candle,
    sweep,
    breakout,
    exhaustion,
    distance_status
):

    quality = 100

    reasons = []

    # -----------------------------------------------------
    # STRUCTURE
    # -----------------------------------------------------

    if direction == "BUY":

        if structure["structure"] != "BULLISH":

            quality -= 25

            reasons.append(
                "Structure not bullish"
            )

    elif direction == "SELL":

        if structure["structure"] != "BEARISH":

            quality -= 25

            reasons.append(
                "Structure not bearish"
            )

    # -----------------------------------------------------
    # TRIGGER
    # -----------------------------------------------------

    trigger = (
        bos_choch["bos"] != "NONE"
        or bos_choch["choch"] != "NONE"
        or breakout != "NONE"
    )

    if not trigger:

        quality -= 20

        reasons.append(
            "No BOS / CHoCH / breakout trigger"
        )

    # -----------------------------------------------------
    # CANDLE
    # -----------------------------------------------------

    if direction == "BUY":

        if not candle.startswith("BULLISH"):

            quality -= 10

            reasons.append(
                "No bullish candle confirmation"
            )

    elif direction == "SELL":

        if not candle.startswith("BEARISH"):

            quality -= 10

            reasons.append(
                "No bearish candle confirmation"
            )

    # -----------------------------------------------------
    # EXHAUSTION
    # -----------------------------------------------------

    if exhaustion == "EXTREME OVERBOUGHT":

        if direction == "BUY":

            quality -= 30

            reasons.append(
                "Extreme overbought"
            )

    elif exhaustion == "EXTREME OVERSOLD":

        if direction == "SELL":

            quality -= 30

            reasons.append(
                "Extreme oversold"
            )

    elif exhaustion == "OVERBOUGHT":

        if direction == "BUY":

            quality -= 15

            reasons.append(
                "Overbought"
            )

    elif exhaustion == "OVERSOLD":

        if direction == "SELL":

            quality -= 15

            reasons.append(
                "Oversold"
            )

    # -----------------------------------------------------
    # DISTANCE
    # -----------------------------------------------------

    if distance_status == "EXTENDED":

        quality -= 25

        reasons.append(
            "Price extended > 2 ATR from EMA20"
        )

    elif distance_status == "FAR":

        quality -= 10

        reasons.append(
            "Price far from EMA20"
        )

    # -----------------------------------------------------
    # COUNTER MOMENTUM
    # -----------------------------------------------------

    if direction == "SELL":

        if candle.startswith("BULLISH"):

            quality -= 15

            reasons.append(
                "Bullish counter-momentum"
            )

        if sweep == "BULLISH LIQUIDITY SWEEP":

            quality -= 10

            reasons.append(
                "Bullish liquidity sweep"
            )

    elif direction == "BUY":

        if candle.startswith("BEARISH"):

            quality -= 15

            reasons.append(
                "Bearish counter-momentum"
            )

        if sweep == "BEARISH LIQUIDITY SWEEP":

            quality -= 10

            reasons.append(
                "Bearish liquidity sweep"
            )

    quality = max(
        0,
        min(
            quality,
            100
        )
    )

    return quality, reasons


# =========================================================
# DECISION V1.6.2
# =========================================================

def make_decision(
    score_result,
    structure,
    bos_choch,
    candle,
    breakout,
    entry_quality,
    exhaustion,
    distance_status
):

    direction = score_result["direction"]

    score = score_result["score"]

    reasons = []

    # -----------------------------------------------------
    # MIXED
    # -----------------------------------------------------

    if structure["structure"] == "MIXED":

        reasons.append(
            "Market structure mixed"
        )

        return "WAIT", reasons

    # -----------------------------------------------------
    # NO DIRECTION
    # -----------------------------------------------------

    if direction == "NEUTRAL":

        reasons.append(
            "No dominant direction"
        )

        return "WAIT", reasons

    # -----------------------------------------------------
    # EXTREME EXHAUSTION
    # -----------------------------------------------------

    if exhaustion in [
        "EXTREME OVERBOUGHT",
        "EXTREME OVERSOLD"
    ]:

        reasons.append(
            exhaustion
        )

        return "WAIT", reasons

    # -----------------------------------------------------
    # ENTRY TOO FAR
    # -----------------------------------------------------

    if distance_status == "EXTENDED":

        reasons.append(
            "Price too extended from EMA20"
        )

        return "WAIT", reasons

    # -----------------------------------------------------
    # STRUCTURE ALIGNMENT
    # -----------------------------------------------------

    if direction == "BUY":

        if structure["structure"] != "BULLISH":

            reasons.append(
                "BUY blocked by bearish/non-bullish structure"
            )

            return "WAIT", reasons

    elif direction == "SELL":

        if structure["structure"] != "BEARISH":

            reasons.append(
                "SELL blocked by bullish/non-bearish structure"
            )

            return "WAIT", reasons

    # -----------------------------------------------------
    # SCORE
    # -----------------------------------------------------

    if score < 70:

        reasons.append(
            "Confidence below 70"
        )

        return "WAIT", reasons

    # -----------------------------------------------------
    # ENTRY QUALITY
    # -----------------------------------------------------

    if entry_quality < 70:

        reasons.append(
            f"Entry quality below 70 ({entry_quality}/100)"
        )

        return "WAIT", reasons

    # -----------------------------------------------------
    # TRIGGER
    # -----------------------------------------------------

    trigger = (
        bos_choch["bos"] != "NONE"
        or bos_choch["choch"] != "NONE"
        or breakout != "NONE"
    )

    # -----------------------------------------------------
    # STRICT STRONG SIGNAL
    # -----------------------------------------------------

    if score >= 85:

        if (
            entry_quality >= 85
            and trigger
        ):

            return (
                f"STRONG {direction}",
                reasons
            )

        reasons.append(
            "Strong signal requires structural trigger"
        )

        return "WAIT", reasons

    # -----------------------------------------------------
    # NORMAL SIGNAL
    # -----------------------------------------------------

    if not trigger:

        reasons.append(
            "Waiting for BOS / CHoCH / breakout"
        )

        return "WAIT", reasons

    if direction == "SELL":

        if not candle.startswith("BEARISH"):

            reasons.append(
                "Waiting for bearish candle confirmation"
            )

            return "WAIT", reasons

    elif direction == "BUY":

        if not candle.startswith("BULLISH"):

            reasons.append(
                "Waiting for bullish candle confirmation"
            )

            return "WAIT", reasons

    return direction, reasons


# =========================================================
# NEXT TRIGGER
# =========================================================

def get_next_trigger(
    structure,
    bos_choch,
    direction
):

    if bos_choch["choch"] == "BULLISH CHoCH":

        return (
            "🟢 BUY CONTINUATION\n"
            "➡️ Retest broken structure\n"
            "➡️ Hold above level\n"
            "➡️ Bullish confirmation"
        )

    if bos_choch["choch"] == "BEARISH CHoCH":

        return (
            "🔴 SELL CONTINUATION\n"
            "➡️ Retest broken structure\n"
            "➡️ Hold below level\n"
            "➡️ Bearish confirmation"
        )

    if bos_choch["bos"] == "BULLISH BOS":

        return (
            "🟢 BUY CONTINUATION\n"
            "➡️ Retest breakout area\n"
            "➡️ Bullish rejection\n"
            "➡️ Continuation"
        )

    if bos_choch["bos"] == "BEARISH BOS":

        return (
            "🔴 SELL CONTINUATION\n"
            "➡️ Retest breakout area\n"
            "➡️ Bearish rejection\n"
            "➡️ Continuation"
        )

    if structure["structure"] == "BULLISH":

        return (
            "🟢 BUY SETUP\n"
            "➡️ Bullish BOS / CHoCH\n"
            "➡️ Break HH\n"
            "➡️ Retest + bullish confirmation"
        )

    if structure["structure"] == "BEARISH":

        return (
            "🔴 SELL SETUP\n"
            "➡️ Bearish BOS / CHoCH\n"
            "➡️ Break LL\n"
            "➡️ Retest + bearish confirmation"
        )

    return (
        "Wait for clear BOS / CHoCH"
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
    distance_status
):

    reasons = []

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

    if structure_phase not in [
        "BULLISH",
        "BEARISH",
        "NEUTRAL"
    ]:

        reasons.append(
            structure_phase.lower()
        )

    if bos_choch["bos"] != "NONE":

        reasons.append(
            bos_choch["bos"]
        )

    if bos_choch["choch"] != "NONE":

        reasons.append(
            bos_choch["choch"]
        )

    if candle != "NONE":

        reasons.append(
            candle.lower()
        )

    if sweep != "NONE":

        reasons.append(
            sweep.lower()
        )

    if breakout != "NONE":

        reasons.append(
            breakout.lower()
        )

    if exhaustion != "NONE":

        reasons.append(
            exhaustion.lower()
        )

    if distance_status != "NORMAL":

        reasons.append(
            f"price {distance_status.lower()} from EMA20"
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
        "🤖 XAUUSD AI-STYLE V1.6.2"
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
    # M30
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

    distance_status, distance_ratio = (
        detect_entry_distance(m30)
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
    # ENTRY QUALITY
    # -----------------------------------------------------

    entry_quality, quality_reasons = (
        calculate_entry_quality(
            direction,
            m30,
            structure,
            bos_choch,
            candle,
            sweep,
            breakout,
            exhaustion,
            distance_status
        )
    )

    # -----------------------------------------------------
    # DECISION
    # -----------------------------------------------------

    signal, rejection_reasons = make_decision(
        score_result,
        structure,
        bos_choch,
        candle,
        breakout,
        entry_quality,
        exhaustion,
        distance_status
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
        distance_status
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

            "🤖 XAUUSD AI-STYLE V1.6.2\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            f"{emoji} {signal}\n"

            f"📊 Confidence : "
            f"{score}/100\n"

            f"🎯 Entry Quality : "
            f"{entry_quality}/100\n\n"

            "📈 MULTI-TIMEFRAME\n"

            f"H4  : {h4['trend']}\n"
            f"H1  : {h1['trend']}\n"
            f"M30 : {m30['trend']}\n"
            f"M15 : {m15['trend']}\n\n"

            "🏗 MARKET STRUCTURE\n"

            f"Structure : "
            f"{structure['structure']}\n"

            f"High : {structure['high']}\n"

            f"Low : {structure['low']}\n"

            f"Phase : "
            f"{structure_phase}\n\n"

            "⚡ BOS / CHoCH\n"

            f"BOS : "
            f"{bos_choch['bos']}\n"

            f"CHoCH : "
            f"{bos_choch['choch']}\n\n"

            "💧 LIQUIDITY\n"

            f"{sweep}\n\n"

            "⚡ BREAKOUT\n"

            f"{breakout}\n\n"

            "🕯 CANDLE\n"

            f"{candle}\n\n"

            "📊 INDICATORS\n"

            f"Price : "
            f"{m30['price']:.2f}\n"

            f"EMA20 : "
            f"{m30['ema20']:.2f}\n"

            f"EMA50 : "
            f"{m30['ema50']:.2f}\n"

            f"RSI : "
            f"{m30['rsi']:.2f}\n"

            f"ATR : "
            f"{m30['atr']:.2f}\n"

            f"EMA Distance : "
            f"{distance_ratio:.2f} ATR\n\n"

            "🧱 SMART LEVELS\n"

            f"Support : "
            f"{support:.2f}\n"

            f"Resistance : "
            f"{resistance:.2f}\n\n"

            "🛡 SMART FILTER\n"

            f"Exhaustion : "
            f"{exhaustion}\n"

            f"Entry Quality : "
            f"{entry_quality}/100\n"

            f"{warning_text}\n"

            "🎯 TRADE PLAN\n"

            f"Entry : "
            f"{entry:.2f}\n"

            f"SL : "
            f"{sl:.2f}\n"

            f"TP1 : "
            f"{tp1:.2f}\n"

            f"TP2 : "
            f"{tp2:.2f}\n\n"

            "📐 RISK / REWARD\n"

            f"TP1 : "
            f"1:{rr1:.2f}\n"

            f"TP2 : "
            f"1:{rr2:.2f}\n\n"

            "🎯 NEXT TRIGGER\n"

            f"{next_trigger}\n\n"

            "🤖 ANALYSIS\n"

            f"{analysis}\n\n"

            f"⏱ Candle : "
            f"{m30['time']}\n\n"

            "⚠️ Signal only — manage your risk."
        )

    else:

        reason_list = (
            rejection_reasons
            + [
                x
                for x in quality_reasons
                if x not in rejection_reasons
            ]
        )

        reason_text = "\n".join(
            f"• {x}"
            for x in reason_list
        )

        if not reason_text:

            reason_text = (
                "• Konfirmasi belum cukup kuat"
            )

        message = (

            "🤖 XAUUSD AI-STYLE V1.6.2\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            f"⚪ {signal}\n"

            f"📊 Confidence : "
            f"{score}/100\n"

            f"🎯 Entry Quality : "
            f"{entry_quality}/100\n\n"

            "📈 MULTI-TIMEFRAME\n"

            f"H4  : {h4['trend']}\n"
            f"H1  : {h1['trend']}\n"
            f"M30 : {m30['trend']}\n"
            f"M15 : {m15['trend']}\n\n"

            "🏗 MARKET STRUCTURE\n"

            f"Structure : "
            f"{structure['structure']}\n"

            f"High : {structure['high']}\n"

            f"Low : {structure['low']}\n"

            f"Phase : "
            f"{structure_phase}\n\n"

            "⚡ BOS / CHoCH\n"

            f"BOS : "
            f"{bos_choch['bos']}\n"

            f"CHoCH : "
            f"{bos_choch['choch']}\n\n"

            "💧 LIQUIDITY\n"

            f"{sweep}\n\n"

            "⚡ BREAKOUT\n"

            f"{breakout}\n\n"

            "🕯 CANDLE\n"

            f"{candle}\n\n"

            "📊 INDICATORS\n"

            f"Price : "
            f"{m30['price']:.2f}\n"

            f"EMA20 : "
            f"{m30['ema20']:.2f}\n"

            f"EMA50 : "
            f"{m30['ema50']:.2f}\n"

            f"RSI : "
            f"{m30['rsi']:.2f}\n"

            f"ATR : "
            f"{m30['atr']:.2f}\n"

            f"EMA Distance : "
            f"{distance_ratio:.2f} ATR\n\n"

            "🧱 SMART LEVELS\n"

            f"Support : "
            f"{support:.2f}\n"

            f"Resistance : "
            f"{resistance:.2f}\n\n"

            "🛡 SMART FILTER\n"

            f"Exhaustion : "
            f"{exhaustion}\n"

            f"Entry Quality : "
            f"{entry_quality}/100\n\n"

            f"{reason_text}\n\n"

            "🎯 NEXT TRIGGER\n"

            f"{next_trigger}\n\n"

            "🤖 ANALYSIS\n"

            f"{analysis}\n\n"

            f"⏱ Candle : "
            f"{m30['time']}\n\n"

            "⏳ Menunggu setup berkualitas."
        )

    print(message)

    send_telegram(message)

    print(
        "================================"
    )

    print(
        "✅ V1.6.2 FINISHED"
    )

    print(
        "================================"
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()