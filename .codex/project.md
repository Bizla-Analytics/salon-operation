# SalonOps context for Codex

SalonOps tracks whether every salon standard operating procedure is completed and captures labour, passive, equipment, and utility time for later analysis.

Master-data hierarchy: Service -> ServiceDetail -> SubService -> OperationalTask -> Inventory/Equipment requirements.

Execution hierarchy: Visit -> ordered VisitService rows -> VisitTask snapshots. Visit tasks are snapshots so later master-data imports must not rewrite work already performed.

Business rules:

- Managers may combine multiple services for one customer and define their execution order.
- Employees follow that order.
- Consultation (`SUB001`) occurs once, first.
- Sanitisation (`SUB025`) occurs once, last.
- Workbook and customer data stay outside Git.
