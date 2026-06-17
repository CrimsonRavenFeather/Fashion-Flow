"""
app.py  —  Fashion Shopping Chatbot
-------------------------------------
Streamlit UI with LangGraph-style tools.

Tools available:
  view_catalogue       — browse all products
  filter_by_budget     — filter by price range
  search_products      — keyword/category search
  get_recommendations  — personalised picks based on profile
  view_cart            — show cart contents
  add_to_cart          — add item to cart
  remove_from_cart     — remove item from cart
  checkout             — place order
  view_wishlist        — show wishlist
  track_order          — mock order tracking

Run:
    streamlit run app.py
"""

import json
import random
import string
from pathlib import Path
import os
from datetime import datetime, timezone

import streamlit as st

# ─ Langgraph config ───────────────────────────────────────────────────────────────

from agent.graph import create_graph
from langchain_core.messages import HumanMessage

config={
    "configurable":{
        "thread_id":1
    }
}

graph = create_graph()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StyleAI — Fashion Chatbot",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent

# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADERS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_catalogue():
    with open(BASE / "data/catalogue.json", encoding="utf-8") as f:
        return json.load(f)["items"]

def load_views():
    path = BASE / "data/views.json"
    if not path.exists():
        return {"behaviour_log": [], "discount_rules": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_views(data):
    with open(BASE / "data/views.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ══════════════════════════════════════════════════════════════════════════════
# TOOLS  (LangGraph-style — each returns a structured result dict)
# ══════════════════════════════════════════════════════════════════════════════

def tool_view_catalogue(category: str = None, limit: int = 12) -> dict:
    """View all available products, optionally filtered by category."""
    items = load_catalogue()
    if category and category.lower() != "all":
        items = [i for i in items if i["category"].lower() == category.lower()
                 or i["sub_category"].lower() == category.lower()]
    in_stock = [i for i in items if i["in_stock"]]
    return {
        "tool": "view_catalogue",
        "category": category or "all",
        "total": len(in_stock),
        "items": in_stock[:limit],
    }


def tool_search_products(query: str) -> dict:
    """Search products by keyword across name, brand, tags, fabric, occasion."""
    items     = load_catalogue()
    q         = query.lower()
    matched   = []
    for item in items:
        searchable = " ".join([
            item["name"], item["brand"], item["category"],
            item["sub_category"], item["fabric"],
            " ".join(item.get("trend_tags", [])),
            " ".join(item.get("occasion", [])),
            " ".join(item.get("colors", [])),
        ]).lower()
        if q in searchable and item["in_stock"]:
            matched.append(item)
    return {
        "tool": "search_products",
        "query": query,
        "total": len(matched),
        "items": matched[:12],
    }


def tool_filter_by_budget(max_budget: int, category: str = None) -> dict:
    """Filter products within a budget, optionally by category."""
    items = load_catalogue()
    filtered = [
        i for i in items
        if i["price"] <= max_budget and i["in_stock"]
        and (not category or i["category"].lower() == category.lower())
    ]
    filtered.sort(key=lambda x: x["value_score"], reverse=True)
    return {
        "tool": "filter_by_budget",
        "max_budget": max_budget,
        "total": len(filtered),
        "items": filtered[:12],
    }


def tool_get_recommendations(user_profile: dict) -> dict:
    """Personalised picks based on age group, style prefs, and budget."""
    items      = load_catalogue()
    age        = user_profile.get("age", 24)
    budget     = user_profile.get("budget", 2000)
    style_pref = user_profile.get("style", "").lower()
    gender     = user_profile.get("gender", "female").lower()

    # Determine age group
    if age < 18:
        age_group = "16-18"
    elif age <= 24:
        age_group = "18-24"
    elif age <= 34:
        age_group = "25-34"
    elif age <= 44:
        age_group = "35-44"
    else:
        age_group = "45+"

    scored = []
    for item in items:
        if not item["in_stock"]:
            continue
        if item["price"] > budget * 1.1:
            continue
        if item["gender"] not in (gender, "unisex"):
            continue

        score = item.get("value_score", 5.0)
        if age_group in item.get("age_group", []):
            score += 2.0
        if style_pref and style_pref in " ".join(item.get("trend_tags", [])).lower():
            score += 1.5
        if "trending" in item.get("trend_tags", []):
            score += 1.0
        if item["price"] <= budget:
            score += 0.5

        scored.append({**item, "_score": round(score, 2)})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    return {
        "tool": "get_recommendations",
        "age_group": age_group,
        "budget": budget,
        "total": len(scored),
        "items": scored[:8],
    }


def tool_view_cart() -> dict:
    """Show current cart contents with totals."""
    cart  = st.session_state.get("cart", {})
    items = load_catalogue()
    item_map = {i["id"]: i for i in items}

    cart_items = []
    subtotal   = 0
    for item_id, qty in cart.items():
        item = item_map.get(item_id)
        if item:
            line_total = item["price"] * qty
            subtotal  += line_total
            cart_items.append({**item, "qty": qty, "line_total": line_total})

    return {
        "tool":       "view_cart",
        "cart_items": cart_items,
        "subtotal":   subtotal,
        "item_count": sum(cart.values()),
    }


def tool_add_to_cart(item_id: str, qty: int = 1) -> dict:
    """Add an item to cart."""
    items    = load_catalogue()
    item_map = {i["id"]: i for i in items}
    item     = item_map.get(item_id)

    if not item:
        return {"tool": "add_to_cart", "success": False, "message": f"Item '{item_id}' not found."}
    if not item["in_stock"]:
        return {"tool": "add_to_cart", "success": False, "message": f"'{item['name']}' is out of stock."}

    cart = st.session_state.setdefault("cart", {})
    cart[item_id] = cart.get(item_id, 0) + qty
    st.session_state["cart"] = cart

    return {
        "tool":    "add_to_cart",
        "success": True,
        "item":    item,
        "qty":     cart[item_id],
        "message": f"✅ Added **{item['name']}** to cart (qty: {cart[item_id]})",
    }


def tool_remove_from_cart(item_id: str) -> dict:
    """Remove an item from cart."""
    cart = st.session_state.get("cart", {})
    if item_id not in cart:
        return {"tool": "remove_from_cart", "success": False, "message": "Item not in cart."}

    items    = load_catalogue()
    item_map = {i["id"]: i for i in items}
    name     = item_map.get(item_id, {}).get("name", item_id)
    del cart[item_id]
    st.session_state["cart"] = cart
    return {"tool": "remove_from_cart", "success": True, "message": f"🗑️ Removed **{name}** from cart."}


def tool_checkout() -> dict:
    """Place order and clear cart."""
    cart = st.session_state.get("cart", {})
    if not cart:
        return {"tool": "checkout", "success": False, "message": "Your cart is empty."}

    cart_result = tool_view_cart()
    order_id    = "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    eta         = "3–5 business days"

    st.session_state["cart"]   = {}
    st.session_state["orders"] = st.session_state.get("orders", [])
    st.session_state["orders"].append({
        "order_id": order_id,
        "items":    cart_result["cart_items"],
        "total":    cart_result["subtotal"],
        "placed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status":   "Confirmed",
        "eta":      eta,
    })
    return {
        "tool":       "checkout",
        "success":    True,
        "order_id":   order_id,
        "total":      cart_result["subtotal"],
        "item_count": cart_result["item_count"],
        "eta":        eta,
        "message":    f"🎉 Order **{order_id}** placed! Total: ₹{cart_result['subtotal']:,}. ETA: {eta}",
    }


def tool_view_wishlist() -> dict:
    """Show wishlisted items from views.json."""
    views_data = load_views()
    user_id    = st.session_state.get("user_profile", {}).get("user_id", "usr-001")
    items      = load_catalogue()
    item_map   = {i["id"]: i for i in items}

    wishlist_ids = [
        e["item_id"] for e in views_data.get("behaviour_log", [])
        if e.get("user_id") == user_id and e.get("wishlist")
    ]
    wishlist_items = [item_map[id] for id in wishlist_ids if id in item_map]

    return {
        "tool":  "view_wishlist",
        "total": len(wishlist_items),
        "items": wishlist_items,
    }


def tool_track_order() -> dict:
    """Show recent order statuses."""
    orders = st.session_state.get("orders", [])
    return {"tool": "track_order", "orders": orders}


# ── Tool registry (keyword → tool function) ───────────────────────────────────
TOOL_KEYWORDS = {
    # catalogue
    "catalogue":      lambda: tool_view_catalogue(),
    "show catalogue": lambda: tool_view_catalogue(),
    "view catalogue": lambda: tool_view_catalogue(),
    "show products":  lambda: tool_view_catalogue(),
    "all products":   lambda: tool_view_catalogue(),
    "browse":         lambda: tool_view_catalogue(),
    # cart
    "cart":           lambda: tool_view_cart(),
    "view cart":      lambda: tool_view_cart(),
    "show cart":      lambda: tool_view_cart(),
    "my cart":        lambda: tool_view_cart(),
    # wishlist
    "wishlist":       lambda: tool_view_wishlist(),
    "my wishlist":    lambda: tool_view_wishlist(),
    "saved items":    lambda: tool_view_wishlist(),
    # checkout
    "checkout":       lambda: tool_checkout(),
    "place order":    lambda: tool_checkout(),
    "buy now":        lambda: tool_checkout(),
    "order":          lambda: tool_checkout(),
    # orders
    "track":          lambda: tool_track_order(),
    "my orders":      lambda: tool_track_order(),
    "order status":   lambda: tool_track_order(),
    # recommendations
    "recommend":      lambda: tool_get_recommendations(st.session_state.get("user_profile", {})),
    "suggestions":    lambda: tool_get_recommendations(st.session_state.get("user_profile", {})),
    "what should i":  lambda: tool_get_recommendations(st.session_state.get("user_profile", {})),
    "picks for me":   lambda: tool_get_recommendations(st.session_state.get("user_profile", {})),
    "show me":        lambda: tool_get_recommendations(st.session_state.get("user_profile", {})),
}

def detect_tool(text: str):
    """Return (tool_name, result) if a keyword matches, else None."""
    tl = text.lower().strip()

    # Budget filter: "under ₹1000" or "budget 1500" or "less than 2000"
    import re
    budget_match = re.search(r"(?:under|budget|less than|below|upto|up to|within)\s*₹?\s*(\d+)", tl)
    if budget_match:
        budget = int(budget_match.group(1))
        return "filter_by_budget", tool_filter_by_budget(budget)

    # Add to cart: "add product-007" or "buy product-007"
    add_match = re.search(r"(?:add|buy|cart)\s+(product-\d+)", tl)
    if add_match:
        return "add_to_cart", tool_add_to_cart(add_match.group(1))

    # Remove from cart
    remove_match = re.search(r"(?:remove|delete)\s+(product-\d+)", tl)
    if remove_match:
        return "remove_from_cart", tool_remove_from_cart(remove_match.group(1))

    # Category search: "show ethnic" "show footwear" etc.
    categories = ["ethnic", "casual", "footwear", "western", "formal", "accessories",
                  "kurta", "saree", "sneakers", "flats", "top", "bottom", "dress"]
    for cat in categories:
        if f"show {cat}" in tl or f"view {cat}" in tl or f"{cat} items" in tl or tl == cat:
            return "view_catalogue", tool_view_catalogue(category=cat)

    # Keyword search: "search cotton" or "find kurta"
    search_match = re.search(r"(?:search|find|looking for|show me)\s+(.+)", tl)
    if search_match:
        q = search_match.group(1).strip()
        if len(q) > 2 and q not in ["products", "items", "clothes", "catalogue"]:
            result = tool_search_products(q)
            if result["total"] > 0:
                return "search_products", result

    # Exact keyword matches
    for kw, fn in TOOL_KEYWORDS.items():
        if kw in tl:
            return kw, fn()

    return None, None


# ══════════════════════════════════════════════════════════════════════════════
# AGENT RESPONSE GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def agent_response(user_msg: str) -> dict:
    """
    Simulates LangGraph agent: detect tool → call → format response.
    Returns {"text": ..., "tool_result": ..., "tool_name": ...}
    """


    response=graph.invoke(
        {
            "messages":[HumanMessage(content=user_msg)]
        },
        config=config
    )

    # tool_name, result = detect_tool(user_msg)
    profile = st.session_state.get("user_profile", {})
    name    = profile.get("name", "there")

    # if result is None:
    #     # Conversational fallback
    #     tl = user_msg.lower()
    #     if any(w in tl for w in ["hello", "hi", "hey", "start"]):
    #         text = (f"Hey {name}! 👋 I'm your personal fashion assistant.\n\n"
    #                 "Here's what I can do:\n"
    #                 "• **show catalogue** — browse all products\n"
    #                 "• **show ethnic / footwear / casual** — filter by category\n"
    #                 "• **budget 2000** — find items under your budget\n"
    #                 "• **recommend** — get personalised picks\n"
    #                 "• **search cotton kurta** — search by keyword\n"
    #                 "• **add product-007** — add item to cart\n"
    #                 "• **cart** — view your cart\n"
    #                 "• **checkout** — place your order\n"
    #                 "• **wishlist** — view your saved items\n"
    #                 "• **track** — track your orders")
    #     elif any(w in tl for w in ["thank", "thanks", "great", "awesome"]):
    #         text = f"Happy to help, {name}! 😊 Anything else you'd like to explore?"
    #     elif any(w in tl for w in ["price", "cost", "expensive", "cheap"]):
    #         text = "Try **budget 1500** or **budget 2500** to filter products by price range! 💰"
    #     elif any(w in tl for w in ["help", "what can", "how"]):
    #         text = ("I can help you:\n"
    #                 "🛍️ **browse** — `show catalogue`\n"
    #                 "🔍 **search** — `search floral kurta`\n"
    #                 "💰 **budget filter** — `budget 2000`\n"
    #                 "✨ **recommendations** — `recommend`\n"
    #                 "🛒 **cart** — `view cart` / `add product-001`\n"
    #                 "📦 **orders** — `checkout` / `track`")
    #     else:
    #         text = (f"I didn't quite catch that. Try typing **show catalogue**, "
    #                 f"**recommend**, **budget 2000**, or **search kurta**. "
    #                 f"Type **help** to see all options!")
    #     return {"text": text, "tool_result": None, "tool_name": None}

    # # Build text response based on tool result
    # if tool_name in ("view_catalogue", "filter_by_budget", "search_products"):
    #     total = result["total"]
    #     if total == 0:
    #         text = f"I couldn't find any items matching that. Try a different search or **show catalogue** to browse everything."
    #     else:
    #         if tool_name == "filter_by_budget":
    #             text = f"Found **{total} items** under ₹{result['max_budget']:,} for you, {name}! Here are the top picks by value:"
    #         elif tool_name == "search_products":
    #             text = f"Found **{total} results** for *\"{result['query']}\"*. Here they are:"
    #         else:
    #             cat = result["category"]
    #             text = f"Here's our **{cat}** collection — {total} items in stock:"

    # elif tool_name == "get_recommendations":
    #     text = (f"Based on your profile, {name}, here are my top picks "
    #             f"for age group **{result['age_group']}** within ₹{result['budget']:,}:")

    # elif tool_name == "view_cart":
    #     if result["item_count"] == 0:
    #         text = f"Your cart is empty, {name}. Try **show catalogue** or **recommend** to find something you'll love!"
    #     else:
    #         text = (f"Here's your cart, {name} — "
    #                 f"**{result['item_count']} item(s)**, subtotal **₹{result['subtotal']:,}**.\n"
    #                 "Type **checkout** to place your order!")

    # elif tool_name == "add_to_cart":
    #     text = result["message"]

    # elif tool_name == "remove_from_cart":
    #     text = result["message"]

    # elif tool_name == "checkout":
    #     if result["success"]:
    #         text = result["message"]
    #     else:
    #         text = result["message"]

    # elif tool_name == "view_wishlist":
    #     if result["total"] == 0:
    #         text = f"Your wishlist is empty, {name}. Browse products and wishlist your favourites!"
    #     else:
    #         text = f"Your wishlist has **{result['total']} items**, {name}:"

    # elif tool_name == "track_order":
    #     if not result["orders"]:
    #         text = f"No orders yet, {name}. Place your first order by adding items and typing **checkout**!"
    #     else:
    #         text = f"Here are your recent orders, {name}:"

    # else:
    #     text = f"Here you go, {name}!"
    

    return {"text": response["messages"][-1].content, "tool_result": "", "tool_name": ""}


# ══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

def render_product_card(item: dict, key_prefix: str = ""):
    """Render a single product card with Add to Cart button."""
    in_stock = item.get("in_stock", True)
    discount = item.get("discount_percent", 0)

    with st.container():
        st.markdown(f"""
        <div style="
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 14px;
            background: #fff;
            height: 100%;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        ">
            <div style="
                background: linear-gradient(135deg, #f8f4f0, #ede8e3);
                border-radius: 8px;
                height: 120px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 10px;
                font-size: 2rem;
            ">
                {"👗" if item["category"] == "ethnic" else
                 "👟" if item["category"] == "footwear" else
                 "👚" if item["category"] == "casual" else
                 "💼" if item["category"] == "formal" else "🛍️"}
            </div>
            <div style="font-size:11px; color:#9ca3af; text-transform:uppercase; letter-spacing:.05em;">
                {item['brand']} · {item['sub_category']}
            </div>
            <div style="font-weight:600; font-size:14px; color:#1f2937; margin:4px 0;">
                {item['name']}
            </div>
            <div style="font-size:12px; color:#6b7280; margin-bottom:6px;">
                {", ".join(item.get("colors", [])[:2])} · {item['fabric']}
            </div>
            <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                <span style="font-weight:700; font-size:16px; color:#111827;">₹{item['price']:,}</span>
                {"<span style='font-size:11px;color:#9ca3af;text-decoration:line-through;'>₹" + str(item['original_price']) + "</span>" if discount > 0 else ""}
                {"<span style='font-size:11px;background:#dcfce7;color:#16a34a;padding:1px 6px;border-radius:20px;'>" + str(discount) + "% off</span>" if discount > 0 else ""}
            </div>
            <div style="font-size:11px; color:#6b7280; margin-bottom:8px;">
                ⭐ {item['rating']} ({item['review_count']} reviews)
            </div>
            {"<div style='font-size:11px;color:#ef4444;'>Out of stock</div>" if not in_stock else ""}
        </div>
        """, unsafe_allow_html=True)

        if in_stock:
            if st.button("Add to Cart 🛒", key=f"{key_prefix}_{item['id']}", use_container_width=True):
                result = tool_add_to_cart(item["id"])
                st.session_state.messages.append({
                    "role": "assistant",
                    "text": result["message"],
                    "tool_result": None,
                    "tool_name": "add_to_cart",
                })
                st.rerun()


def render_tool_result(result: dict, tool_name: str):
    """Render the visual output of a tool call."""
    if not result:
        return

    # Product grid tools
    if tool_name in ("view_catalogue", "filter_by_budget", "search_products", "get_recommendations"):
        items = result.get("items", [])
        if not items:
            return
        cols = st.columns(min(4, len(items)))
        for idx, item in enumerate(items):
            with cols[idx % 4]:
                render_product_card(item, key_prefix=f"{tool_name}_{idx}")

    # Cart
    elif tool_name == "view_cart":
        cart_items = result.get("cart_items", [])
        if cart_items:
            for ci in cart_items:
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    st.markdown(f"**{ci['name']}** by {ci['brand']}")
                    st.caption(f"{ci['sub_category']} · {ci['fabric']}")
                with col2:
                    st.markdown(f"₹{ci['price']:,}")
                with col3:
                    st.markdown(f"× {ci['qty']}")
                with col4:
                    st.markdown(f"**₹{ci['line_total']:,}**")
                st.divider()
            st.markdown(f"### Total: ₹{result['subtotal']:,}")

    # Wishlist
    elif tool_name == "view_wishlist":
        items = result.get("items", [])
        if items:
            cols = st.columns(min(4, len(items)))
            for idx, item in enumerate(items):
                with cols[idx % 4]:
                    render_product_card(item, key_prefix=f"wl_{idx}")

    # Track order
    elif tool_name == "track_order":
        for order in result.get("orders", []):
            with st.container():
                st.markdown(f"""
                <div style="border:1px solid #e5e7eb; border-radius:10px; padding:14px; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div style="font-weight:600; font-size:15px;">📦 {order['order_id']}</div>
                            <div style="font-size:12px; color:#6b7280;">Placed: {order['placed_at']}</div>
                        </div>
                        <div style="background:#dcfce7; color:#16a34a; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:500;">
                            {order['status']}
                        </div>
                    </div>
                    <div style="margin-top:8px; font-size:13px; color:#374151;">
                        {len(order['items'])} item(s) · <strong>₹{order['total']:,}</strong> · ETA: {order['eta']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # Checkout success
    elif tool_name == "checkout" and result.get("success"):
        st.success(f"🎉 Order **{result['order_id']}** confirmed! ₹{result['total']:,} · ETA: {result['eta']}")
        st.balloons()


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE INIT
# ══════════════════════════════════════════════════════════════════════════════

def init_session():
    if "stage" not in st.session_state:
        st.session_state.stage = "onboarding"   # onboarding | chat
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = {}
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "cart" not in st.session_state:
        st.session_state.cart = {}
    if "orders" not in st.session_state:
        st.session_state.orders = []

init_session()


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Hide streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem !important; }

/* Chat bubbles */
.user-bubble {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    padding: 12px 16px;
    border-radius: 18px 18px 4px 18px;
    max-width: 70%;
    margin-left: auto;
    margin-bottom: 4px;
    font-size: 14px;
    line-height: 1.5;
    box-shadow: 0 2px 8px rgba(99,102,241,0.25);
}

.bot-bubble {
    background: #f8f9fa;
    color: #1f2937;
    padding: 12px 16px;
    border-radius: 18px 18px 18px 4px;
    max-width: 80%;
    margin-bottom: 4px;
    font-size: 14px;
    line-height: 1.6;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.chat-avatar-bot {
    width: 32px; height: 32px;
    background: linear-gradient(135deg, #f59e0b, #ef4444);
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
    margin-right: 8px;
}

.tool-badge {
    display: inline-block;
    background: #ede9fe;
    color: #7c3aed;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 20px;
    margin-bottom: 6px;
    font-weight: 500;
}

/* Onboarding form */
.onboard-card {
    max-width: 480px;
    margin: 0 auto;
    padding: 40px;
    background: white;
    border-radius: 20px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.10);
}

/* Quick action chips */
.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}

/* Navbar */
.navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    border-bottom: 1px solid #e5e7eb;
    margin-bottom: 16px;
}

.stButton>button {
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}

/* Input bar */
.stChatInput > div {
    border-radius: 14px !important;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING SCREEN
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.stage == "onboarding":
    col_left, col_mid, col_right = st.columns([1, 2, 1])
    with col_mid:
        st.markdown("""
        <div style="text-align:center; padding: 40px 0 20px;">
            <div style="font-size:56px; margin-bottom:12px;">👗</div>
            <div style="font-size:28px; font-weight:700; color:#111827; letter-spacing:-0.5px;">
                StyleAI
            </div>
            <div style="font-size:15px; color:#6b7280; margin-top:6px;">
                Your personal fashion assistant
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("onboarding_form"):
            st.markdown("#### Tell us about yourself")
            st.caption("We'll use this to personalise your experience")

            name   = st.text_input("Your name", placeholder="e.g. Priya")
            age    = st.number_input("Age", min_value=13, max_value=80, value=24, step=1)
            gender = st.selectbox("Gender", ["Female", "Male", "Unisex / Prefer not to say"])
            budget = st.slider("Shopping budget (₹)", 500, 5000, 2000, step=100,
                               help="Maximum you'd like to spend on an outfit")
            style  = st.selectbox("Style preference",
                                  ["Ethnic", "Casual", "Western", "Minimalist",
                                   "Streetwear", "Formal", "Mix of everything"])

            submitted = st.form_submit_button("Start Shopping →", use_container_width=True)

                
        if submitted and name.strip():
            age_int = int(age)

            if age_int < 18:
                age_group = "16-18"
            elif age_int <= 24:
                age_group = "18-24"
            elif age_int <= 34:
                age_group = "25-34"
            elif age_int <= 44:
                age_group = "35-44"
            else:
                age_group = "45+"

            now = datetime.now(timezone.utc).isoformat()

            user_id = f"usr-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Map style selection to categories
            style_categories = {
                "ethnic": ["ethnic"],
                "casual": ["casual"],
                "western": ["western"],
                "minimalist": ["casual", "western"],
                "streetwear": ["casual", "western"],
                "formal": ["formal"],
                "mix of everything": ["ethnic", "casual", "western", "formal"]
            }

            user_profile = {
                "user_id": user_id,
                "name": name.strip(),
                "age": age_int,
                "age_group": age_group,
                "gender": gender.lower().split()[0],

                "location": {
                    "city": "Kolkata",
                    "state": "",
                    "currency": "INR"
                },

                "budget": {
                    "total": int(budget * 4),  # assuming monthly budget
                    "per_item_max": int(budget),
                    "flexibility_percent": 10
                },

                "style_preferences": {
                    "categories": style_categories.get(
                        style.lower(),
                        ["casual"]
                    ),
                    "avoid": [],
                    "favorite_colors": [],
                    "favorite_fabrics": [],
                    "occasions": [
                        "college",
                        "casual",
                        "office"
                    ]
                },

                "body_profile": {},

                "photo_path": "",

                "created_at": now,
                "last_active": now
            }

            # Save in session
            st.session_state.user_profile = user_profile

            # Save to JSON
            with open("data/user.json", "w", encoding="utf-8") as f:
                json.dump(user_profile, f, indent=2)

            st.success("Profile created successfully!")
            st.session_state.stage = "chat"
            # Giving langgraph user info

            user_detail_query = f"""
            You are a personalized AI Shopping Assistant.

            Store the following user profile and use it as persistent context for the entire session.

            USER PROFILE
            ------------
            User ID: {st.session_state.user_profile['user_id']}
            Name: {st.session_state.user_profile['name']}
            Age: {st.session_state.user_profile['age']}
            Age Group: {st.session_state.user_profile['age_group']}
            Gender: {st.session_state.user_profile['gender']}
            Budget Information: {st.session_state.user_profile['budget']}
            Style Preferences: {st.session_state.user_profile['style_preferences']}
            """

            graph.invoke(
                {
                    "messages":[HumanMessage(content=user_detail_query)]
                },
                config=config
            )

            # Giving welcome message
            
            result=graph.invoke(
                {
                    "messages":[HumanMessage(content="Act as a shopping assistant. Welcome the user to the platform in a warm and professional manner. Briefly highlight personalized recommendations, trending products, exclusive deals, and offer assistance in finding products that match their preferences.")]
                },
                config=config
            )

            st.session_state.messages.append({
                "role": "assistant", "text": result["messages"][-1].content,
                "tool_result": None, "tool_name": None,
            })
            st.rerun()
        elif submitted:
            st.error("Please enter your name to continue.")

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CHAT SCREEN
# ══════════════════════════════════════════════════════════════════════════════

profile     = st.session_state.user_profile
cart        = st.session_state.cart
cart_count  = sum(cart.values())

# ── Navbar ─────────────────────────────────────────────────────────────────
nav_left, nav_mid, nav_right = st.columns([2, 3, 2])
with nav_left:
    st.markdown(f"<div style='font-size:20px;font-weight:700;color:#111;'>👗 StyleAI</div>", unsafe_allow_html=True)
# with nav_mid:
#     st.markdown(
#         f"<div style='text-align:center;font-size:13px;color:#6b7280;'>"
#         f"Hi <strong>{profile.get('name','')}</strong> · "
#         f"Age {profile.get('age','')} · "
#         # f"Budget ₹{profile.get('budget',0):,} · "
#         f"Style: {profile.get('style','').title()}"
#         f"</div>", unsafe_allow_html=True
#     )
with nav_right:
    col_c, col_r = st.columns(2)
    with col_c:
        if st.button(f"🛒 Cart ({cart_count})", use_container_width=True):
            result = tool_view_cart()
            st.session_state.messages.append({
                "role": "assistant",
                "text": (f"Here's your cart — {result['item_count']} item(s), "
                         f"₹{result['subtotal']:,}" if result["item_count"] else
                         "Your cart is empty."),
                "tool_result": result, "tool_name": "view_cart",
            })
            st.rerun()
    with col_r:
        if st.button("↩ Reset", use_container_width=True):
            for key in ["stage","user_profile","messages","cart","orders"]:
                st.session_state.pop(key, None)
            st.rerun()

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ── Quick action chips ──────────────────────────────────────────────────────
st.markdown("<div style='font-size:12px;color:#9ca3af;margin-bottom:6px;'>Quick actions:</div>", unsafe_allow_html=True)
chip_cols = st.columns(8)
chips = [
    ("✨ Recommend", "recommend"),
    ("👗 Catalogue", "show catalogue"),
    ("🪡 Ethnic",    "show ethnic"),
    ("👟 Footwear",  "show footwear"),
    ("💰 Budget",    f"budget {profile.get('budget', 2000)}"),
    ("🛒 Cart",      "view cart"),
    ("❤️ Wishlist",  "my wishlist"),
    ("📦 Orders",    "track"),
]
for i, (label, cmd) in enumerate(chips):
    with chip_cols[i]:
        if st.button(label, key=f"chip_{i}", use_container_width=True):
            # inject as user message
            st.session_state.messages.append({
                "role": "user", "text": cmd,
                "tool_result": None, "tool_name": None,
            })
            resp = agent_response(cmd)
            st.session_state.messages.append({
                "role": "assistant", **resp,
            })
            st.rerun()

st.markdown("<hr style='margin:10px 0;border-color:#f3f4f6;'>", unsafe_allow_html=True)

# ── Chat history ──────────────────────────────────────────────────────────────
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(
                f"<div style='display:flex;justify-content:flex-end;margin-bottom:12px;'>"
                f"<div class='user-bubble'>{msg['text']}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div style='display:flex;align-items:flex-start;margin-bottom:4px;'>"
                f"<div class='chat-avatar-bot'>🤖</div>"
                f"<div>"
                f"{'<div class=tool-badge>🔧 ' + (msg.get('tool_name') or '').replace('_',' ').title() + '</div>' if msg.get('tool_name') else ''}"
                f"<div class='bot-bubble'>{msg['text']}</div>"
                f"</div></div>",
                unsafe_allow_html=True
            )
            # Render tool result visuals
            if msg.get("tool_result") and msg.get("tool_name"):
                render_tool_result(msg["tool_result"], msg["tool_name"])
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── Chat input ────────────────────────────────────────────────────────────────
if user_input := st.chat_input("Ask me anything — 'show catalogue', 'budget 2000', 'recommend', 'add product-007'…"):
    st.session_state.messages.append({
        "role": "user", "text": user_input,
        "tool_result": None, "tool_name": None,
    })
    resp = agent_response(user_input)
    st.session_state.messages.append({
        "role": "assistant", **resp,
    })
    st.rerun()