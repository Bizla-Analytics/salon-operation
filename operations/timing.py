from .models import TaskTimingSegment
from django.utils import timezone


def format_duration(seconds):
    minutes = int((seconds / 60) + 0.5)
    hours, minutes = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes or not parts:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return ' '.join(parts)


def compact_duration(seconds):
    minutes = int((seconds / 60) + 0.5)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f'{hours}h {minutes}m' if minutes else f'{hours}h'
    return f'{minutes}m'


def add_timing_summary(obj, tasks, now=None):
    """Total task time is hands-on plus waiting, not visit wall-clock duration."""
    now = now or timezone.now()
    working = waiting = 0
    for task in tasks:
        if task.task_type in ['HYGIENE', 'CONSULT'] or task.status == 'CANCELLED':
            continue
        segments = list(task.timing_segments.all())
        if segments:
            for segment in segments:
                seconds = max(((segment.ended_at or now) - segment.started_at).total_seconds(), 0)
                if segment.kind == 'ACTIVE':
                    working += seconds
                else:
                    waiting += seconds
        elif task.started_at and task.status in ['COMPLETED', 'IN_PROGRESS', 'WAITING']:
            # Legacy tasks have no separated waiting intervals.
            working += max(((task.completed_at or now) - task.started_at).total_seconds(), 0)
    obj.working_seconds = int(working)
    obj.waiting_seconds = int(waiting)
    obj.total_seconds = int(working + waiting)
    obj.working_time = format_duration(working)
    obj.waiting_time = format_duration(waiting)
    obj.total_task_time = format_duration(working + waiting)
    obj.working_time_short = compact_duration(working)
    obj.waiting_time_short = compact_duration(waiting)
    obj.total_time_short = compact_duration(working + waiting)
    return obj


def close_segment(task, now):
    """Call while holding the employee/task transaction locks."""
    task.timing_segments.filter(ended_at__isnull=True).update(ended_at=now)


def start_segment(task, kind, now):
    close_segment(task, now)
    TaskTimingSegment.objects.create(task=task, kind=kind, started_at=now)


def adopt_legacy_active_segment(task):
    # Existing in-progress snapshots are not rebuilt. Account for the active
    # interval that predates deployment only when the employee next acts.
    if task.status == "IN_PROGRESS" and task.started_at and not task.timing_segments.exists():
        TaskTimingSegment.objects.create(task=task, kind="ACTIVE", started_at=task.started_at)
