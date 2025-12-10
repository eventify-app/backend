from celery import shared_task
from django.db.models.query_utils import Q
from django.utils import timezone
from django.core.mail import send_mail
from .models import EventReminder, StudentEvent
from .utils import reminder_datetime


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def send_event_reminder(self, reminder_id):
    try:
        r = (
            EventReminder.objects
            .select_for_update(skip_locked=True)
            .select_related("event", "user")
            .get(pk=reminder_id)
        )
    except EventReminder.DoesNotExist:
        return "not_found"

    if r.sent_at:
        return "already_sent"

    if timezone.now() < r.scheduled_for:
        return "too_early"

    if not getattr(getattr(r.user, "notif_prefs", None), "email_enabled", True):
        r.status = "skipped"
        r.sent_at = timezone.now()
        r.save(update_fields=["status", "sent_at"])
        return "skipped"

    ev = r.event
    subject = f"Recordatorio: {ev.title} empieza pronto"
    body = (
        f"Hola {r.user.first_name or r.user.username},\n\n"
        f"Tu evento '{ev.title}' será el {ev.start_date} a las {ev.start_time} en {ev.place}.\n"
        f"¡Nos vemos allí!\n\nEventify"
    )
    send_mail(subject, body, None, [r.user.email], fail_silently=False)
    r.status = "sent"
    r.sent_at = timezone.now()
    r.save(update_fields=["status", "sent_at"])
    return "sent"


@shared_task
def scan_and_schedule_reminders():
    now = timezone.now()
    window_end = now + timezone.timedelta(minutes=10)

    se_qs = (StudentEvent.objects
             .select_related("event", "student")
             .filter(event__disabled_at__isnull=True)
             .filter(Q(event__start_date__gte=timezone.localdate()))
             .filter(Q(student__notif_prefs__email_enabled=True) | Q(student__notif_prefs__isnull=True))
             )

    created = 0
    for se in se_qs:
        user, ev = se.student, se.event
        sched_for = reminder_datetime(ev, user)

        if sched_for < now - timezone.timedelta(minutes=1) or sched_for > window_end:
            continue

        r, _  = EventReminder.objects.get_or_create(event=ev, user=user, kind="pre", defaults={"scheduled_for": sched_for})

        if r.scheduled_for != sched_for and not r.sent_at:
            r.scheduled_for = sched_for
            r.save(update_fields=["scheduled_for"])

        if not r.sent_at and r.scheduled_for <= now:
            send_event_reminder.delay(r.id)
            created += 1

    return created