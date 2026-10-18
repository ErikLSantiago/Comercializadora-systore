"""Pure date logic, shared by the service and its regression checks."""
from datetime import datetime, time, timedelta

import pytz


SCOPES = {'date', 'overdue', 'all', 'undated', 'next_days', 'upcoming'}


def local_day_bounds(day, timezone):
    zone = pytz.timezone(timezone)
    # Localize each midnight separately, including days crossing a DST change.
    start = zone.localize(datetime.combine(day, time.min))
    end = zone.localize(datetime.combine(day + timedelta(days=1), time.min))
    return (start.astimezone(pytz.UTC).replace(tzinfo=None),
            end.astimezone(pytz.UTC).replace(tzinfo=None))


def local_date(value, timezone):
    if not value:
        return None
    return pytz.UTC.localize(value).astimezone(pytz.timezone(timezone)).date()


def matches_scope(value, scope, selected_day, today, timezone):
    if scope == 'all':
        return True
    day = local_date(value, timezone)
    if scope == 'undated':
        return day is None
    if day is None:
        return False
    if scope == 'upcoming':
        return day > today
    if scope == 'next_days':
        return today <= day <= today + timedelta(days=1)
    if scope == 'overdue':
        return day < today
    return day == selected_day
