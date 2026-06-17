
import json
from collections import defaultdict
import random

def get_random_products():
    """
    Retrieve a random sample of products from the catalogue for browsing.

    This tool is intended for use by a shopping assistant when a user
    wants to explore the available catalogue without applying specific
    filters or preferences.

    Typical user queries include:
    - "Show me the catalogue"
    - "Browse products"
    - "What products do you have?"
    - "Show me some items"
    - "Show me what's available"

    The tool:
    - Loads products from 'data/catalogue.json'.
    - Randomly selects up to 10 products.
    - Returns only customer-facing product information suitable for
      display in a shopping interface.
    - Excludes internal metadata and recommendation features.

    Returns:
        list[dict]: A list containing up to 10 randomly selected products.
        Each product includes:
            - id: Unique product identifier
            - name: Product name
            - brand: Brand name
            - category: Product category
            - price: Current selling price
            - discount_percent: Available discount percentage
            - colors: Available colors
            - rating: Average customer rating
            - in_stock: Product availability status
            - image_url: Product image URL

    Notes:
        - Products are selected randomly on each invocation to provide
          variety while browsing.
        - This tool is designed for catalogue discovery and should not
          be used when the user requests personalized recommendations,
          product comparisons, or category-specific searches.
    """
    
    with open("data/catalogue.json", "r", encoding="utf-8") as f:
        catalogue = json.load(f)

    items = catalogue.get("items", [])

    sample_size = min(10, len(items))
    selected_products = random.sample(items, sample_size)

    return [
        {
            "id": product["id"],
            "name": product["name"],
            "brand": product["brand"],
            "category": product["category"],
            "price": product["price"],
            "discount_percent": product["discount_percent"],
            "colors": product["colors"],
            "rating": product["rating"],
            "in_stock": product["in_stock"],
            "image_url": product["image_url"],
        }
        for product in selected_products
    ]    

def format_product(product):
    return {
        "id": product["id"],
        "name": product["name"],
        "brand": product["brand"],
        "category": product["category"],
        "price": product["price"],
        "discount_percent": product["discount_percent"],
        "rating": product["rating"],
        "colors": product["colors"],
        "in_stock": product["in_stock"],
        "image_url": product["image_url"]
    }

def filter_products():
    """
    Retrieve products from the catalogue and return the most relevant items
    for the current user.

    Use this tool whenever the user wants to discover, browse, or receive
    recommendations for products available in the catalogue.

    Typical user queries:
    - "Show me some products"
    - "Show me the catalogue"
    - "What products do you have?"
    - "Browse items"
    - "Recommend something for me"
    - "Based on my profile, show me some items"
    - "What would suit me?"
    - "Show products I might like"
    - "Suggest some products"

    The tool:
    - Reads the user's profile from 'data/user.json'.
    - Reads the product catalogue from 'data/catalogue.json'.
    - Evaluates products based on profile compatibility, including:
        * category preferences
        * favorite colors
        * favorite fabrics
        * preferred occasions
        * age group
        * gender compatibility
        * budget constraints
        * product quality signals
    - Ranks products by relevance and returns the best matches.
    - Can be used for both general product discovery and personalized
    recommendations.

    Returns:
        dict:
        {
            "message": str,
            "products": list
        }

        message:
            A brief explanation of the results returned.

        products:
            A list of products containing only customer-facing information:
            - id
            - name
            - brand
            - category
            - price
            - discount_percent
            - colors
            - rating
            - in_stock
            - image_url

    Fallback Behavior:
    - If no products strongly match the user's profile, the tool returns
    alternative catalogue items that may still be relevant to the user.
    - Ensures that products are returned whenever possible, even when
    preference matching is limited.

    Notes:
    - Use this tool for product browsing, product discovery, and
    recommendation-related requests.
    - This is the primary catalogue exploration tool and can handle both
    generic browsing requests and profile-based recommendation requests.
    """
    with open("data/user.json", "r") as f:
        user = json.load(f)

    with open("data/catalogue.json", "r") as f:
        catalog = json.load(f)

    recommendations = []

    for item in catalog["items"]:
        # Hard constraints
        if not item.get("in_stock", False):
            continue

        if item["price"] > (
            user["budget"]["per_item_max"]
            * (1 + user["budget"]["flexibility_percent"] / 100)
        ):
            continue

        score = 0

        # Gender
        if item["gender"] in [user["gender"], "unisex"]:
            score += 2

        # Age Group
        if user["age_group"] in item.get("age_group", []):
            score += 2

        # Category Preference
        if item["category"] in user["style_preferences"]["categories"]:
            score += 4

        # Occasion Match
        occasion_overlap = len(
            set(item.get("occasion", []))
            & set(user["style_preferences"]["occasions"])
        )
        score += occasion_overlap * 2

        # Favorite Fabric
        if item.get("fabric") in user["style_preferences"]["favorite_fabrics"]:
            score += 3

        # Favorite Colors
        color_overlap = len(
            set(item.get("colors", []))
            & set(user["style_preferences"]["favorite_colors"])
        )
        score += color_overlap * 2

        # Trend Tags
        avoid_tags = set(
            tag.lower()
            for tag in user["style_preferences"]["avoid"]
        )

        item_tags = set(
            tag.lower()
            for tag in item.get("trend_tags", [])
        )

        if avoid_tags.intersection(item_tags):
            score -= 5

        # Quality Signals
        score += item.get("rating", 0)
        score += item.get("value_score", 0)

        recommendations.append({
            "score": score,
            "product": item
        })

    recommendations.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    recommendations = recommendations[:10]

    if not recommendations:
        return {
            "message": (
                "We couldn't find products that closely match your preferences. "
                "You might like these instead."
            ),
            "products": get_random_products()
        }

    return {
        "message": "Here are some products selected based on your preferences.",
        "products": [
            format_product(r["product"])
            for r in recommendations
        ]
    }

def create_merged_item_data():
    # Load catalogue
    with open("data/catalogue.json", "r") as f:
        catalogue = json.load(f)

    # Load views
    with open("data/views.json", "r") as f:
        views = json.load(f)

    item_details = defaultdict(list)
    item_views = defaultdict(list)

    # Process catalogue items
    for item in catalogue["items"]:
        item = item.copy()

        item_id = item.pop("id")
        item.pop("image_url", None)

        item_details[item_id].append(item)

    # Process view logs
    for view in views["behaviour_log"]:
        view = view.copy()

        item_id = view.pop("item_id")

        item_views[item_id].append(view)

    # Merge
    merged = {}

    for product_id in set(item_details) | set(item_views):
        merged[product_id] = {
            "product": item_details.get(product_id, []),
            "views": item_views.get(product_id, [])
        }

    # Save merged output
    with open("filter/item_merged.json", "w") as f:
        json.dump(merged, f, indent=2)

    print(f"Merged {len(merged)} products into filter/item_merged.json")
