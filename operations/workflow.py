from .models import SubService, VisitTask


CONSULTATION_CODE = "SUB001"
SANITISATION_CODE = "SUB025"


def _task_type(sub_service_code):
    if sub_service_code == CONSULTATION_CODE:
        return "CONSULT", "BEFORE"
    if sub_service_code == SANITISATION_CODE:
        return "HYGIENE", "AFTER"
    return "SERVICE", "DURING"


def _append_sub_service_tasks(rows, visit_service, sub_service, start_sequence, required=True):
    task_type, phase = _task_type(sub_service.code)
    sequence = start_sequence
    for task in sub_service.tasks.filter(active=True).order_by("sequence", "id"):
        rows.append(
            VisitTask(
                visit_service=visit_service,
                source_operational_task=task,
                sequence=sequence,
                sub_service_name=sub_service.name,
                phase=phase,
                task_type=task_type,
                title=task.name,
                instructions=task.notes,
                active_labour_minutes=task.active_labour_minutes,
                passive_time_minutes=task.passive_time_minutes,
                required=required,
                can_skip=task.is_skippable,
                skip_reason_required=task.is_skippable,
            )
        )
        sequence += 10
    return sequence


def build_visit_tasks(visit):
    """Build one ordered execution plan for every service in a visit.

    Consultation is placed only on the first service and sanitisation only on
    the last service, even when each selected service maps those sub-services.
    """
    visit_services = list(visit.services.select_related("service").order_by("order_number", "id"))
    if not visit_services:
        return
    if VisitTask.objects.filter(visit_service__visit=visit).exclude(status="PENDING").exists():
        return

    VisitTask.objects.filter(visit_service__visit=visit).delete()
    rows = []
    consultation = SubService.objects.filter(code=CONSULTATION_CODE, active=True).first()
    sanitisation = SubService.objects.filter(code=SANITISATION_CODE, active=True).first()

    for index, visit_service in enumerate(visit_services):
        sequence = 10
        if index == 0 and consultation:
            sequence = _append_sub_service_tasks(rows, visit_service, consultation, sequence)

        details = (
            visit_service.service.service_details.filter(active=True, sub_service__active=True)
            .exclude(sub_service__code__in=[CONSULTATION_CODE, SANITISATION_CODE])
            .select_related("sub_service")
            .prefetch_related("sub_service__tasks")
            .order_by("sequence", "id")
        )
        for detail in details:
            sequence = _append_sub_service_tasks(
                rows,
                visit_service,
                detail.sub_service,
                sequence,
                required=detail.mandatory,
            )

        if index == len(visit_services) - 1 and sanitisation:
            sequence = _append_sub_service_tasks(rows, visit_service, sanitisation, sequence)

        # Existing CSV/demo services continue to work until workbook data is imported.
        if not any(row.visit_service_id == visit_service.id for row in rows):
            for legacy in visit_service.service.sop_tasks.filter(active=True):
                rows.append(
                    VisitTask(
                        visit_service=visit_service,
                        source_task=legacy,
                        sequence=legacy.sequence,
                        phase=legacy.phase,
                        task_type=legacy.task_type,
                        title=legacy.title,
                        instructions=legacy.instructions,
                        required=legacy.required,
                        can_skip=legacy.can_skip,
                        skip_reason_required=legacy.skip_reason_required,
                    )
                )

    VisitTask.objects.bulk_create(rows)


def task_resources(task, service):
    """Return service-specific inventory and shared equipment for a task."""
    inventory = task.inventory_requirements.filter(active=True, service=service).select_related("inventory")
    equipment = task.equipment_requirements.filter(active=True).select_related("equipment")
    return inventory, equipment
