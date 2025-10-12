from django.apps import AppConfig
from django.db.models.signals import post_migrate

def create_default_groups(sender, **kwargs):
    from django.contrib.auth.models import Group
    Group.objects.get_or_create(name='Student')
    Group.objects.get_or_create(name='Administrator')

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'

    def ready(self):
        post_migrate.connect(create_default_groups, sender=self)