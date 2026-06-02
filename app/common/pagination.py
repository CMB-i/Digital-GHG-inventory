def paginate_query(query, page=1, per_page=20):
    # TODO Phase 1: adapt to SQLAlchemy query objects once models exist.
    return {
        "items": query,
        "page": page,
        "per_page": per_page,
        "total": None,
    }
