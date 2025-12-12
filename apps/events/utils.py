from datetime import datetime, timedelta
from django.utils import timezone

def combine(dt_date, dt_time):
    """
    Combine date and time into an aware datetime object.
    """
    if dt_date is None or dt_time is None:
        return None
    naive = datetime.combine(dt_date, dt_time)
    return timezone.make_aware(naive)


def compute_status(event):
    """
    Compute the status of an event: finished, ongoing, or upcoming.
    """
    now = timezone.now()
    start = combine(event.start_date, event.start_time)
    end = combine(event.end_date, event.end_time)

    is_finished = bool(end and now > end)
    is_ongoing = bool(start and end and start <= now <= end)
    is_upcoming = bool(start and now < start)
    return is_finished, is_ongoing, is_upcoming


def reminder_datetime(event, user):
    """
    Compute the reminder datetime for an event based on user preferences.
    """
    hours = getattr(getattr(user, "notif_prefs", None), "hours_before", 24)
    return combine(event.start_date, event.start_time) - timedelta(hours=hours)