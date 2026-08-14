from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("operations", "0005_revise_malayalam_feedback_questions"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="visitservice",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="visitservice",
            name="verified_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="verified_services",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="visitservice",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="visitservice",
            name="cancelled_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cancelled_services",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="visitservice",
            name="cancellation_reason",
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name="visitservice",
            name="replaces",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="replacements",
                to="operations.visitservice",
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="status",
            field=models.CharField(
                choices=[("DRAFT", "Draft"), ("COMPLETED", "Completed"), ("VOID", "Void")],
                default="COMPLETED",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="visittask",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("IN_PROGRESS", "In progress"),
                    ("COMPLETED", "Completed"),
                    ("SKIPPED", "Skipped"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
