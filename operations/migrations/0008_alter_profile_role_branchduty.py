# Generated for branch duty roster and general-manager role.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("operations", "0007_operationaltask_staff_instructions_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="role",
            field=models.CharField(
                choices=[
                    ("ADMIN", "Admin"),
                    ("GENERAL_MANAGER", "General manager"),
                    ("MANAGER", "Manager"),
                    ("EMPLOYEE", "Employee"),
                ],
                default="EMPLOYEE",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="BranchDuty",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField()),
                ("status", models.CharField(choices=[("WORK", "Working"), ("LEAVE", "On leave")], default="WORK", max_length=10)),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="operations.branch")),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="roster_changes", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="branch_duties", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["date", "user__username"],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "date"), name="one_branch_duty_per_person_day"),
                    models.CheckConstraint(
                        condition=(models.Q(status="WORK", branch__isnull=False) | models.Q(status="LEAVE", branch__isnull=True)),
                        name="valid_branch_duty_status_branch",
                    ),
                ],
            },
        ),
    ]
