from django.db import connection, migrations


def add_beach_bar_image_url(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'beach_bar'
              AND COLUMN_NAME = 'image_url'
            """
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "ALTER TABLE beach_bar ADD COLUMN image_url VARCHAR(512) NULL"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_user_last_login_column"),
    ]

    operations = [
        migrations.RunPython(add_beach_bar_image_url, migrations.RunPython.noop),
    ]
