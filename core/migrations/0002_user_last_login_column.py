from django.db import connection, migrations


def add_user_last_login(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'user'
              AND COLUMN_NAME = 'last_login'
            """
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE user ADD COLUMN last_login DATETIME NULL")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_user_last_login, migrations.RunPython.noop),
    ]
