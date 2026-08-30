from app.price_deviation import HISTORICAL_WINDOW_DAYS, MIN_PRIOR_OBSERVATIONS


PRESENTATION_CATEGORY_BY_REASON = {
    "insufficient_prior_history": "NOT_ENOUGH_HISTORY",
    "missing_normalized_price": "PRICE_NOT_COMPARABLE",
    "missing_price_evidence": "PRICE_NOT_COMPARABLE",
    "unsupported_unit": "PRICE_NOT_COMPARABLE",
    "unsupported_source": "PRICE_NOT_COMPARABLE",
    "service_line": "PRICE_NOT_COMPARABLE",
    "unresolved_multipack": "PRICE_NOT_COMPARABLE",
    "unresolved_product_identity": "PRODUCT_IDENTITY_UNCERTAIN",
    "non_positive_price_evidence": "EVIDENCE_NEEDS_REVIEW",
    "normalized_price_out_of_range": "EVIDENCE_NEEDS_REVIEW",
    "low_confidence": "EVIDENCE_NEEDS_REVIEW",
    "missing_store": "EVIDENCE_NEEDS_REVIEW",
    "invalid_date": "EVIDENCE_NEEDS_REVIEW",
    "invalid_date_or_ordering": "EVIDENCE_NEEDS_REVIEW",
    "arithmetic_mismatch": "EVIDENCE_NEEDS_REVIEW",
    "parser_contamination": "EVIDENCE_NEEDS_REVIEW",
    "ambiguous_measurement": "EVIDENCE_NEEDS_REVIEW",
    "blocked_price_diagnostic": "EVIDENCE_NEEDS_REVIEW",
}

PRESENTATION_COPY = {
    "NOT_ENOUGH_HISTORY": {
        "title": "Недостаточно истории цен",
        "explanation": (
            f"Для сравнения нужны {MIN_PRIOR_OBSERVATIONS} сопоставимых наблюдения "
            f"за предыдущие {HISTORICAL_WINDOW_DAYS} дней."
        ),
    },
    "PRICE_NOT_COMPARABLE": {
        "title": "Цена пока несопоставима",
        "explanation": (
            "Не удалось надёжно определить цену за кг, литр или штуку."
        ),
    },
    "PRODUCT_IDENTITY_UNCERTAIN": {
        "title": "История товара требует уточнения",
        "explanation": (
            "Покупки пока нельзя надёжно объединить в одну историю цен."
        ),
    },
    "EVIDENCE_NEEDS_REVIEW": {
        "title": "Данные требуют проверки",
        "explanation": (
            "Эту покупку пока нельзя безопасно использовать для сравнения цен."
        ),
    },
}


def build_price_evidence_presentation(evaluation):
    """Translate one fail-closed evaluator result into stable user-facing evidence."""
    if evaluation.get("status") != "INSUFFICIENT_HISTORY":
        return None

    reason = evaluation.get("reason")
    category = PRESENTATION_CATEGORY_BY_REASON.get(
        reason,
        "EVIDENCE_NEEDS_REVIEW",
    )
    copy = PRESENTATION_COPY[category]
    show_progress = category == "NOT_ENOUGH_HISTORY"
    prior_count = (
        int(evaluation.get("eligible_prior_observation_count") or 0)
        if show_progress
        else None
    )
    remaining_count = (
        max(0, MIN_PRIOR_OBSERVATIONS - prior_count)
        if show_progress
        else None
    )

    return {
        "category": category,
        "title": copy["title"],
        "explanation": copy["explanation"],
        "eligible_prior_count": prior_count,
        "required_prior_count": MIN_PRIOR_OBSERVATIONS,
        "remaining_count": remaining_count,
        "show_progress": show_progress,
        "progress_text": (
            f"Сопоставимых наблюдений: {prior_count} "
            f"из {MIN_PRIOR_OBSERVATIONS}."
            if show_progress
            else None
        ),
    }
