# ── STEP 1: Create Product Embeddings ──────────────────────

import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import OneHotEncoder, MultiLabelBinarizer, MinMaxScaler

def create_product_embeddings(data):
    with open(data, "r") as f:
        data = json.load(f)

    product_ids = []
    products = []

    for product_id, item in data.items():
        product = item["product"][0] if item["product"] else {}
        views = item.get("views", [])

        total_views = sum(v.get("view_count", 0) for v in views)
        wishlist_count = sum(int(v.get("wishlist", False)) for v in views)
        cart_count = sum(int(v.get("cart_added", False)) for v in views)
        purchase_count = sum(int(v.get("purchased", False)) for v in views)

        avg_engagement = (
            sum(v.get("engagement_score", 0) for v in views) / len(views)
            if views else 0
        )

        flattened = {
            **product,
            "total_views": total_views,
            "wishlist_count": wishlist_count,
            "cart_count": cart_count,
            "purchase_count": purchase_count,
            "avg_engagement": avg_engagement,
        }

        product_ids.append(product_id)
        products.append(flattened)

    # ------------------------------
    # CATEGORICAL FEATURES
    # ------------------------------
    cat_features = [
        [
            p.get("category", ""),
            p.get("sub_category", ""),
            p.get("brand", ""),
            p.get("gender", ""),
            p.get("fabric", ""),
        ]
        for p in products
    ]

    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    cat_matrix = ohe.fit_transform(cat_features)

    # ------------------------------
    # MULTI-VALUE FEATURES
    # ------------------------------
    def encode_multilabel(field):
        mlb = MultiLabelBinarizer()
        return mlb.fit_transform(
            [p.get(field, []) for p in products]
        )

    colors_matrix = encode_multilabel("colors")
    age_matrix = encode_multilabel("age_group")
    trend_matrix = encode_multilabel("trend_tags")
    occasion_matrix = encode_multilabel("occasion")
    size_matrix = encode_multilabel("sizes_available")

    # ------------------------------
    # NUMERIC FEATURES
    # ------------------------------
    numeric_features = np.array([
        [
            p.get("price", 0),
            p.get("original_price", 0),
            p.get("discount_percent", 0),
            p.get("rating", 0),
            p.get("review_count", 0),
            p.get("value_score", 0),
            int(p.get("in_stock", False)),
            p.get("total_views", 0),
            p.get("wishlist_count", 0),
            p.get("cart_count", 0),
            p.get("purchase_count", 0),
            p.get("avg_engagement", 0),
        ]
        for p in products
    ])

    scaler = MinMaxScaler()
    numeric_matrix = scaler.fit_transform(numeric_features)

    # ------------------------------
    # FINAL EMBEDDING
    # ------------------------------
    embeddings = np.hstack([
        cat_matrix,
        colors_matrix,
        age_matrix,
        trend_matrix,
        occasion_matrix,
        size_matrix,
        numeric_matrix
    ])
 
    return product_ids, embeddings


def build_similarity_matrix(embeddings):
    similarity = cosine_similarity(embeddings)
    return similarity

    
