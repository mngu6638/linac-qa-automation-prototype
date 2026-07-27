"""
Set or reset the Django admin password on a local SQLite database.

Useful for local demo resets when the demo admin password needs changing.
"""
from __future__ import annotations

import secrets
import string
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = 'Set admin password on the active database or a specified SQLite file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default='demo_admin',
            help='Username to reset (default: demo_admin)',
        )
        parser.add_argument(
            '--password',
            default='',
            help='New password. If omitted, a strong random password is generated.',
        )
        parser.add_argument(
            '--db-path',
            default='',
            help='Optional path to a local db.sqlite3 file. '
                 'Uses the project settings database when omitted.',
        )
        parser.add_argument(
            '--create-if-missing',
            action='store_true',
            help='Create the user as staff/superuser if it does not exist.',
        )

    def handle(self, *args, **options):
        username = (options.get('username') or 'demo_admin').strip()
        password = (options.get('password') or '').strip()
        db_path = (options.get('db_path') or '').strip()
        create_if_missing = bool(options.get('create_if_missing'))

        if not password:
            alphabet = string.ascii_letters + string.digits + '!@#$%^&*()-_=+'
            password = ''.join(secrets.choice(alphabet) for _ in range(16))

        if db_path:
            resolved = Path(db_path).expanduser().resolve()
            if not resolved.exists():
                raise CommandError(f'Database file not found: {resolved}')
            settings.DATABASES['default']['NAME'] = str(resolved)
            connections.close_all()
            self.stdout.write(f'Using database: {resolved}')

        user = User.objects.filter(username=username).first()
        if user is None:
            if not create_if_missing:
                raise CommandError(
                    f'User "{username}" not found. Use --create-if-missing to create it.'
                )
            user = User.objects.create_user(
                username=username,
                password=password,
                is_staff=True,
                is_superuser=True,
        email='demo_admin@example.com',
            )
            self.stdout.write(self.style.SUCCESS(f'Created user "{username}".'))
        else:
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=['password', 'is_staff', 'is_superuser'])
            self.stdout.write(self.style.SUCCESS(f'Updated password for "{username}".'))

        self.stdout.write('')
        self.stdout.write('Login credentials:')
        self.stdout.write(f'  Username: {username}')
        self.stdout.write(f'  Password: {password}')
        self.stdout.write('')
        self.stdout.write('Change this password after first login.')
