import numpy as np
from sklearn.neighbors import NearestNeighbors

def get_similar_products(product_id, product_ids, similarity, k=5):
    idx = product_ids.index(product_id)

    scores = similarity[idx]

    top_indices = np.argsort(scores)[::-1][1:k+1]

    return [
        (product_ids[i], float(scores[i]))
        for i in top_indices
    ]


def recommend_products(product_id, product_ids, embeddings, k=5):
    nn = NearestNeighbors(
        metric="cosine",
        algorithm="brute"
    )

    nn.fit(embeddings)

    idx = product_ids.index(product_id)

    distances, indices = nn.kneighbors(
        embeddings[idx].reshape(1, -1),
        n_neighbors=k + 1
    )

    recommendations = []

    for dist, i in zip(distances[0][1:], indices[0][1:]):
        recommendations.append({
            "product_id": product_ids[i],
            "similarity": 1 - dist
        })

    return recommendations