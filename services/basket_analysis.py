"""Apriori market-basket analysis over POS transaction line-items.

Only 6 menu items exist, so the itemset space is tiny (max 2^6), but the
data has real structure: most transactions carry exactly 2 items, and a
handful of pairs dominate. Association rules (support/confidence/lift) turn
that into concrete bundle/upsell recommendations rather than a guess.
"""

from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

from services.data_loader import get_data

MIN_SUPPORT = 0.01
MIN_LIFT = 1.05


def _basket_matrix():
    d = get_data()
    pos = d["pos"]
    baskets = pos.groupby("Transaction_ID")["Item_Name"].apply(list).tolist()
    te = TransactionEncoder()
    encoded = te.fit(baskets).transform(baskets)
    import pandas as pd
    return pd.DataFrame(encoded, columns=te.columns_), len(baskets)


def get_association_rules(min_support=MIN_SUPPORT, min_lift=MIN_LIFT):
    df, basket_count = _basket_matrix()

    frequent = apriori(df, min_support=min_support, use_colnames=True)
    if frequent.empty:
        return {"rules": [], "basket_count": basket_count, "note": "No itemsets clear that support threshold."}

    rules = association_rules(frequent, metric="lift", min_threshold=min_lift, num_itemsets=len(frequent))
    rules = rules[(rules["antecedents"].apply(len) == 1) & (rules["consequents"].apply(len) == 1)]
    rules = rules.sort_values("lift", ascending=False)

    out = []
    for _, r in rules.iterrows():
        antecedent = next(iter(r["antecedents"]))
        consequent = next(iter(r["consequents"]))
        lift = round(float(r["lift"]), 2)
        confidence_pct = round(float(r["confidence"]) * 100, 1)
        out.append({
            "antecedent": antecedent,
            "consequent": consequent,
            "support_pct": round(float(r["support"]) * 100, 2),
            "confidence_pct": confidence_pct,
            "lift": lift,
            "recommendation": (
                f"When a customer orders {antecedent}, prompt {consequent} — ordered together "
                f"{lift}x more than chance ({confidence_pct}% of {antecedent} orders include it)."
            ),
        })

    return {
        "rules": out,
        "basket_count": basket_count,
        "min_support": min_support,
        "min_lift": min_lift,
        "note": (
            f"Computed over {basket_count:,} real transactions via the apriori algorithm. "
            "Lift > 1 means the pair co-occurs more than random chance would predict; "
            "confidence is directional (share of the antecedent's own orders that include the consequent)."
        ),
    }
