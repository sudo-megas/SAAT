from saat.models import Watch


def fuzzy_match(query: str, text: str) -> bool:
    """True if every character of query appears in text in order, with gaps
    allowed — a classic fuzzy-finder subsequence match. No external fuzzy-
    matching library is in budget (SPEC.md's three-dependency rule), and this
    is the standard dependency-free reading of "fuzzy"."""
    if not query:
        return True
    it = iter(text.casefold())
    return all(ch in it for ch in query.casefold())


def search_matches(watch: Watch, query: str) -> bool:
    """SPEC.md §5.1/§7: fuzzy search across brand, model, reference, caliber
    and tags. Matched per-field, not against the fields concatenated — a
    concatenated search would let a query borrow letters across field
    boundaries (e.g. "sk" matching brand="S..." + model="...k...")."""
    if not query.strip():
        return True
    fields = [watch.brand, watch.model, watch.reference, watch.movement.caliber, *watch.tags]
    return any(fuzzy_match(query, field) for field in fields if field)
