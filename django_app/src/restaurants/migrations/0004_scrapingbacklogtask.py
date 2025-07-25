# Generated by Django 4.2.7 on 2025-07-23 15:12

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("restaurants", "0003_update_user_references"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScrapingBacklogTask",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "task_id",
                    models.CharField(db_index=True, max_length=255, unique=True),
                ),
                ("url", models.URLField()),
                ("restaurant_name", models.CharField(max_length=255)),
                (
                    "task_type",
                    models.CharField(
                        choices=[
                            ("text", "Text Scraping"),
                            ("images", "Image Scraping"),
                            ("comprehensive", "Comprehensive Scraping"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("priority", models.PositiveIntegerField(db_index=True, default=1)),
                ("max_retries", models.PositiveIntegerField(default=3)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error_messages", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_attempt", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "restaurant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="backlog_tasks",
                        to="restaurants.restaurant",
                    ),
                ),
            ],
            options={
                "ordering": ["-priority", "created_at"],
                "indexes": [
                    models.Index(
                        fields=["status", "priority", "created_at"],
                        name="restaurants_status_81a2ed_idx",
                    ),
                    models.Index(
                        fields=["task_type", "status"],
                        name="restaurants_task_ty_7fc730_idx",
                    ),
                    models.Index(
                        fields=["retry_count", "max_retries", "status"],
                        name="restaurants_retry_c_248a47_idx",
                    ),
                ],
            },
        ),
    ]
