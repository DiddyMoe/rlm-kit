"""Relevance scoring for search results.

Implements term frequency-based scoring for efficient local IDE search.
"""

import re
from collections import Counter
from typing import Any


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

    # Normalize to lowercase for case-insensitive matching
    query_lower = query.lower()
    text_lower = text.lower()

    # Split query into terms (words)
    query_terms = re.findall(r"\w+", query_lower)
    if not query_terms:
        # If no word terms, check for exact substring match
        if query_lower in text_lower:
            return 0.5
        return 0.0

    # Count term frequencies in text
    text_words = re.findall(r"\w+", text_lower)
    text_word_counts = Counter(text_words)

    # Calculate term frequency scores
    total_score = 0.0
    matched_terms = 0

    for term in query_terms:
        if term in text_word_counts:
            # Term frequency: count of term / total words
            term_freq = text_word_counts[term] / len(text_words) if text_words else 0.0

            # Boost score if term appears multiple times
            term_score = min(term_freq * 10.0, 1.0)  # Cap at 1.0
            total_score += term_score
            matched_terms += 1

    # Normalize by number of query terms
    if matched_terms == 0:
        return 0.0

    base_score = total_score / len(query_terms)

    # Boost for exact phrase match
    if query_lower in text_lower:
        base_score = min(base_score + 0.3, 1.0)

    # Boost for query terms appearing at start of line
    text_stripped = text_lower.strip()
    if text_stripped:
        first_words = text_stripped.split()[:3]  # First 3 words
        if any(term in first_words for term in query_terms):
            base_score = min(base_score + 0.2, 1.0)

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
