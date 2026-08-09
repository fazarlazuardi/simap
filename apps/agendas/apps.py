from django.apps import AppConfig
from django.db import connection



class AgendasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agendas'

    def ready(self):
        pass


