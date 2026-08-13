from django.apps import AppConfig

class MoviesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'movies'

    def ready(self):
        try:
            from django.core.management import call_command
            from django.db import connection
            tables = connection.introspection.table_names()
            if 'django_session' not in tables:
                call_command('migrate', interactive=False)
        except Exception:
            pass

