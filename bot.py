# ============================================================
# V1.6.8 CONFIRMATION GATE
# ============================================================

def confirmation_gate(
    direction,
    score,
    structure,
    bos,
    choch,
    breakout,
    retest,
    ema_state,
    sr
):
    """
    Entry hanya boleh aktif jika terdapat konfirmasi struktur
    yang cukup kuat.

    Score tinggi TIDAK otomatis berarti entry.
    """

    # --------------------------------------------------------
    # SCORE MINIMUM
    # --------------------------------------------------------

    if score < 70:
        return False, "Score belum mencapai minimum entry"

    # --------------------------------------------------------
    # EMA COMPRESSION PROTECTION
    # --------------------------------------------------------

    if ema_state == "COMPRESSION":

        if (
            bos == "NONE"
            and choch == "NONE"
            and breakout == "NONE"
        ):

            return (
                False,
                "EMA compression tanpa BOS/CHoCH/breakout"
            )

    # --------------------------------------------------------
    # STRUCTURE MIXED PROTECTION
    # --------------------------------------------------------

    if structure == "MIXED":

        if (
            bos == "NONE"
            and choch == "NONE"
        ):

            return (
                False,
                "Market structure MIXED tanpa BOS/CHoCH"
            )

    # --------------------------------------------------------
    # BUY CONFIRMATION
    # --------------------------------------------------------

    if direction == "BUY":

        bullish_confirmation = (
            structure == "BULLISH"
            or bos == "BULLISH BOS"
            or choch == "BULLISH CHoCH"
            or breakout == "BULLISH BREAKOUT"
        )

        if not bullish_confirmation:

            return (
                False,
                "Belum ada bullish structural confirmation"
            )

        # BUY dekat resistance
        if sr["resistance_zone"]:

            return (
                False,
                "BUY terlalu dekat resistance"
            )

    # --------------------------------------------------------
    # SELL CONFIRMATION
    # --------------------------------------------------------

    if direction == "SELL":

        bearish_confirmation = (
            structure == "BEARISH"
            or bos == "BEARISH BOS"
            or choch == "BEARISH CHoCH"
            or breakout == "BEARISH BREAKOUT"
        )

        if not bearish_confirmation:

            return (
                False,
                "Belum ada bearish structural confirmation"
            )

        # SELL dekat support
        if sr["support_zone"]:

            return (
                False,
                "SELL terlalu dekat support"
            )

    # --------------------------------------------------------
    # RETEST QUALITY
    # --------------------------------------------------------

    if (
        bos != "NONE"
        and retest == "NONE"
    ):

        # BOS ada tetapi belum retest.
        # Boleh WATCH, tetapi jangan entry langsung.
        return (
            False,
            "BOS sudah terjadi tetapi belum retest"
        )

    return True, "Entry confirmation valid"