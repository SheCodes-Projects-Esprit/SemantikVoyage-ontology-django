from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("city", "0001_initial"),
    ]

    operations = [
        # Rename existing columns to preserve data
        migrations.RenameField(
            model_name="capitalcity",
            old_name="city_id",
            new_name="name",
        ),
        migrations.RenameField(
            model_name="metropolitancity",
            old_name="city_id",
            new_name="name",
        ),
        migrations.RenameField(
            model_name="touristiccity",
            old_name="city_id",
            new_name="name",
        ),
        migrations.RenameField(
            model_name="industrialcity",
            old_name="city_id",
            new_name="name",
        ),

        # Update field definitions to match models.py
        migrations.AlterField(
            model_name="capitalcity",
            name="name",
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name="metropolitancity",
            name="name",
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name="touristiccity",
            name="name",
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name="industrialcity",
            name="name",
            field=models.CharField(max_length=100, unique=True),
        ),
    ]


