import os
import requests
import pandas as pd
import numpy as np

# ============================================================
# XAUUSD AI-STYLE V1.6.5
# MARKET STRUCTURE + MTF + DUAL TRIGGER ENGINE
# ============================================================

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TWELVE_DATA_API_KEY = os.environ["TWELVE_DATA_API_KEY"]

SYMBOL = "XAU/USD"
BASE_URL = "https://api.twelvedata.com/time_series"


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()


# ============================================================
# DATA
# ============================================================

def get_data(interval, outputsize=250):

    params = {
        "symbol": SYMBOL,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY,
        "format": "JSON"
    }

    response = requests.get(BASE_URL, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()

    if "values" not in data:
        raise Exception(f"Twelve Data error: {data}")

    df = pd.DataFrame(data["values"])

    df["datetime"] = pd.to_datetime(df["datetime"])

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("datetime").reset_index(drop=True)

    return df


# ============================================================
# INDICATORS
# ============================================================

def add_indicators(df):

    df["ema20"] = df["close"].ewm(
        span=20,
        adjust=False
    ).mean()

    df["ema50"] = df["close"].ewm(
        span=50,
        adjust=False
    ).mean()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["rsi"] = 100 - (100 / (1 + rs))

    prev_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    df["atr"] = tr.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    return df


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(df):

    row = df.iloc[-2]

    price = row["close"]
    ema20 = row["ema20"]
    ema50 = row["ema50"]

    if price > ema20 > ema50:
        direction = "BULLISH"

    elif price < ema20 < ema50:
        direction = "BEARISH"

    else:
        direction = "NEUTRAL"

    return direction


# ============================================================
# SWINGS
# ============================================================

def find_swings(df, lookback=3):

    highs = []
    lows = []

    end = len(df) - 1

    for i in range(lookback, end - lookback):

        high = df["high"].iloc[i]
        low = df["low"].iloc[i]

        left_high = df["high"].iloc[
            i - lookback:i
        ].max()

        right_high = df["high"].iloc[
            i + 1:i + 1 + lookback
        ].max()

        left_low = df["low"].iloc[
            i - lookback:i
        ].min()

        right_low = df["low"].iloc[
            i + 1:i + 1 + lookback
        ].min()

        if high > left_high and high > right_high:
            highs.append((i, high))

        if low < left_low and low < right_low:
            lows.append((i, low))

    return highs, lows


# ============================================================
# MARKET STRUCTURE
# ============================================================

def detect_market_structure(df):

    highs, lows = find_swings(df)

    if len(highs) < 2 or len(lows) < 2:

        return {
            "structure": "MIXED",
            "high_label": "N/A",
            "low_label": "N/A",
            "last_high": None,
            "last_low": None
        }

    prev_high = highs[-2][1]
    last_high = highs[-1][1]

    prev_low = lows[-2][1]
    last_low = lows[-1][1]

    if last_high > prev_high:
        high_label = "HH"
    else:
        high_label = "LH"

    if last_low > prev_low:
        low_label = "HL"
    else:
        low_label = "LL"

    if high_label == "HH" and low_label == "HL":
        structure = "BULLISH"

    elif high_label == "LH" and low_label == "LL":
        structure = "BEARISH"

    else:
        structure = "MIXED"

    return {
        "structure": structure,
        "high_label": high_label,
        "low_label": low_label,
        "last_high": last_high,
        "last_low": last_low
    }


# ============================================================
# BOS / CHOCH
# ============================================================

def detect_bos_choch(df, structure):

    row = df.iloc[-2]

    close = row["close"]

    last_high = structure["last_high"]
    last_low = structure["last_low"]

    bos = "NONE"
    choch = "NONE"

    if last_high is not None and close > last_high:

        if structure["structure"] == "BULLISH":
            bos = "BULLISH BOS"
        else:
            choch = "BULLISH CHoCH"

    elif last_low is not None and close < last_low:

        if structure["structure"] == "BEARISH":
            bos = "BEARISH BOS"
        else:
            choch = "BEARISH CHoCH"

    return bos, choch


# ============================================================
# CANDLE CONFIRMATION
# ============================================================

def candle_confirmation(df):

    row = df.iloc[-2]
    prev = df.iloc[-3]

    o = row["open"]
    h = row["high"]
    l = row["low"]
    c = row["close"]

    po = prev["open"]
    pc = prev["close"]

    body = abs(c - o)
    candle_range = h - l

    if candle_range == 0:
        return "NONE"

    body_ratio = body / candle_range

    bullish_engulfing = (
        c > o
        and pc < po
        and c > po
        and o < pc
    )

    bearish_engulfing = (
        c < o
        and pc > po
        and c < po
        and o > pc
    )

    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    bullish_rejection = (
        lower_wick > body * 1.5
        and c > o
    )

    bearish_rejection = (
        upper_wick > body * 1.5
        and c < o
    )

    if bullish_engulfing:
        return "BULLISH ENGULFING"

    if bearish_engulfing:
        return "BEARISH ENGULFING"

    if bullish_rejection:
        return "BULLISH REJECTION"

    if bearish_rejection:
        return "BEARISH REJECTION"

    if body_ratio >= 0.65:

        if c > o:
            return "BULLISH MOMENTUM"

        if c < o:
            return "BEARISH MOMENTUM"

    return "NONE"


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def detect_liquidity_sweep(df):

    row = df.iloc[-2]

    previous = df.iloc[-7:-2]

    prior_high = previous["high"].max()
    prior_low = previous["low"].min()

    bullish_sweep = (
        row["low"] < prior_low
        and row["close"] > prior_low
    )

    bearish_sweep = (
        row["high"] > prior_high
        and row["close"] < prior_high
    )

    if bullish_sweep:
        return "BULLISH LIQUIDITY SWEEP"

    if bearish_sweep:
        return "BEARISH LIQUIDITY SWEEP"

    return "NONE"


# ============================================================
# BREAKOUT
# ============================================================

def detect_breakout(df):

    row = df.iloc[-2]
    previous = df.iloc[-7:-2]

    previous_high = previous["high"].max()
    previous_low = previous["low"].min()

    if row["close"] > previous_high:
        return "BULLISH BREAKOUT"

    if row["close"] < previous_low:
        return "BEARISH BREAKOUT"

    return "NONE"


# ============================================================
# PULLBACK
# ============================================================

def detect_pullback(df, structure, atr):

    row = df.iloc[-2]

    price = row["close"]
    ema20 = row["ema20"]

    distance = abs(price - ema20)

    if atr <= 0:
        return "NONE"

    if distance <= 0.60 * atr:

        if structure["structure"] == "BULLISH":
            return "BULLISH PULLBACK"

        if structure["structure"] == "BEARISH":
            return "BEARISH PULLBACK"

    return "NONE"


# ============================================================
# RETEST
# ============================================================

def detect_retest(df, structure):

    if len(df) < 8:
        return "NONE"

    recent = df.iloc[-7:-1]

    last_high = structure["last_high"]
    last_low = structure["last_low"]

    tolerance = recent["atr"].iloc[-1] * 0.35

    if last_high is not None:

        for i in range(len(recent) - 2):

            row1 = recent.iloc[i]
            row2 = recent.iloc[i + 1]

            bullish_break = row1["close"] > last_high

            retest = (
                abs(row2["low"] - last_high) <= tolerance
                and row2["close"] > last_high
            )

            if bullish_break and retest:
                return "BULLISH RETEST"

    if last_low is not None:

        for i in range(len(recent) - 2):

            row1 = recent.iloc[i]
            row2 = recent.iloc[i + 1]

            bearish_break = row1["close"] < last_low

            retest = (
                abs(row2["high"] - last_low) <= tolerance
                and row2["close"] < last_low
            )

            if bearish_break and retest:
                return "BEARISH RETEST"

    return "NONE"


# ============================================================
# EMA STATE
# ============================================================

def detect_ema_state(row):

    atr = row["atr"]

    if atr <= 0:
        return "UNKNOWN"

    spread = abs(row["ema20"] - row["ema50"])
    spread_atr = spread / atr

    if spread_atr <= 0.35:
        return "COMPRESSION"

    if spread_atr <= 0.60:
        return "TIGHT"

    return "EXPANDED"


def detect_ema_expansion(df):

    current = df.iloc[-2]
    previous = df.iloc[-3]

    current_spread = abs(
        current["ema20"] - current["ema50"]
    )

    previous_spread = abs(
        previous["ema20"] - previous["ema50"]
    )

    atr = current["atr"]

    if atr <= 0:
        return "FLAT"

    increase = (
        current_spread - previous_spread
    ) / atr

    current_atr_spread = current_spread / atr

    if increase > 0.03 and current_atr_spread > 0.35:
        return "EXPANDING"

    if increase > 0:
        return "EARLY EXPANSION"

    return "FLAT"


# ============================================================
# SMART LEVELS
# ============================================================

def smart_levels(df, atr):

    highs, lows = find_swings(df)

    price = df.iloc[-2]["close"]

    support_candidates = [
        value for _, value in lows
        if value < price
    ]

    resistance_candidates = [
        value for _, value in highs
        if value > price
    ]

    if support_candidates:
        support = max(support_candidates)
    else:
        support = price - 3 * atr

    if resistance_candidates:
        resistance = min(resistance_candidates)
    else:
        resistance = price + 3 * atr

    return support, resistance


# ============================================================
# S/R PROXIMITY
# ============================================================

def detect_sr_proximity(price, support, resistance, atr):

    if atr <= 0:
        return {
            "support_distance": 999,
            "resistance_distance": 999,
            "support_zone": False,
            "resistance_zone": False
        }

    support_distance = (
        abs(price - support) / atr
    )

    resistance_distance = (
        abs(resistance - price) / atr
    )

    return {
        "support_distance": support_distance,
        "resistance_distance": resistance_distance,
        "support_zone": support_distance <= 0.50,
        "resistance_zone": resistance_distance <= 0.50
    }


# ============================================================
# TIGHT RANGE
# ============================================================

def detect_tight_range(
    support,
    resistance,
    atr
):

    if atr <= 0:
        return "UNKNOWN", 999

    width = resistance - support
    width_atr = width / atr

    if width_atr <= 0.50:
        return "TIGHT RANGE", width_atr

    if width_atr <= 0.90:
        return "NORMAL RANGE", width_atr

    return "EXPANDED RANGE", width_atr


# ============================================================
# MARKET PHASE
# ============================================================

def detect_market_phase(
    structure,
    h4,
    h1,
    bos,
    choch,
    breakout,
    candle,
    tight_range
):

    if tight_range == "TIGHT RANGE":
        return "TIGHT RANGE"

    bullish_ltf = (
        choch == "BULLISH CHoCH"
        or breakout == "BULLISH BREAKOUT"
        or candle.startswith("BULLISH")
    )

    bearish_ltf = (
        choch == "BEARISH CHoCH"
        or breakout == "BEARISH BREAKOUT"
        or candle.startswith("BEARISH")
    )

    htf_bearish = (
        h4 == "BEARISH"
        and h1 == "BEARISH"
    )

    htf_bullish = (
        h4 == "BULLISH"
        and h1 == "BULLISH"
    )

    if htf_bearish and bullish_ltf:
        return "BEARISH HTF / BULLISH LTF TRANSITION"

    if htf_bullish and bearish_ltf:
        return "BULLISH HTF / BEARISH LTF TRANSITION"

    if structure == "BULLISH" and bos == "BULLISH BOS":
        return "BULLISH CONTINUATION"

    if structure == "BEARISH" and bos == "BEARISH BOS":
        return "BEARISH CONTINUATION"

    if structure == "BULLISH":
        return "BULLISH PULLBACK"

    if structure == "BEARISH":
        return "BEARISH PULLBACK"

    return "RANGE / MIXED"


# ============================================================
# SCORE
# ============================================================

def calculate_score(
    h4,
    h1,
    m30,
    m15,
    structure,
    bos,
    choch,
    candle,
    liquidity,
    breakout,
    pullback,
    retest,
    rsi
):

    buy = 0
    sell = 0

    # MTF
    for direction, weight in [
        (h4, 15),
        (h1, 20),
        (m30, 15),
        (m15, 10)
    ]:

        if direction == "BULLISH":
            buy += weight

        elif direction == "BEARISH":
            sell += weight

    # RSI
    if 50 <= rsi <= 70:
        buy += 10

    elif 30 <= rsi < 50:
        sell += 10

    # Structure
    if structure == "BULLISH":
        buy += 10

    elif structure == "BEARISH":
        sell += 10

    # BOS
    if bos == "BULLISH BOS":
        buy += 10

    elif bos == "BEARISH BOS":
        sell += 10

    # CHoCH
    if choch == "BULLISH CHoCH":
        buy += 8

    elif choch == "BEARISH CHoCH":
        sell += 8

    # Candle
    if candle.startswith("BULLISH"):
        buy += 5

    elif candle.startswith("BEARISH"):
        sell += 5

    # Liquidity
    if liquidity.startswith("BULLISH"):
        buy += 5

    elif liquidity.startswith("BEARISH"):
        sell += 5

    # Breakout
    if breakout == "BULLISH BREAKOUT":
        buy += 5

    elif breakout == "BEARISH BREAKOUT":
        sell += 5

    # Pullback
    if pullback == "BULLISH PULLBACK":
        buy += 3

    elif pullback == "BEARISH PULLBACK":
        sell += 3

    # Retest
    if retest == "BULLISH RETEST":
        buy += 7

    elif retest == "BEARISH RETEST":
        sell += 7

    return min(buy, 100), min(sell, 100)


# ============================================================
# ENTRY QUALITY
# ============================================================

def calculate_entry_quality(
    structure,
    phase,
    ema_state,
    ema_expansion,
    breakout,
    choch,
    bos,
    pullback,
    retest,
    sr,
    tight_range,
    candle,
    rsi
):

    quality = 100
    reasons = []

    # Tight range
    if tight_range == "TIGHT RANGE":
        quality -= 25
        reasons.append("Tight range")

    # Mixed structure
    if structure == "MIXED":
        quality -= 15
        reasons.append("Mixed structure")

    # EMA compression
    if ema_state == "COMPRESSION":
        quality -= 15
        reasons.append("EMA compression")

    elif ema_state == "TIGHT":
        quality -= 7
        reasons.append("EMA tight")

    # No expansion
    if ema_expansion == "FLAT":
        quality -= 5

    # Breakout
    if breakout != "NONE":
        quality += 5

    # BOS
    if bos != "NONE":
        quality += 8

    # CHoCH
    if choch != "NONE":
        quality += 4

    # Retest
    if retest != "NONE":
        quality += 8

    # Pullback
    if pullback != "NONE":
        quality += 3

    # Candle
    if candle != "NONE":
        quality += 3

    # S/R
    if sr["support_zone"]:
        quality -= 10
        reasons.append("Price near support")

    if sr["resistance_zone"]:
        quality -= 10
        reasons.append("Price near resistance")

    # RSI exhaustion
    if rsi >= 75:
        quality -= 15
        reasons.append("Extreme overbought")

    elif rsi <= 25:
        quality -= 15
        reasons.append("Extreme oversold")

    return max(0, min(100, quality)), reasons


# ============================================================
# CHOCH CONFLICT FILTER
# ============================================================

def conflict_filter(
    h4,
    h1,
    choch,
    bos
):

    htf_bearish = (
        h4 == "BEARISH"
        and h1 == "BEARISH"
    )

    htf_bullish = (
        h4 == "BULLISH"
        and h1 == "BULLISH"
    )

    sell_blocked = False
    buy_blocked = False

    if htf_bearish and choch == "BULLISH CHoCH":

        if bos != "BEARISH BOS":
            sell_blocked = True

    if htf_bullish and choch == "BEARISH CHoCH":

        if bos != "BULLISH BOS":
            buy_blocked = True

    return buy_blocked, sell_blocked


# ============================================================
# NEXT TRIGGER
# ============================================================

def build_dual_triggers(
    support,
    resistance,
    tight_range
):

    if tight_range == "TIGHT RANGE":

        return (
            "🔴 SELL TRIGGER\n"
            f"Break support {support:.2f}\n"
            "→ bearish BOS\n"
            "→ retest\n"
            "→ bearish candle confirmation\n\n"

            "🟢 BUY TRIGGER\n"
            f"Break resistance {resistance:.2f}\n"
            "→ bullish BOS\n"
            "→ retest\n"
            "→ bullish candle confirmation"
        )

    return (
        "🔴 SELL TRIGGER\n"
        f"Break support {support:.2f}\n"
        "→ bearish BOS / CHoCH\n"
        "→ retest\n"
        "→ bearish confirmation\n\n"

        "🟢 BUY TRIGGER\n"
        f"Break resistance {resistance:.2f}\n"
        "→ bullish BOS / CHoCH\n"
        "→ retest\n"
        "→ bullish confirmation"
    )


# ============================================================
# TRADE PLAN
# ============================================================

def trade_plan(
    direction,
    price,
    atr
):

    if direction == "BUY":

        sl = price - 1.5 * atr
        tp1 = price + 2.25 * atr
        tp2 = price + 3.75 * atr

    else:

        sl = price + 1.5 * atr
        tp1 = price - 2.25 * atr
        tp2 = price - 3.75 * atr

    return sl, tp1, tp2


# ============================================================
# MAIN ANALYSIS
# ============================================================

def analyze():

    timeframes = {
        "H4": "4h",
        "H1": "1h",
        "M30": "30min",
        "M15": "15min"
    }

    datasets = {}

    for name, interval in timeframes.items():

        df = get_data(interval)
        df = add_indicators(df)

        datasets[name] = df

    h4 = analyze_timeframe(datasets["H4"])
    h1 = analyze_timeframe(datasets["H1"])
    m30 = analyze_timeframe(datasets["M30"])
    m15 = analyze_timeframe(datasets["M15"])

    df = datasets["M30"]

    row = df.iloc[-2]

    price = row["close"]
    ema20 = row["ema20"]
    ema50 = row["ema50"]
    rsi = row["rsi"]
    atr = row["atr"]

    structure = detect_market_structure(df)

    bos, choch = detect_bos_choch(
        df,
        structure
    )

    candle = candle_confirmation(df)

    liquidity = detect_liquidity_sweep(df)

    breakout = detect_breakout(df)

    pullback = detect_pullback(
        df,
        structure,
        atr
    )

    retest = detect_retest(
        df,
        structure
    )

    ema_state = detect_ema_state(row)

    ema_expansion = detect_ema_expansion(df)

    support, resistance = smart_levels(
        df,
        atr
    )

    sr = detect_sr_proximity(
        price,
        support,
        resistance,
        atr
    )

    tight_range, range_width_atr = detect_tight_range(
        support,
        resistance,
        atr
    )

    phase = detect_market_phase(
        structure["structure"],
        h4,
        h1,
        bos,
        choch,
        breakout,
        candle,
        tight_range
    )

    buy_score, sell_score = calculate_score(
        h4,
        h1,
        m30,
        m15,
        structure["structure"],
        bos,
        choch,
        candle,
        liquidity,
        breakout,
        pullback,
        retest,
        rsi
    )

    quality, quality_reasons = calculate_entry_quality(
        structure["structure"],
        phase,
        ema_state,
        ema_expansion,
        breakout,
        choch,
        bos,
        pullback,
        retest,
        sr,
        tight_range,
        candle,
        rsi
    )

    buy_blocked, sell_blocked = conflict_filter(
        h4,
        h1,
        choch,
        bos
    )

    # ========================================================
    # FINAL DECISION
    # ========================================================

    decision = "WAIT"

    if tight_range == "TIGHT RANGE":

        decision = "WAIT"

    else:

        if buy_blocked:
            buy_score = min(buy_score, 40)

        if sell_blocked:
            sell_score = min(sell_score, 40)

        if (
            buy_score >= 70
            and buy_score > sell_score
            and not sr["resistance_zone"]
        ):
            decision = "BUY"

        elif (
            sell_score >= 70
            and sell_score > buy_score
            and not sr["support_zone"]
        ):
            decision = "SELL"

        else:
            decision = "WAIT"

    # ========================================================
    # CONFIDENCE
    # ========================================================

    confidence = max(
        buy_score,
        sell_score
    )

    if decision == "WAIT":

        confidence = int(
            confidence * 0.60
        )

    confidence = max(
        0,
        min(100, confidence)
    )

    # ========================================================
    # REASONS
    # ========================================================

    reasons = []

    if structure["structure"] == "MIXED":
        reasons.append("Market structure mixed")

    if ema_state == "COMPRESSION":
        reasons.append("EMA20/EMA50 compression")

    if tight_range == "TIGHT RANGE":
        reasons.append(
            f"Tight range {range_width_atr:.2f} ATR"
        )

    if candle != "NONE":
        reasons.append(candle)

    if pullback != "NONE":
        reasons.append(pullback)

    if retest != "NONE":
        reasons.append(retest)

    if choch != "NONE":
        reasons.append(choch)

    if breakout != "NONE":
        reasons.append(breakout)

    if phase == "BEARISH HTF / BULLISH LTF TRANSITION":
        reasons.append(
            "HTF bearish vs LTF bullish transition"
        )

    elif phase == "BULLISH HTF / BEARISH LTF TRANSITION":
        reasons.append(
            "HTF bullish vs LTF bearish transition"
        )

    for reason in quality_reasons:
        if reason not in reasons:
            reasons.append(reason)

    # ========================================================
    # TRIGGERS
    # ========================================================

    if tight_range == "TIGHT RANGE":

        next_trigger = build_dual_triggers(
            support,
            resistance,
            tight_range
        )

    elif decision == "BUY":

        next_trigger = (
            f"BUY confirmed → monitor retest "
            f"above {resistance:.2f}"
        )

    elif decision == "SELL":

        next_trigger = (
            f"SELL confirmed → monitor retest "
            f"below {support:.2f}"
        )

    else:

        next_trigger = build_dual_triggers(
            support,
            resistance,
            tight_range
        )

    # ========================================================
    # TRADE PLAN
    # ========================================================

    plan = ""

    if decision in ["BUY", "SELL"]:

        sl, tp1, tp2 = trade_plan(
            decision,
            price,
            atr
        )

        plan = (
            f"\n\n💰 TRADE PLAN\n"
            f"Entry : {price:.2f}\n"
            f"SL    : {sl:.2f}\n"
            f"TP1   : {tp1:.2f}\n"
            f"TP2   : {tp2:.2f}\n"
            f"RR    : 1:1.5 / 1:2.5"
        )

    # ========================================================
    # OUTPUT
    # ========================================================

    message = (
        "🤖 XAUUSD AI-STYLE V1.6.5\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"{'🟢' if decision == 'BUY' else '🔴' if decision == 'SELL' else '⚪'} "
        f"{decision}\n"
        f"📊 Confidence : {confidence}/100\n"
        f"🎯 Entry Quality : {quality}/100\n\n"

        "📈 MULTI-TIMEFRAME\n"
        f"H4  : {h4}\n"
        f"H1  : {h1}\n"
        f"M30 : {m30}\n"
        f"M15 : {m15}\n\n"

        "🏗 MARKET STRUCTURE\n"
        f"Structure : {structure['structure']}\n"
        f"High : {structure['high_label']}\n"
        f"Low  : {structure['low_label']}\n\n"

        "🧭 MARKET PHASE\n"
        f"{phase}\n\n"

        "📊 STRUCTURE EVENT\n"
        f"BOS   : {bos}\n"
        f"CHoCH : {choch}\n"
        f"Liquidity : {liquidity}\n"
        f"Breakout  : {breakout}\n"
        f"Candle    : {candle}\n"
        f"Pullback  : {pullback}\n"
        f"Retest    : {retest}\n\n"

        "📐 EMA ENGINE\n"
        f"EMA20 : {ema20:.2f}\n"
        f"EMA50 : {ema50:.2f}\n"
        f"EMA Spread : {abs(ema20 - ema50) / atr:.2f} ATR\n"
        f"Price → EMA20 : {abs(price - ema20) / atr:.2f} ATR\n"
        f"EMA State : {ema_state}\n"
        f"EMA Expansion : {ema_expansion}\n\n"

        "📦 MARKET RANGE\n"
        f"Range State : {tight_range}\n"
        f"Range Width : {range_width_atr:.2f} ATR\n\n"

        f"💰 Price : {price:.2f}\n"
        f"RSI : {rsi:.2f}\n"
        f"ATR : {atr:.2f}\n\n"

        f"🟢 Support : {support:.2f}\n"
        f"🔴 Resistance : {resistance:.2f}\n"
        f"Support Distance : {sr['support_distance']:.2f} ATR\n"
        f"Resistance Distance : {sr['resistance_distance']:.2f} ATR\n\n"
    )

    # ========================================================
    # BLOCK STATUS
    # ========================================================

    if tight_range == "TIGHT RANGE":

        message += (
            "⚠️ TIGHT RANGE — BOTH SIDES BLOCKED\n"
            "Market terlalu sempit untuk entry langsung.\n\n"
        )

    else:

        if sell_blocked:
            message += (
                "⚠️ SELL BLOCKED\n"
                "Bullish CHoCH melawan HTF bearish.\n\n"
            )

        if buy_blocked:
            message += (
                "⚠️ BUY BLOCKED\n"
                "Bearish CHoCH melawan HTF bullish.\n\n"
            )

        if sr["support_zone"]:
            message += (
                "⚠️ SELL ZONE BLOCKED\n"
                "Price too close to support.\n\n"
            )

        if sr["resistance_zone"]:
            message += (
                "⚠️ BUY ZONE BLOCKED\n"
                "Price too close to resistance.\n\n"
            )

    # ========================================================
    # REASONS
    # ========================================================

    if reasons:

        message += "🧠 REASONS\n"

        unique_reasons = []

        for reason in reasons:

            if reason not in unique_reasons:
                unique_reasons.append(reason)

        for reason in unique_reasons[:8]:
            message += f"• {reason}\n"

        message += "\n"

    message += (
        "🎯 NEXT TRIGGER\n"
        f"{next_trigger}"
        f"{plan}\n\n"

        "📊 SCORE\n"
        f"BUY  {buy_score} / SELL {sell_score}"
    )

    return message


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        message = analyze()

        send_telegram(message)

        print(message)

    except Exception as e:

        error_message = (
            "❌ XAUUSD BOT ERROR\n\n"
            f"{type(e).__name__}: {e}"
        )

        print(error_message)

        send_telegram(error_message)