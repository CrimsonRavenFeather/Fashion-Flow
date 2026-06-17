"""
behaviour.py
------------
All functions to log user events and read/write views.json.
Works with the flat folder — views.json is in the same directory.

FUNCTIONS:
    log_view(user_id, item_id, session_id)
    log_cart_add(user_id, item_id, session_id)
    log_wishlist(user_id, item_id, session_id)
    log_remove_wishlist(user_id, item_id)
    log_purchase(user_id, item_id, session_id)
    check_discount(user_id, item_id, item_price)  -> dict | None
    get_user_behaviour(user_id)                   -> summary dict
    get_item_stats(item_id)                       -> stats dict
    get_all_engagement_scores()                   -> list (ML input)
"""

import json
import uuid
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

# ── File path (flat folder — same dir as this script) ─────────────────────────
BASE_DIR   = Path(__file__).parent
VIEWS_FILE = BASE_DIR / "data" / "views.json"

# ── Discount constants ─────────────────────────────────────────────────────────
VIEW_THRESHOLD        = 3
DISCOUNT_PERCENT      = 10
DISCOUNT_EXPIRY_HRS   = 24
MAX_DISCOUNTS_PER_DAY = 2


# ══════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _load() -> dict:
    if not VIEWS_FILE.exists():
        blank = {
            "version": "1.0",
            "schema_note": "engagement_score: views(x1)+wishlist(+2)+cart(+3)+purchase(+5)+discount(+1)",
            "behaviour_log": [],
            "discount_rules": {
                "view_threshold": VIEW_THRESHOLD,
                "discount_percent": DISCOUNT_PERCENT,
                "expiry_hours": DISCOUNT_EXPIRY_HRS,
                "max_discount_per_user_per_day": MAX_DISCOUNTS_PER_DAY
            }
        }
        _save(blank)
        return blank
    with open(VIEWS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(VIEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_session() -> str:
    return f"sess-{uuid.uuid4().hex[:8]}"


def _find_entry(log: list, user_id: str, item_id: str):
    for entry in log:
        if entry["user_id"] == user_id and entry["item_id"] == item_id:
            return entry
    return None


def _get_item_snapshot(item_id: str) -> dict:
    catalogue_file = BASE_DIR / "catalogue.json"
    if not catalogue_file.exists():
        return {}
    with open(catalogue_file, "r", encoding="utf-8") as f:
        catalogue = json.load(f)
    for item in catalogue.get("items", []):
        if item["id"] == item_id:
            return {
                "category":     item.get("category", ""),
                "sub_category": item.get("sub_category", ""),
                "gender":       item.get("gender", ""),
                "age_group":    item.get("age_group", []),
                "price":        item.get("price", 0),
                "in_stock":     item.get("in_stock", True),
            }
    return {}


def _get_related_products(item_id: str, sub_category: str, price: int, max_related: int = 4) -> list:
    catalogue_file = BASE_DIR / "catalogue.json"
    if not catalogue_file.exists():
        return []
    with open(catalogue_file, "r", encoding="utf-8") as f:
        items = json.load(f).get("items", [])
    related = []
    for item in items:
        if item["id"] == item_id:
            continue
        if item.get("sub_category") != sub_category:
            continue
        if price > 0:
            ratio = item.get("price", 0) / price
            if not (0.6 <= ratio <= 1.4):
                continue
        related.append(item["id"])
        if len(related) >= max_related:
            break
    return related


def _recalculate_engagement(entry: dict) -> float:
    score = (
        entry.get("view_count", 0) * 1.0
        + (2.0 if entry.get("wishlist")          else 0)
        + (3.0 if entry.get("cart_added")        else 0)
        + (5.0 if entry.get("purchased")         else 0)
        + (1.0 if entry.get("discount_triggered") else 0)
    )
    return round(min(score, 10.0), 1)


def _new_entry(user_id: str, item_id: str) -> dict:
    snapshot = _get_item_snapshot(item_id)
    related  = _get_related_products(
        item_id,
        snapshot.get("sub_category", ""),
        snapshot.get("price", 0)
    )
    return {
        "user_id":              user_id,
        "item_id":              item_id,
        "item_snapshot":        snapshot,
        "events":               [],
        "view_count":           0,
        "wishlist":             False,
        "cart_added":           False,
        "purchased":            False,
        "in_stock_when_viewed": snapshot.get("in_stock", True),
        "related_products":     related,
        "discount_triggered":   False,
        "discount_code":        None,
        "discounted_price":     None,
        "engagement_score":     0.0,
        "last_event_at":        None,
        "first_seen_at":        None,
    }


def _append_event(entry: dict, event_type: str, session_id: str) -> None:
    now = _now()
    entry["events"].append({
        "event_type": event_type,
        "timestamp":  now,
        "session_id": session_id,
    })
    entry["last_event_at"] = now
    if entry["first_seen_at"] is None:
        entry["first_seen_at"] = now


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC WRITE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def log_view(user_id: str, item_id: str, session_id: str = None) -> dict:
    """
    Record a product view.

    Usage:
        entry = log_view("usr-001", "product-007")
        print(entry["view_count"])   # 1
    """
    data    = _load()
    session = session_id or _new_session()
    entry   = _find_entry(data["behaviour_log"], user_id, item_id)

    if entry is None:
        entry = _new_entry(user_id, item_id)
        data["behaviour_log"].append(entry)

    _append_event(entry, "view", session)
    entry["view_count"]       = sum(1 for e in entry["events"] if e["event_type"] == "view")
    entry["engagement_score"] = _recalculate_engagement(entry)

    _save(data)
    print(f"[view]             {user_id} → {item_id}  (total views: {entry['view_count']})")
    return entry


def log_cart_add(user_id: str, item_id: str, session_id: str = None) -> dict:
    """
    Record an add-to-cart event.

    Usage:
        entry = log_cart_add("usr-001", "product-020")
        print(entry["cart_added"])   # True
    """
    data    = _load()
    session = session_id or _new_session()
    entry   = _find_entry(data["behaviour_log"], user_id, item_id)

    if entry is None:
        entry = _new_entry(user_id, item_id)
        data["behaviour_log"].append(entry)

    _append_event(entry, "cart_add", session)
    entry["cart_added"]       = True
    entry["engagement_score"] = _recalculate_engagement(entry)

    _save(data)
    print(f"[cart_add]         {user_id} → {item_id}")
    return entry


def log_wishlist(user_id: str, item_id: str, session_id: str = None) -> dict:
    """
    Add an item to the user's wishlist.

    Usage:
        entry = log_wishlist("usr-001", "product-032")
        print(entry["wishlist"])   # True
    """
    data    = _load()
    session = session_id or _new_session()
    entry   = _find_entry(data["behaviour_log"], user_id, item_id)

    if entry is None:
        entry = _new_entry(user_id, item_id)
        data["behaviour_log"].append(entry)

    _append_event(entry, "wishlist_add", session)
    entry["wishlist"]         = True
    entry["engagement_score"] = _recalculate_engagement(entry)

    _save(data)
    print(f"[wishlist_add]     {user_id} → {item_id}")
    return entry


def log_remove_wishlist(user_id: str, item_id: str) -> dict:
    """
    Remove an item from the user's wishlist.

    Usage:
        entry = log_remove_wishlist("usr-001", "product-032")
        print(entry["wishlist"])   # False
    """
    data  = _load()
    entry = _find_entry(data["behaviour_log"], user_id, item_id)

    if entry is None:
        print(f"[wishlist_remove]  no entry for {user_id}/{item_id}")
        return {}

    _append_event(entry, "wishlist_remove", _new_session())
    entry["wishlist"]         = False
    entry["engagement_score"] = _recalculate_engagement(entry)

    _save(data)
    print(f"[wishlist_remove]  {user_id} → {item_id}")
    return entry


def log_purchase(user_id: str, item_id: str, session_id: str = None) -> dict:
    """
    Record a purchase.

    Usage:
        entry = log_purchase("usr-001", "product-003")
        print(entry["purchased"])   # True
    """
    data    = _load()
    session = session_id or _new_session()
    entry   = _find_entry(data["behaviour_log"], user_id, item_id)

    if entry is None:
        entry = _new_entry(user_id, item_id)
        data["behaviour_log"].append(entry)

    _append_event(entry, "purchase", session)
    entry["purchased"]        = True
    entry["cart_added"]       = True
    entry["engagement_score"] = _recalculate_engagement(entry)

    _save(data)
    print(f"[purchase]         {user_id} → {item_id}  ✓")
    return entry


def check_discount(user_id: str, item_id: str, item_price: int = None):
    """
    Check if a discount should fire for this user-item pair.
    Fires when view_count >= VIEW_THRESHOLD and no discount issued yet.

    Args:
        user_id    : e.g. "usr-001"
        item_id    : e.g. "product-007"
        item_price : price in INR (read from snapshot if omitted)

    Returns dict if triggered, None otherwise:
        {
          "code":             "USR00110",
          "percent_off":      10,
          "original_price":   1020,
          "discounted_price": 918,
          "saving":           102,
          "expires_at":       "2026-06-12T10:00:00Z",
          "message":          "🎉 10% off! Use code USR00110 — expires in 24 hrs"
        }

    Usage:
        discount = check_discount("usr-001", "product-007")
        if discount:
            print(discount["message"])
    """
    data  = _load()
    entry = _find_entry(data["behaviour_log"], user_id, item_id)

    if entry is None:
        print(f"[discount]  no entry for {user_id}/{item_id}")
        return None

    # Already triggered — return existing info
    if entry.get("discount_triggered") and entry.get("discount_code"):
        price  = item_price or entry["item_snapshot"].get("price", 0)
        disc_p = int(price * (1 - DISCOUNT_PERCENT / 100))
        print(f"[discount]  {user_id}/{item_id}  already active: {entry['discount_code']}")
        return {
            "code":             entry["discount_code"],
            "percent_off":      DISCOUNT_PERCENT,
            "original_price":   price,
            "discounted_price": disc_p,
            "saving":           price - disc_p,
            "message":          f"Already active — use code {entry['discount_code']}"
        }

    views = entry.get("view_count", 0)
    print(f"[discount]  {user_id}/{item_id}  views={views}/{VIEW_THRESHOLD}", end="  ")

    if views < VIEW_THRESHOLD:
        print(f"→ not yet ({VIEW_THRESHOLD - views} more needed)")
        return None

    # Daily limit check
    active_today = sum(
        1 for e in data["behaviour_log"]
        if e["user_id"] == user_id and e.get("discount_triggered")
    )
    if active_today >= MAX_DISCOUNTS_PER_DAY:
        print(f"→ daily limit reached ({MAX_DISCOUNTS_PER_DAY})")
        return None

    # Create discount
    price      = item_price or entry["item_snapshot"].get("price", 0)
    disc_price = int(price * (1 - DISCOUNT_PERCENT / 100))
    code       = f"{user_id.replace('-','').upper()[:6]}{DISCOUNT_PERCENT}"
    expires_at = (datetime.utcnow() + timedelta(hours=DISCOUNT_EXPIRY_HRS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry["discount_triggered"] = True
    entry["discount_code"]      = code
    entry["discounted_price"]   = disc_price
    entry["engagement_score"]   = _recalculate_engagement(entry)
    _append_event(entry, "discount_triggered", _new_session())
    _save(data)

    print(f"→ 🎉 triggered!  code={code}  ₹{price} → ₹{disc_price}")
    return {
        "code":             code,
        "percent_off":      DISCOUNT_PERCENT,
        "original_price":   price,
        "discounted_price": disc_price,
        "saving":           price - disc_price,
        "expires_at":       expires_at,
        "message":          f"🎉  {DISCOUNT_PERCENT}% off! Use code {code} — expires in {DISCOUNT_EXPIRY_HRS} hrs"
    }


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC READ / QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_user_behaviour(user_id: str) -> dict:
    """
    Full summary of a user's tracked behaviour.

    Usage:
        summary = get_user_behaviour("usr-001")
        print(summary["wishlist"])
        print(summary["top_categories"])
    """
    data = _load()
    log  = [e for e in data["behaviour_log"] if e["user_id"] == user_id]

    if not log:
        return {"user_id": user_id, "message": "No behaviour data found"}

    cat_counter = Counter()
    for entry in log:
        cat = entry["item_snapshot"].get("category", "unknown")
        cat_counter[cat] += entry.get("view_count", 0)

    engagement_list = sorted(
        [{"item_id": e["item_id"], "score": e["engagement_score"]} for e in log],
        key=lambda x: -x["score"]
    )

    return {
        "user_id":       user_id,
        "total_views":   sum(e.get("view_count", 0) for e in log),
        "unique_items":  len(log),
        "wishlist":      [e["item_id"] for e in log if e.get("wishlist")],
        "cart":          [e["item_id"] for e in log if e.get("cart_added")],
        "purchased":     [e["item_id"] for e in log if e.get("purchased")],
        "active_discounts": [
            {"item_id": e["item_id"], "code": e["discount_code"]}
            for e in log if e.get("discount_triggered") and e.get("discount_code")
        ],
        "top_categories":     dict(cat_counter.most_common()),
        "engagement_by_item": engagement_list,
    }


def get_item_stats(item_id: str) -> dict:
    """
    Aggregate popularity stats for one item across all users.
    Feed into item-based collaborative filtering.

    Usage:
        stats = get_item_stats("product-007")
        print(stats["purchase_count"])
    """
    data    = _load()
    entries = [e for e in data["behaviour_log"] if e["item_id"] == item_id]

    if not entries:
        return {"item_id": item_id, "message": "No data yet"}

    avg_eng = round(sum(e["engagement_score"] for e in entries) / len(entries), 2)

    return {
        "item_id":        item_id,
        "total_views":    sum(e.get("view_count", 0) for e in entries),
        "wishlist_count": sum(1 for e in entries if e.get("wishlist")),
        "cart_count":     sum(1 for e in entries if e.get("cart_added")),
        "purchase_count": sum(1 for e in entries if e.get("purchased")),
        "unique_users":   len(entries),
        "avg_engagement": avg_eng,
    }


def get_all_engagement_scores() -> list:
    """
    All user-item pairs with engagement scores.
    Primary input matrix for collaborative filtering.

    Usage:
        scores = get_all_engagement_scores()
        # build a user x item matrix from this
        for row in scores:
            print(row["user_id"], row["item_id"], row["score"])
    """
    data = _load()
    result = [
        {
            "user_id":   e["user_id"],
            "item_id":   e["item_id"],
            "score":     e["engagement_score"],
            "purchased": e.get("purchased", False),
            "category":  e["item_snapshot"].get("category", ""),
        }
        for e in data["behaviour_log"]
    ]
    return sorted(result, key=lambda x: -x["score"])