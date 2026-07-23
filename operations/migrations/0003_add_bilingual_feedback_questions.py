from django.db import migrations


QUESTIONS = [
    (
        10,
        "✨ അന്തിമ ഫലത്തിൽ നിങ്ങൾ എത്രത്തോളം സംതൃപ്തരാണ്?\n"
        "How satisfied are you with the final result?",
    ),
    (
        20,
        "🧑‍💼 ജീവനക്കാരൻ നിങ്ങളുടെ സേവനം എത്രത്തോളം പ്രൊഫഷണലായി കൈകാര്യം ചെയ്തു?\n"
        "How professionally did the employee handle your service?",
    ),
    (
        30,
        "🧼 നിങ്ങളുടെ അനുഭവം എത്രത്തോളം സുഖകരവും വൃത്തിയുള്ളതുമായിരുന്നു?\n"
        "How comfortable and clean was your experience?",
    ),
    (
        40,
        "👂 ജീവനക്കാരൻ നിങ്ങളുടെ ആവശ്യങ്ങൾ എത്രത്തോളം മനസ്സിലാക്കി?\n"
        "How well did the employee understand your requirements?",
    ),
    (
        50,
        "🔄 നിങ്ങൾ വീണ്ടും ഞങ്ങളെ സന്ദർശിക്കാൻ എത്രത്തോളം സാധ്യതയുണ്ട്?\n"
        "How likely are you to visit us again?",
    ),
]


def add_questions(apps, schema_editor):
    FeedbackQuestion = apps.get_model("operations", "FeedbackQuestion")
    for sequence, text in QUESTIONS:
        FeedbackQuestion.objects.update_or_create(
            sequence=sequence,
            defaults={"text": text, "active": True},
        )


def deactivate_questions(apps, schema_editor):
    FeedbackQuestion = apps.get_model("operations", "FeedbackQuestion")
    FeedbackQuestion.objects.filter(
        sequence__in=[sequence for sequence, _ in QUESTIONS]
    ).update(active=False)


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0002_equipment_inventoryitem_operationaltask_subservice_and_more"),
    ]

    operations = [
        migrations.RunPython(add_questions, deactivate_questions),
    ]
