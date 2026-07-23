from django.db import migrations


QUESTIONS = [
    (
        10,
        "അന്തിമ ഫലത്തിൽ നിങ്ങൾ എത്രത്തോളം തൃപ്തനാണ്?\n"
        "How satisfied are you with the final result?",
    ),
    (
        20,
        "ഞങ്ങളുടെ ജീവനക്കാരൻ എത്രത്തോളം പ്രൊഫഷണലായാണ് സേവനം നൽകിയത്?\n"
        "How professionally did the employee handle your service?",
    ),
    (
        30,
        "ഞങ്ങളുടെ കേന്ദ്രത്തിലെ ശുചിത്വവും അന്തരീക്ഷവും നിങ്ങൾക്ക് എത്രത്തോളം സുഖകരമായിരുന്നു?\n"
        "How comfortable and clean was your experience?",
    ),
    (
        40,
        "നിങ്ങളുടെ ആവശ്യങ്ങൾ ഞങ്ങളുടെ ജീവനക്കാരൻ എത്രത്തോളം കൃത്യമായി മനസ്സിലാക്കി?\n"
        "How well did the employee understand your requirements?",
    ),
    (
        50,
        "വീണ്ടും ഞങ്ങളെ സന്ദർശിക്കാൻ നിങ്ങൾക്ക് എത്രത്തോളം സാധ്യതയുണ്ട്?\n"
        "How likely are you to visit us again?",
    ),
]


def revise_questions(apps, schema_editor):
    FeedbackQuestion = apps.get_model("operations", "FeedbackQuestion")
    for sequence, text in QUESTIONS:
        FeedbackQuestion.objects.update_or_create(
            sequence=sequence,
            defaults={"text": text, "active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0004_remove_feedback_question_emojis"),
    ]

    operations = [
        migrations.RunPython(revise_questions, migrations.RunPython.noop),
    ]
