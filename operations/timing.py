from .models import TaskTimingSegment


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
