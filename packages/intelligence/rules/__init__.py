"""Deterministic rules parsers. Each returns matches with spans in the original text."""

from .amounts import AmountMatch, parse_amounts
from .dates import DateMatch, parse_dates
from .payment import PaymentMatch, parse_payment_phrases
from .penalty import PenaltyMatch, parse_penalty_phrases
from .percent import PercentMatch, parse_percentages
from .quantities import QuantityMatch, parse_quantities

PARSERS = frozenset({"amounts", "quantities", "dates", "percent", "payment", "penalty"})

__all__ = [
    "PARSERS",
    "AmountMatch",
    "DateMatch",
    "PaymentMatch",
    "PenaltyMatch",
    "PercentMatch",
    "QuantityMatch",
    "parse_amounts",
    "parse_dates",
    "parse_payment_phrases",
    "parse_penalty_phrases",
    "parse_percentages",
    "parse_quantities",
]
