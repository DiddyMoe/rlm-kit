"""Relevance scoring for search results.

Implements term frequency-based scoring for efficient local IDE search.
"""

import re
from collections import Counter
from typing import Any


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text)


def _normalize_terms(query: str, text: str) -> tuple[str, str, list[str], Counter[str], int]:
    query_lower = query.lower()
    text_lower = text.lower()
    query_terms = _tokenize(query_lower)
    text_words = _tokenize(text_lower)
    text_word_counts: Counter[str] = Counter(text_words)
    return query_lower, text_lower, query_terms, text_word_counts, len(text_words)


def _compute_score(
    query_terms: list[str], text_word_counts: Counter[str], word_count: int
) -> float:
    if word_count == 0:
        return 0.0

    total_score = 0.0
    matched_terms = 0
    for term in query_terms:
        if term not in text_word_counts:
            continue

        term_freq = text_word_counts[term] / word_count
        total_score += min(term_freq * 10.0, 1.0)
        matched_terms += 1

    if matched_terms == 0:
        return 0.0

    return total_score / len(query_terms)


def _apply_phrase_boost(base_score: float, query_lower: str, text_lower: str) -> float:
    if query_lower in text_lower:
        return min(base_score + 0.3, 1.0)
    return base_score


def _apply_start_word_boost(base_score: float, query_terms: list[str], text_lower: str) -> float:
    text_stripped = text_lower.strip()
    if not text_stripped:
        return base_score

    first_words = text_stripped.split()[:3]
    if any(term in first_words for term in query_terms):
        return min(base_score + 0.2, 1.0)

    return base_score


def calculate_term_frequency_score(query: str, text: str) -> float:
    """
    Calculate term frequency-based relevance score.

    Args:
        query: Search query string
        text: Text to score against

    Returns:
        Relevance score between 0.0 and 1.0
    """
    if not query or not text:
        return 0.0

    query_lower, text_lower, query_terms, text_word_counts, word_count = _normalize_terms(
        query, text
    )
    if not query_terms:
        return 0.5 if query_lower in text_lower else 0.0

    base_score = _compute_score(query_terms, text_word_counts, word_count)
    if base_score == 0.0:
        return 0.0

    base_score = _apply_phrase_boost(base_score, query_lower, text_lower)
    base_score = _apply_start_word_boost(base_score, query_terms, text_lower)

    return min(base_score, 1.0)


def score_search_results(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Score and sort search results by relevance.

    Args:
        query: Search query
        results: List of search result dictionaries with 'file_path', 'start_line', etc.

    Returns:
        Sorted list of results with relevance_score updated
    """
    # Score each result
    for result in results:
        # Get the line text if available (for better scoring)
        # For now, we'll use a simple approach based on file path and line number
        # In a full implementation, we'd read the actual line content
        file_path = result.get("file_path", "")

        # Simple scoring based on file path match
        path_score = calculate_term_frequency_score(query, file_path)

        # If we have snippet or line content, use that for better scoring
        snippet = result.get("snippet", "")
        if snippet:
            snippet_score = calculate_term_frequency_score(query, snippet)
            # Combine path and snippet scores
            result["relevance_score"] = max(path_score, snippet_score)
        else:
            result["relevance_score"] = path_score

    # Sort by relevance score (descending)
    results.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

    return results


def score_line_match(query: str, line: str) -> float:
    """
    Calculate relevance score for a single line match.

    Args:
        query: Search query
        line: Line of text to score

    Returns:
        Relevance score between 0.0 and 1.0
    """
    return calculate_term_frequency_score(query, line)
