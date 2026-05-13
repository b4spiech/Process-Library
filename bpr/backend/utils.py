from datetime import date
from typing import Optional
from dateutil.relativedelta import relativedelta
from models import ReviewFrequency


FREQUENCY_DELTAS = {
    ReviewFrequency.monthly: relativedelta(months=1),
    ReviewFrequency.quarterly: relativedelta(months=3),
    ReviewFrequency.annually: relativedelta(years=1),
}


def compute_next_review_date(
    last_review_date: Optional[date],
    frequency: Optional[ReviewFrequency],
) -> Optional[date]:
    if last_review_date is None or frequency is None:
        return None
    delta = FREQUENCY_DELTAS.get(frequency)
    if delta is None:
        return None
    return last_review_date + delta
