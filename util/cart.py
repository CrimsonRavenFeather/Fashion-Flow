from agent.tools import get_product_details

import json
import os

CART_FILE = "data/cart.json"


def _load_cart():
    """Load cart from disk."""

    if not os.path.exists(CART_FILE):
        return {"items": []}

    with open(CART_FILE, "r") as f:
        return json.load(f)


def _save_cart(cart):
    """Persist cart to disk."""

    os.makedirs("data", exist_ok=True)

    with open(CART_FILE, "w") as f:
        json.dump(cart, f, indent=2)

def add_to_cart(product_id: str, quantity: int = 1):
    """
    Add a product to the user's shopping cart.

    Use this tool when the user wants to purchase, save, or keep a
    product for later. If the product is already present in the cart,
    its quantity is increased automatically.

    Typical requests:
    - Add this item to my cart
    - Buy this product
    - Save this for later
    - Add two of these to my cart

    Returns a confirmation message indicating whether the product
    was added or its quantity was updated.
    """

    cart = _load_cart()

    for item in cart["items"]:
        if item["product_id"] == product_id:
            item["quantity"] += quantity
            _save_cart(cart)
            return f"Updated quantity for {product_id}"

    cart["items"].append({
        "product_id": product_id,
        "quantity": quantity
    })

    _save_cart(cart)

    return f"Added {product_id} to cart"

def remove_from_cart(product_id: str):
    """
    Remove a product from the user's shopping cart.

    Use this tool when the user no longer wishes to purchase an item
    or explicitly asks for its removal.

    Typical requests:
    - Remove this item
    - Delete this from my cart
    - I don't want this anymore

    Returns a confirmation message indicating that the product
    was removed from the cart.
    """

    cart = _load_cart()

    cart["items"] = [
        item
        for item in cart["items"]
        if item["product_id"] != product_id
    ]

    _save_cart(cart)

    return f"Removed {product_id} from cart"

def update_cart_quantity(product_id: str, quantity: int):
    """
    Update the quantity of a product already present in the cart.

    Use this tool when the user wants to increase, decrease, or set
    a specific quantity for a cart item.

    Typical requests:
    - Change quantity to 3
    - Increase this item to 2 units
    - Set quantity to 5

    If the requested quantity is zero or negative, the item is
    removed from the cart.

    Returns a confirmation message describing the update.
    """
    
    cart = _load_cart()

    if quantity <= 0:
        return remove_from_cart(product_id)

    for item in cart["items"]:
        if item["product_id"] == product_id:
            item["quantity"] = quantity
            _save_cart(cart)
            return f"Updated quantity for {product_id}"

    return f"{product_id} not found in cart"


def clear_cart():
    """
    Remove all products from the shopping cart.

    Use this tool when the user wants to empty their cart and start
    over.

    Typical requests:
    - Clear my cart
    - Remove everything
    - Empty the cart

    Returns a confirmation message indicating that the cart has
    been cleared.
    """

    _save_cart({"items": []})

    return "Cart cleared"

def get_cart():
    """
    Retrieve the current contents of the shopping cart.

    Use this tool whenever the user wants to review selected items,
    check prices, calculate totals, or inspect their cart before
    making a purchase.

    Typical requests:
    - Show my cart
    - What items have I selected?
    - How much will my order cost?
    - Review my cart

    Returns the products currently in the cart together with
    quantities, subtotals, and the overall cart total.
    """

    cart = _load_cart()

    result = []
    total = 0

    for item in cart["items"]:

        product = get_product_details(item["product_id"])

        if "error" in product:
            continue

        subtotal = product["price"] * item["quantity"]

        result.append({
            "product_id": product["id"],
            "name": product["name"],
            "price": product["price"],
            "quantity": item["quantity"],
            "subtotal": subtotal,
            "image_url": product["image_url"]
        })

        total += subtotal

    return {
        "items": result,
        "total": total,
        "item_count": len(result)
    }

import json
from datetime import datetime


def checkout():
    """
    Complete the purchase for all items currently in the cart.

    Use this tool when the user is ready to place an order, complete
    payment, or check out their shopping cart.

    Typical user requests:
    - Checkout
    - Place my order
    - Buy everything in my cart
    - Proceed to payment
    - Complete purchase

    The tool:
    - Retrieves all items currently in the cart.
    - Calculates the total cart value.
    - Applies available product discounts.
    - Calculates the final payable amount.
    - Generates an order summary.
    - Saves the order to 'data/orders.json'.
    - Clears the cart after successful payment.

    Returns:
        dict:
            Contains:
            - order_id
            - total_amount
            - total_discount
            - final_amount
            - purchased_items
            - order_timestamp

    Notes:
    - This is a simulated checkout process.
    - No real payment gateway is used.
    - Cart is automatically cleared after successful checkout.
    """

    cart = get_cart()

    if not cart["items"]:
        return {
            "message": "Your cart is empty."
        }

    total_amount = 0
    total_discount = 0
    purchased_items = []

    for item in cart["items"]:

        product = get_product_details(item["product_id"])

        quantity = item["quantity"]

        original_price = product.get(
            "original_price",
            product["price"]
        )

        selling_price = product["price"]

        subtotal = original_price * quantity
        discounted_subtotal = selling_price * quantity

        discount = subtotal - discounted_subtotal

        total_amount += subtotal
        total_discount += discount

        purchased_items.append({
            "product_id": product["id"],
            "name": product["name"],
            "quantity": quantity,
            "price": selling_price,
            "subtotal": discounted_subtotal
        })

    final_amount = total_amount - total_discount

    order = {
        "order_id": f"ORD-{int(datetime.now().timestamp())}",
        "timestamp": datetime.now().isoformat(),
        "total_amount": total_amount,
        "total_discount": total_discount,
        "final_amount": final_amount,
        "items": purchased_items
    }

    try:
        with open("data/orders.json", "r") as f:
            orders = json.load(f)
    except FileNotFoundError:
        orders = []

    orders.append(order)

    with open("data/orders.json", "w") as f:
        json.dump(orders, f, indent=2)

    clear_cart()

    return order