import os
import requests
import pandas as pd
import numpy as np

# =========================================================
# XAUUSD AI-STYLE V1.6.4
# S/R PROXIMITY + EMA EXPANSION + PULLBACK + RETEST
# =========================================================

SYMBOL = "XAU/USD"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")


# =========================================================
# TELEGRAM
# =========================================================

def send_telegram(message):

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=20
        )

        print("Telegram:", response.status_code)

    except Exception as e:
        print("Telegram error:", e)


# =========================================================
# DATA
# =========================================================

def get_data(interval, outputsize=250):

    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": SYMBOL,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY,
        "format": "JSON"
    }

    response = requests.get(
        url,
        params=params,
        timeout=20
    )

    data = response.json()

    if "values" not in data:
        raise Exception(
            f"Twelve Data error: {data}"
        )

    df = pd.DataFrame(data["values"])

    df["datetime"] = pd.to_datetime(
        df["datetime"]
    )

    for column in [
        "open",
        "high",
        "low",
        "close"
    ]:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.sort_values(
        "datetime"
    ).reset_index(drop=True)

    return df


# =========================================================
# INDICATORS
# =========================================================

def add_indicators(df):

    df = df.copy()

    # EMA
    df["EMA20"] = df["close"].ewm(
        span=20,
        adjust=False
    ).mean()

    df["EMA50"] = df["close"].ewm(
        span=50,
        adjust=False
    ).mean()

    # RSI
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

    rs = avg_gain / avg_loss.replace(
        0,
        np.nan
    )

    df["RSI"] = 100 - (
        100 / (1 + rs)
    )

    # ATR
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

    df["ATR"] = true_range.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    return df


# =========================================================
# TIMEFRAME
# =========================================================

def analyze_timeframe(df):

    latest = df.iloc[-2]

    price = latest["close"]
    ema20 = latest["EMA20"]
    ema50 = latest["EMA50"]

    if price > ema20 > ema50:
        return "BULLISH"

    if price < ema20 < ema50:
        return "BEARISH"

    return "NEUTRAL"


# =========================================================
# SWINGS
# =========================================================

def find_swings(df, lookback=3):

    highs = []
    lows = []

    data = df.iloc[:-1]

    for i in range(
        lookback,
        len(data) - lookback
    ):

        high = data.iloc[i]["high"]
        low = data.iloc[i]["low"]

        left_highs = data.iloc[
            i - lookback:i
        ]["high"]

        right_highs = data.iloc[
            i + 1:i + lookback + 1
        ]["high"]

        left_lows = data.iloc[
            i - lookback:i
        ]["low"]

        right_lows = data.iloc[
            i + 1:i + lookback + 1
        ]["low"]

        if (
            high > left_highs.max()
            and high > right_highs.max()
        ):

            highs.append(
                (i, high)
            )

        if (
            low < left_lows.min()
            and low < right_lows.min()
        ):

            lows.append(
                (i, low)
            )

    return highs, lows


# =========================================================
# MARKET STRUCTURE
# =========================================================

def detect_market_structure(df):

    highs, lows = find_swings(df)

    if len(highs) < 2 or len(lows) < 2:

        return {
            "structure": "NEUTRAL",
            "high_type": "NONE",
            "low_type": "NONE",
            "last_high": None,
            "last_low": None
        }

    previous_high = highs[-2][1]
    latest_high = highs[-1][1]

    previous_low = lows[-2][1]
    latest_low = lows[-1][1]

    high_type = (
        "HH"
        if latest_high > previous_high
        else "LH"
    )

    low_type = (
        "HL"
        if latest_low > previous_low
        else "LL"
    )

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

    else:

        structure = "MIXED"

    return {
        "structure": structure,
        "high_type": high_type,
        "low_type": low_type,
        "last_high": latest_high,
        "last_low": latest_low
    }


# =========================================================
# BOS / CHOCH
# =========================================================

def detect_bos_choch(
    df,
    structure_data
):

    latest = df.iloc[-2]

    close = latest["close"]

    last_high = structure_data["last_high"]
    last_low = structure_data["last_low"]

    structure = structure_data["structure"]

    bos = "NONE"
    choch = "NONE"

    if (
        last_high is not None
        and close > last_high
    ):

        if structure == "BULLISH":
            bos = "BULLISH BOS"
        else:
            choch = "BULLISH CHoCH"

    elif (
        last_low is not None
        and close < last_low
    ):

        if structure == "BEARISH":
            bos = "BEARISH BOS"
        else:
            choch = "BEARISH CHoCH"

    return bos, choch


# =========================================================
# CANDLE
# =========================================================

def candle_confirmation(df):

    current = df.iloc[-2]
    previous = df.iloc[-3]

    o = current["open"]
    h = current["high"]
    l = current["low"]
    c = current["close"]

    po = previous["open"]
    pc = previous["close"]

    body = abs(c - o)
    candle_range = h - l

    if candle_range == 0:
        return "NONE"

    body_ratio = body / candle_range

    # Bullish engulfing
    if (
        c > o
        and pc < po
        and c > po
        and o < pc
    ):

        return "BULLISH ENGULFING"

    # Bearish engulfing
    if (
        c < o
        and pc > po
        and c < po
        and o > pc
    ):

        return "BEARISH ENGULFING"

    # Momentum
    if body_ratio >= 0.65:

        if c > o:
            return "BULLISH MOMENTUM"

        if c < o:
            return "BEARISH MOMENTUM"

    # Rejection
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    if lower_wick > body * 2:
        return "BULLISH REJECTION"

    if upper_wick > body * 2:
        return "BEARISH REJECTION"

    return "NONE"


# =========================================================
# LIQUIDITY
# =========================================================

def detect_liquidity_sweep(df):

    current = df.iloc[-2]

    previous = df.iloc[-7:-2]

    previous_high = previous["high"].max()
    previous_low = previous["low"].min()

    if (
        current["high"] > previous_high
        and current["close"] < previous_high
    ):

        return "BUY-SIDE LIQUIDITY SWEEP"

    if (
        current["low"] < previous_low
        and current["close"] > previous_low
    ):

        return "SELL-SIDE LIQUIDITY SWEEP"

    return "NONE"


# =========================================================
# BREAKOUT
# =========================================================

def detect_breakout(df):

    current = df.iloc[-2]

    previous = df.iloc[-7:-2]

    previous_high = previous["high"].max()
    previous_low = previous["low"].min()

    if current["close"] > previous_high:
        return "BULLISH BREAKOUT"

    if current["close"] < previous_low:
        return "BEARISH BREAKOUT"

    return "NONE"


# =========================================================
# EMA ANALYSIS
# =========================================================

def detect_ema_state(df):

    current = df.iloc[-2]

    price = current["close"]
    ema20 = current["EMA20"]
    ema50 = current["EMA50"]
    atr = current["ATR"]

    if atr <= 0:
        return {
            "spread_atr": 0,
            "price_ema20_atr": 0,
            "state": "UNKNOWN"
        }

    # EMA20 ↔ EMA50
    spread_atr = (
        abs(ema20 - ema50) / atr
    )

    # Price ↔ EMA20
    price_ema20_atr = (
        abs(price - ema20) / atr
    )

    if spread_atr <= 0.35:
        state = "COMPRESSION"

    elif spread_atr <= 0.60:
        state = "TIGHT"

    else:
        state = "EXPANDED"

    return {
        "spread_atr": spread_atr,
        "price_ema20_atr": price_ema20_atr,
        "state": state
    }


# =========================================================
# EMA EXPANSION
# =========================================================

def detect_ema_expansion(df):

    current = df.iloc[-2]
    previous = df.iloc[-3]

    atr = current["ATR"]

    if atr <= 0:
        return "NONE"

    current_spread = abs(
        current["EMA20"]
        - current["EMA50"]
    ) / atr

    previous_spread = abs(
        previous["EMA20"]
        - previous["EMA50"]
    ) / atr

    increase = (
        current_spread
        - previous_spread
    )

    if (
        current_spread > 0.35
        and increase > 0.03
    ):

        return "EXPANDING"

    if (
        current_spread <= 0.35
        and increase > 0
    ):

        return "EARLY EXPANSION"

    return "FLAT"


# =========================================================
# PULLBACK
# =========================================================

def detect_pullback(
    df,
    h1_direction
):

    current = df.iloc[-2]

    price = current["close"]
    ema20 = current["EMA20"]
    ema50 = current["EMA50"]
    atr = current["ATR"]

    if atr <= 0:
        return "NONE"

    # Bearish trend:
    # price retraces upward toward EMA
    if h1_direction == "BEARISH":

        if (
            price >= ema20
            and price - ema20 <= 0.75 * atr
        ):

            return "BEARISH PULLBACK"

        if (
            price >= ema50
            and price - ema50 <= 0.75 * atr
        ):

            return "BEARISH PULLBACK"

    # Bullish trend:
    # price retraces downward toward EMA
    if h1_direction == "BULLISH":

        if (
            price <= ema20
            and ema20 - price <= 0.75 * atr
        ):

            return "BULLISH PULLBACK"

        if (
            price <= ema50
            and ema50 - price <= 0.75 * atr
        ):

            return "BULLISH PULLBACK"

    return "NONE"


# =========================================================
# RETEST
# =========================================================

def detect_retest(
    df,
    structure_data,
    bos,
    choch
):

    current = df.iloc[-2]

    close = current["close"]
    atr = current["ATR"]

    if atr <= 0:
        return "NONE"

    level = None
    direction = None

    if (
        "BULLISH" in bos
        or "BULLISH" in choch
    ):

        level = structure_data["last_high"]
        direction = "BULLISH"

    elif (
        "BEARISH" in bos
        or "BEARISH" in choch
    ):

        level = structure_data["last_low"]
        direction = "BEARISH"

    if level is None:
        return "NONE"

    distance = abs(
        close - level
    )

    if distance <= 0.35 * atr:

        if (
            direction == "BULLISH"
            and close >= level
        ):

            return "BULLISH RETEST"

        if (
            direction == "BEARISH"
            and close <= level
        ):

            return "BEARISH RETEST"

    return "NONE"


# =========================================================
# SMART SUPPORT / RESISTANCE
# =========================================================

def smart_levels(df):

    current = df.iloc[-2]

    price = current["close"]
    atr = current["ATR"]

    highs, lows = find_swings(df)

    supports = [
        x[1]
        for x in lows
        if x[1] < price
    ]

    resistances = [
        x[1]
        for x in highs
        if x[1] > price
    ]

    if supports:
        support = max(supports)
    else:
        support = price - 3 * atr

    if resistances:
        resistance = min(resistances)
    else:
        resistance = price + 3 * atr

    return support, resistance


# =========================================================
# S/R PROXIMITY FILTER
# =========================================================

def detect_sr_proximity(
    price,
    support,
    resistance,
    atr
):

    if atr <= 0:
        return {
            "support_distance_atr": 999,
            "resistance_distance_atr": 999,
            "support_zone": False,
            "resistance_zone": False
        }

    support_distance = (
        abs(price - support) / atr
    )

    resistance_distance = (
        abs(resistance - price) / atr
    )

    # 0.50 ATR dianggap terlalu dekat
    support_zone = (
        support_distance <= 0.50
    )

    resistance_zone = (
        resistance_distance <= 0.50
    )

    return {
        "support_distance_atr": support_distance,
        "resistance_distance_atr": resistance_distance,
        "support_zone": support_zone,
        "resistance_zone": resistance_zone
    }


# =========================================================
# EXHAUSTION
# =========================================================

def detect_exhaustion(df):

    rsi = df.iloc[-2]["RSI"]

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
# COUNTER TREND
# =========================================================

def analyze_counter_trend(
    direction,
    candle,
    sweep
):

    warnings = []

    if direction == "SELL":

        if "BULLISH" in candle:
            warnings.append(
                "Bullish counter-momentum"
            )

        if "SELL-SIDE" in sweep:
            warnings.append(
                "Bullish liquidity sweep"
            )

    if direction == "BUY":

        if "BEARISH" in candle:
            warnings.append(
                "Bearish counter-momentum"
            )

        if "BUY-SIDE" in sweep:
            warnings.append(
                "Bearish liquidity sweep"
            )

    return warnings


# =========================================================
# CONTINUATION
# =========================================================

def detect_continuation(
    h4,
    h1,
    m30,
    structure,
    bos,
    choch,
    candle,
    pullback,
    retest
):

    bullish = 0
    bearish = 0

    if h4 == "BULLISH":
        bullish += 2

    if h1 == "BULLISH":
        bullish += 2

    if m30 == "BULLISH":
        bullish += 1

    if structure == "BULLISH":
        bullish += 2

    if "BULLISH" in bos:
        bullish += 3

    if "BULLISH" in choch:
        bullish += 2

    if "BULLISH" in candle:
        bullish += 1

    if pullback == "BULLISH PULLBACK":
        bullish += 1

    if retest == "BULLISH RETEST":
        bullish += 3

    if h4 == "BEARISH":
        bearish += 2

    if h1 == "BEARISH":
        bearish += 2

    if m30 == "BEARISH":
        bearish += 1

    if structure == "BEARISH":
        bearish += 2

    if "BEARISH" in bos:
        bearish += 3

    if "BEARISH" in choch:
        bearish += 2

    if "BEARISH" in candle:
        bearish += 1

    if pullback == "BEARISH PULLBACK":
        bearish += 1

    if retest == "BEARISH RETEST":
        bearish += 3

    if (
        bullish >= 7
        and bullish > bearish
    ):

        return "BULLISH CONTINUATION"

    if (
        bearish >= 7
        and bearish > bullish
    ):

        return "BEARISH CONTINUATION"

    if pullback != "NONE":
        return pullback

    if structure == "MIXED":
        return "RANGE / MIXED"

    return "NEUTRAL"


# =========================================================
# ENTRY QUALITY
# =========================================================

def calculate_entry_quality(
    direction,
    exhaustion,
    warnings,
    ema_state,
    ema_expansion,
    continuation,
    retest,
    sr_filter,
    breakout
):

    quality = 100

    # Exhaustion
    if (
        direction == "BUY"
        and exhaustion == "EXTREME OVERBOUGHT"
    ):

        quality -= 30

    if (
        direction == "SELL"
        and exhaustion == "EXTREME OVERSOLD"
    ):

        quality -= 30

    if exhaustion in [
        "OVERBOUGHT",
        "OVERSOLD"
    ]:

        quality -= 15

    # Counter momentum
    quality -= (
        len(warnings) * 12
    )

    # EMA compression
    if ema_state == "COMPRESSION":
        quality -= 20

    elif ema_state == "TIGHT":
        quality -= 10

    # Expansion
    if ema_expansion == "EXPANDING":
        quality += 8

    elif ema_expansion == "EARLY EXPANSION":
        quality += 4

    # Continuation
    if (
        direction == "BUY"
        and continuation
        == "BULLISH CONTINUATION"
    ):

        quality += 10

    if (
        direction == "SELL"
        and continuation
        == "BEARISH CONTINUATION"
    ):

        quality += 10

    # Retest
    if (
        direction == "BUY"
        and retest == "BULLISH RETEST"
    ):

        quality += 10

    if (
        direction == "SELL"
        and retest == "BEARISH RETEST"
    ):

        quality += 10

    # S/R proximity
    if direction == "SELL":
        if sr_filter["support_zone"]:
            quality -= 25

    if direction == "BUY":
        if sr_filter["resistance_zone"]:
            quality -= 25

    # Breakout
    if direction == "BUY":
        if "BULLISH" in breakout:
            quality += 5

    if direction == "SELL":
        if "BEARISH" in breakout:
            quality += 5

    return max(
        0,
        min(100, quality)
    )


# =========================================================
# SCORE
# =========================================================

def calculate_score(
    h4,
    h1,
    m30,
    m15,
    structure,
    bos,
    choch,
    candle,
    sweep,
    breakout,
    compression,
    rsi
):

    buy = 0
    sell = 0

    # H4
    if h4 == "BULLISH":
        buy += 15

    elif h4 == "BEARISH":
        sell += 15

    # H1
    if h1 == "BULLISH":
        buy += 20

    elif h1 == "BEARISH":
        sell += 20

    # M30
    if m30 == "BULLISH":
        buy += 15

    elif m30 == "BEARISH":
        sell += 15

    # M15
    if m15 == "BULLISH":
        buy += 10

    elif m15 == "BEARISH":
        sell += 10

    # RSI
    if 50 <= rsi < 70:
        buy += 10

    elif 30 < rsi < 50:
        sell += 10

    # Structure
    if structure == "BULLISH":
        buy += 10

    elif structure == "BEARISH":
        sell += 10

    # BOS
    if "BULLISH" in bos:
        buy += 10

    elif "BEARISH" in bos:
        sell += 10

    # CHOCH
    if "BULLISH" in choch:
        buy += 8

    elif "BEARISH" in choch:
        sell += 8

    # Candle
    if "BULLISH" in candle:
        buy += 5

    elif "BEARISH" in candle:
        sell += 5

    # Liquidity
    if "SELL-SIDE" in sweep:
        buy += 5

    elif "BUY-SIDE" in sweep:
        sell += 5

    # Breakout
    if "BULLISH" in breakout:
        buy += 5

    elif "BEARISH" in breakout:
        sell += 5

    # Compression penalty
    if compression == "COMPRESSION":

        buy -= 10
        sell -= 10

    return (
        max(0, min(100, buy)),
        max(0, min(100, sell))
    )


# =========================================================
# DECISION
# =========================================================

def make_decision(
    buy_score,
    sell_score,
    structure,
    choch,
    exhaustion,
    entry_quality,
    continuation,
    compression,
    sr_filter
):

    if buy_score > sell_score:

        direction = "BUY"
        score = buy_score

    elif sell_score > buy_score:

        direction = "SELL"
        score = sell_score

    else:

        return "WAIT", max(
            buy_score,
            sell_score
        )

    # Mixed structure
    if structure == "MIXED":
        return "WAIT", score

    # S/R proximity
    if (
        direction == "SELL"
        and sr_filter["support_zone"]
    ):

        return "WAIT", score

    if (
        direction == "BUY"
        and sr_filter["resistance_zone"]
    ):

        return "WAIT", score

    # Compression
    if (
        compression == "COMPRESSION"
        and entry_quality < 70
    ):

        return "WAIT", score

    # Structure protection
    if direction == "BUY":

        if (
            structure == "BEARISH"
            and "BULLISH CHoCH" not in choch
        ):

            return "WAIT", score

    if direction == "SELL":

        if (
            structure == "BULLISH"
            and "BEARISH CHoCH" not in choch
        ):

            return "WAIT", score

    # Exhaustion
    if (
        direction == "BUY"
        and exhaustion
        == "EXTREME OVERBOUGHT"
    ):

        return "WAIT", score

    if (
        direction == "SELL"
        and exhaustion
        == "EXTREME OVERSOLD"
    ):

        return "WAIT", score

    # Quality
    if entry_quality < 60:
        return "WAIT", score

    # Pullback without confirmation
    if (
        direction == "BUY"
        and continuation
        == "BULLISH PULLBACK"
        and score < 80
    ):

        return "WAIT", score

    if (
        direction == "SELL"
        and continuation
        == "BEARISH PULLBACK"
        and score < 80
    ):

        return "WAIT", score

    if score < 70:
        return "WAIT", score

    if score >= 85:
        return f"STRONG {direction}", score

    return direction, score


# =========================================================
# NEXT TRIGGER
# =========================================================

def next_trigger(
    decision,
    structure,
    bos,
    choch,
    continuation,
    compression,
    sr_filter
):

    if decision == "WAIT":

        if (
            sr_filter["support_zone"]
        ):

            return (
                "SELL blocked near support → "
                "wait support break + bearish BOS "
                "+ retest"
            )

        if (
            sr_filter["resistance_zone"]
        ):

            return (
                "BUY blocked near resistance → "
                "wait resistance break + bullish BOS "
                "+ retest"
            )

        if compression == "COMPRESSION":

            return (
                "Wait EMA expansion + BOS/CHoCH "
                "+ retest confirmation"
            )

        if structure == "MIXED":

            return (
                "Wait clear BOS/CHoCH "
                "and structure alignment"
            )

        if (
            continuation
            == "BEARISH PULLBACK"
        ):

            return (
                "Wait bearish rejection + "
                "break local low + retest"
            )

        if (
            continuation
            == "BULLISH PULLBACK"
        ):

            return (
                "Wait bullish rejection + "
                "break local high + retest"
            )

        return "Wait for clear BOS / CHoCH"

    if "BULLISH" in bos or "BULLISH" in choch:

        return (
            "Bullish continuation → "
            "retest → hold"
        )

    if "BEARISH" in bos or "BEARISH" in choch:

        return (
            "Bearish continuation → "
            "retest → hold"
        )

    if "BUY" in decision:

        return (
            "Break HH + bullish retest confirmation"
        )

    if "SELL" in decision:

        return (
            "Break LL + bearish retest confirmation"
        )

    return "Wait for confirmation"


# =========================================================
# TRADE PLAN
# =========================================================

def trade_plan(
    direction,
    price,
    atr
):

    if direction == "BUY":

        sl = price - (
            1.5 * atr
        )

        tp1 = price + (
            2.25 * atr
        )

        tp2 = price + (
            3.75 * atr
        )

    elif direction == "SELL":

        sl = price + (
            1.5 * atr
        )

        tp1 = price - (
            2.25 * atr
        )

        tp2 = price - (
            3.75 * atr
        )

    else:

        return None

    return sl, tp1, tp2


# =========================================================
# MAIN
# =========================================================

def run_analysis():

    h4_data = add_indicators(
        get_data("4h")
    )

    h1_data = add_indicators(
        get_data("1h")
    )

    m30_data = add_indicators(
        get_data("30min")
    )

    m15_data = add_indicators(
        get_data("15min")
    )

    # Timeframes
    h4 = analyze_timeframe(
        h4_data
    )

    h1 = analyze_timeframe(
        h1_data
    )

    m30 = analyze_timeframe(
        m30_data
    )

    m15 = analyze_timeframe(
        m15_data
    )

    # Structure
    structure_data = (
        detect_market_structure(
            m30_data
        )
    )

    structure = structure_data[
        "structure"
    ]

    # BOS / CHOCH
    bos, choch = detect_bos_choch(
        m30_data,
        structure_data
    )

    # Price action
    candle = candle_confirmation(
        m30_data
    )

    sweep = detect_liquidity_sweep(
        m30_data
    )

    breakout = detect_breakout(
        m30_data
    )

    # EMA
    ema = detect_ema_state(
        m30_data
    )

    ema_state = ema["state"]

    ema_expansion = detect_ema_expansion(
        m30_data
    )

    # Pullback
    pullback = detect_pullback(
        m30_data,
        h1
    )

    # Retest
    retest = detect_retest(
        m30_data,
        structure_data,
        bos,
        choch
    )

    # Continuation
    continuation = detect_continuation(
        h4,
        h1,
        m30,
        structure,
        bos,
        choch,
        candle,
        pullback,
        retest
    )

    # Current candle
    latest = m30_data.iloc[-2]

    price = latest["close"]
    ema20 = latest["EMA20"]
    ema50 = latest["EMA50"]
    rsi = latest["RSI"]
    atr = latest["ATR"]

    # S/R
    support, resistance = smart_levels(
        m30_data
    )

    sr_filter = detect_sr_proximity(
        price,
        support,
        resistance,
        atr
    )

    # Exhaustion
    exhaustion = detect_exhaustion(
        m30_data
    )

    # Score
    buy_score, sell_score = calculate_score(
        h4,
        h1,
        m30,
        m15,
        structure,
        bos,
        choch,
        candle,
        sweep,
        breakout,
        ema_state,
        rsi
    )

    # Direction for quality
    if buy_score > sell_score:
        quality_direction = "BUY"

    elif sell_score > buy_score:
        quality_direction = "SELL"

    else:
        quality_direction = "WAIT"

    # Warnings
    warnings = analyze_counter_trend(
        quality_direction,
        candle,
        sweep
    )

    # Entry quality
    entry_quality = (
        calculate_entry_quality(
            quality_direction,
            exhaustion,
            warnings,
            ema_state,
            ema_expansion,
            continuation,
            retest,
            sr_filter,
            breakout
        )
    )

    # Decision
    decision, confidence = make_decision(
        buy_score,
        sell_score,
        structure,
        choch,
        exhaustion,
        entry_quality,
        continuation,
        ema_state,
        sr_filter
    )

    # EMA distances
    price_ema20_atr = (
        abs(price - ema20) / atr
        if atr > 0
        else 0
    )

    # Reasons
    reasons = []

    if structure == "MIXED":
        reasons.append(
            "Market structure mixed"
        )

    if ema_state == "COMPRESSION":
        reasons.append(
            "EMA20/EMA50 compression"
        )

    if ema_expansion in [
        "EXPANDING",
        "EARLY EXPANSION"
    ]:

        reasons.append(
            f"EMA {ema_expansion.lower()}"
        )

    if bos == "NONE" and choch == "NONE":
        reasons.append(
            "No BOS / CHoCH trigger"
        )

    if breakout == "NONE":
        reasons.append(
            "No breakout confirmation"
        )

    if "BULLISH" in candle:
        reasons.append(
            "Bullish momentum"
        )

    if "BEARISH" in candle:
        reasons.append(
            "Bearish momentum"
        )

    if pullback != "NONE":
        reasons.append(
            pullback
        )

    if retest != "NONE":
        reasons.append(
            retest
        )

    if (
        sr_filter["support_zone"]
    ):

        reasons.append(
            "Price too close to support"
        )

    if (
        sr_filter["resistance_zone"]
    ):

        reasons.append(
            "Price too close to resistance"
        )

    if continuation != "NEUTRAL":
        reasons.append(
            continuation
        )

    reasons.extend(
        warnings
    )

    # Trade plan
    clean_direction = decision.replace(
        "STRONG ",
        ""
    )

    if clean_direction in [
        "BUY",
        "SELL"
    ]:

        plan = trade_plan(
            clean_direction,
            price,
            atr
        )

    else:

        plan = None

    # =====================================================
    # MESSAGE
    # =====================================================

    icon = (
        "🟢"
        if "BUY" in decision
        else "🔴"
        if "SELL" in decision
        else "⚪"
    )

    message = f"""
🤖 XAUUSD AI-STYLE V1.6.4
━━━━━━━━━━━━━━━━━━

{icon} {decision}

📊 Confidence : {confidence}/100
🎯 Entry Quality : {entry_quality}/100

📈 MULTI-TIMEFRAME
H4  : {h4}
H1  : {h1}
M30 : {m30}
M15 : {m15}

🏗 MARKET STRUCTURE
Structure : {structure}
High : {structure_data["high_type"]}
Low : {structure_data["low_type"]}

🔄 MARKET PHASE
Phase : {continuation}

📌 PRICE ACTION
BOS       : {bos}
CHoCH     : {choch}
Liquidity : {sweep}
Breakout  : {breakout}
Candle    : {candle}

🔄 PULLBACK
{pullback}

🎯 RETEST
{retest}

📏 EMA FILTER
EMA20 : {ema20:.2f}
EMA50 : {ema50:.2f}

EMA Spread :
{ema["spread_atr"]:.2f} ATR

Price → EMA20 :
{price_ema20_atr:.2f} ATR

EMA State :
{ema_state}

EMA Expansion :
{ema_expansion}

📊 INDICATORS
Price : {price:.2f}
RSI   : {rsi:.2f}
ATR   : {atr:.2f}

🧱 SMART LEVELS
Support    : {support:.2f}
Resistance : {resistance:.2f}

📐 S/R DISTANCE
Support Distance :
{sr_filter["support_distance_atr"]:.2f} ATR

Resistance Distance :
{sr_filter["resistance_distance_atr"]:.2f} ATR

"""

    if (
        sr_filter["support_zone"]
    ):

        message += (
            "⚠️ SELL ZONE BLOCKED\n"
            "Price too close to support\n\n"
        )

    if (
        sr_filter["resistance_zone"]
    ):

        message += (
            "⚠️ BUY ZONE BLOCKED\n"
            "Price too close to resistance\n\n"
        )

    message += f"""
🛡 SMART FILTER
Exhaustion : {exhaustion}

🧠 REASONS
"""

    if reasons:

        for reason in reasons:

            message += (
                f"• {reason}\n"
            )

    else:

        message += (
            "• No major confirmation\n"
        )

    message += f"""

🎯 NEXT TRIGGER
{next_trigger(
    decision,
    structure,
    bos,
    choch,
    continuation,
    ema_state,
    sr_filter
)}

📚 SCORE
BUY  : {buy_score}/100
SELL : {sell_score}/100
"""

    if plan:

        sl, tp1, tp2 = plan

        message += f"""

💰 TRADE PLAN
Entry : {price:.2f}
SL    : {sl:.2f}
TP1   : {tp1:.2f}
TP2   : {tp2:.2f}

RR TP1 : 1 : 1.5
RR TP2 : 1 : 2.5
"""

    message += f"""

🕐 Candle:
{latest["datetime"]}
"""

    return message


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        message = run_analysis()

        print(message)

        send_telegram(message)

    except Exception as e:

        error_message = f"""
❌ XAUUSD BOT ERROR

{str(e)}
"""

        print(error_message)

        send_telegram(error_message)