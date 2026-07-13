from django.conf import settings
from django.db import connection, migrations, models
import django.db.models.deletion


def add_user_is_active(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'user'
              AND COLUMN_NAME = 'is_active'
            """
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "ALTER TABLE user ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1"
            )


def create_admin_action_log_if_needed(apps, schema_editor):
    """Create table with a FK type that matches whatever `user.id` is (signed/unsigned)."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'admin_action_log'
            """
        )
        if cursor.fetchone()[0] != 0:
            return

        cursor.execute(
            """
            SELECT COLUMN_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'user'
              AND COLUMN_NAME = 'id'
            """
        )
        row = cursor.fetchone()
        id_type = row[0] if row else "bigint"
        cursor.execute(
            f"""
            CREATE TABLE admin_action_log (
                id {id_type} NOT NULL AUTO_INCREMENT,
                admin_id {id_type} NOT NULL,
                action VARCHAR(64) NOT NULL,
                target_type VARCHAR(40) NOT NULL DEFAULT '',
                target_id BIGINT NULL,
                detail VARCHAR(512) NOT NULL DEFAULT '',
                created_at DATETIME(6) NOT NULL,
                PRIMARY KEY (id),
                KEY idx_admin_action_log_admin (admin_id),
                KEY idx_admin_action_log_action (action),
                KEY idx_admin_action_log_created (created_at),
                CONSTRAINT fk_admin_action_log_admin
                    FOREIGN KEY (admin_id) REFERENCES user (id)
                    ON DELETE RESTRICT ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_beachbar_image_url"),
    ]

    operations = [
        migrations.RunPython(add_user_is_active, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="user",
                    name="is_active",
                    field=models.BooleanField(default=True),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    create_admin_action_log_if_needed,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name="AdminActionLog",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("action", models.CharField(max_length=64)),
                        (
                            "target_type",
                            models.CharField(blank=True, default="", max_length=40),
                        ),
                        ("target_id", models.BigIntegerField(blank=True, null=True)),
                        (
                            "detail",
                            models.CharField(blank=True, default="", max_length=512),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "admin",
                            models.ForeignKey(
                                db_column="admin_id",
                                on_delete=django.db.models.deletion.RESTRICT,
                                related_name="admin_actions",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "admin_action_log",
                        "ordering": ("-created_at",),
                    },
                ),
            ],
        ),
    ]
