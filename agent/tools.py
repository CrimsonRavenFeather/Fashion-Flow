import json 
from util.embedding import create_product_embeddings, build_similarity_matrix
from util.recommedation import get_similar_products
from util.filter import create_merged_item_data 
import numpy as np


def treasure_location():
    '''
    This function know the treasure location
    '''
    message = "The treasure is under the oak tree"
    return message

def treasure_details():
    '''
    This function knows the treasure details
    '''

    return "The treasure is the obsidian sword that can cut through space and time"

import json


def get_user_profile():
    """
    Retrieve the currently stored user profile.

    Use this tool when user profile information is needed to
    personalize shopping recommendations, enforce budget constraints,
    understand style preferences, or provide user-specific assistance.

    Typical use cases:
    - Recommend products based on the user's preferences.
    - Check the user's budget before suggesting items.
    - Personalize responses using age group, gender, or style.
    - Review the user's shopping profile.
    - Access user details for recommendation or discount logic.

    The profile is loaded from 'data/user.json'.

    Returns:
        dict:
            The complete user profile.

            Example:
            {
                "user_id": "usr-20260617094214",
                "name": "Aisha",
                "age": 28,
                "age_group": "25-34",
                "gender": "female",
                "budget": {
                    "total": 20000,
                    "per_item_max": 8000
                },
                "style_preferences": {
                    "categories": ["ethnic", "casual"]
                }
            }

        dict:
            {"error": "User profile not found"}
            if the profile file does not exist.
    """

    try:
        with open("data/user.json", "r") as f:
            return json.load(f)

    except FileNotFoundError:
        return {"error": "User profile not found"}

def collabotative_filttering(k=10):
    """
    Generate item-to-item product similarity recommendations and store
    the top-k most similar products for each item.

    Workflow:
    1. Merge catalogue and behavioral data.
    2. Generate product embeddings.
    3. Compute cosine similarity between products.
    4. For each product, find the top-k most similar products.
    5. Save recommendations to 'filter/item_relativity.json'.

    Output Format:
    {
        "product-001": [
            {
                "product_id": "product-023",
                "score": 0.91
            },
            {
                "product_id": "product-044",
                "score": 0.87
            }
        ]
    }

    Args:
        k (int):
            Number of similar products to store per product.

    Returns:
        str:
            Status message indicating successful completion.
    """

    create_merged_item_data()

    product_ids, embeddings = create_product_embeddings(
        "filter/item_merged.json"
    )

    similarity_matrix = build_similarity_matrix(embeddings)

    recommendations = {}

    for i, pid in enumerate(product_ids):

        scores = similarity_matrix[i]

        top_indices = np.argsort(scores)[::-1]

        recommendations[pid] = []

        for idx in top_indices:
            if idx == i:
                continue

            recommendations[pid].append({
                "product_id": product_ids[idx],
                "score": float(scores[idx])
            })

            if len(recommendations[pid]) >= k:
                break

    with open("filter/item_relativity.json", "w") as f:
        json.dump(recommendations, f, indent=2)

    return "Item similarity analysis completed successfully."
def get_similar_products(product_id: str, k: int = 10):
    """
    Retrieve products similar to a given product.

    Use this tool when a user wants recommendations related to a
    specific product.

    Typical user queries:
        - Show similar products
        - Recommend products like this
        - Customers who viewed this also liked
        - Find alternatives to this product
        - Show related items

    Args:
        product_id: Unique identifier of the product.
        k: Maximum number of similar products to return.

    Returns:
        A list of similar products sorted by similarity score.
    """
    
    with open("filter/item_relativity.json", "r") as f:
        recommendations = json.load(f)

    return recommendations.get(product_id, [])[:k]
def get_product_details(product_id):
    """
    Retrieve detailed information about a specific product from the catalogue.

    Use this tool when the user wants details about a particular product
    identified by its product ID.

    Input:
        product_id: Unique product identifier (e.g. "product-025").

    Returns:
        A dictionary containing customer-facing product information such as
        name, brand, category, price, discount, available sizes, colors,
        ratings, stock status, and image URL.

    Returns an error dictionary if the product cannot be found.
    """

    with open("data/catalogue.json", "r", encoding="utf-8") as f:
        catalogue = json.load(f)

    for product in catalogue.get("items", []):
        if product["id"] == product_id:
            return {
                "id": product["id"],
                "name": product["name"],
                "brand": product["brand"],
                "category": product["category"],
                "sub_category": product["sub_category"],
                "price": product["price"],
                "original_price": product["original_price"],
                "discount_percent": product["discount_percent"],
                "colors": product["colors"],
                "sizes_available": product["sizes_available"],
                "fabric": product["fabric"],
                "occasion": product["occasion"],
                "rating": product["rating"],
                "review_count": product["review_count"],
                "in_stock": product["in_stock"],
                "image_url": product["image_url"]
            }

    return {"error": f"Product '{product_id}' not found"}

import json
from collections import Counter

def get_top_viewed_products(user_id, limit=10):
    """
    Return the user's most viewed products.

    Args:
        user_id (str): User identifier.
        limit (int): Number of products to return.

    Returns:
        list[dict]:
        [
            {
                "product_id": "product-001",
                "view_count": 7
            },
            {
                "product_id": "product-025",
                "view_count": 5
            }
        ]
    """

    with open("data/interactions.json", "r") as f:
        activities = json.load(f)

    views = [
        activity["product_id"]
        for activity in activities
        if activity["user_id"] == user_id
        and activity["action"] == "view"
    ]

    counts = Counter(views)

    return [
        {
            "product_id": product_id,
            "view_count": count
        }
        for product_id, count in counts.most_common(limit)
    ]