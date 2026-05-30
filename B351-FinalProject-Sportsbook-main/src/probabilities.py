# odds -> implied probability helpers


def american_to_prob(price):
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p > 0:
        return 100.0 / (p + 100.0)
    if p < 0:
        return -p / (-p + 100.0)
    return None


def decimal_to_prob(price):
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p <= 1.0:
        return None
    return 1.0 / p


def remove_margin(prob_a, prob_b):
    # rescale a 2-way market so the two sides sum to 1
    if prob_a is None or prob_b is None:
        return None
    s = prob_a + prob_b
    if s <= 0:
        return None
    return prob_a / s


def remove_margin_pair(prob_a, prob_b):
    if prob_a is None or prob_b is None:
        return None, None
    s = prob_a + prob_b
    if s <= 0:
        return None, None
    return prob_a / s, prob_b / s
