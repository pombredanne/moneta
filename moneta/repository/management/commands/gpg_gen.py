# -*- coding=utf-8 -*-
import os
import pwd
import stat
from argparse import ArgumentParser

from django.conf import settings
from django.core.management.base import BaseCommand

from moneta.repository.signing import GPG

__author__ = 'flanker'

if settings.ADMINS and len(settings.ADMINS[0]) == 2:
    default_email = settings.ADMINS[0][1]
else:
    default_email = 'moneta@19pouces.net'


class Command(BaseCommand):
    args = '<generate|show|export>'
    help = """command=generate: Create a new GPG key
    command=show: Show existing GPG keys
    command=export: export GPG key"""

    def add_arguments(self, parser):
        assert isinstance(parser, ArgumentParser)
        parser.add_argument('gpg_command', action='store', default=None, choices=['generate', 'show', 'export']),
        parser.add_argument('--type', action='store', default='RSA', help='Key type (RSA or DSA).',
                            choices=('RSA', 'DSA')),
        parser.add_argument('--length', action='store', default='2048', help='Key length (default 2048).'),
        parser.add_argument('--name', action='store', default='Moneta GNUPG key', help='Name of the key'),
        parser.add_argument('--comment', action='store', default='Generated by gnupg.py',
                            help='Comment to add to the generated key.'),
        parser.add_argument('--email', action='store', default=default_email, help='Email address for the user.'),
        parser.add_argument('--years', action='store', default='10y',
                            help='Expiration date, in number of years (like "10y") or days (like "10d").'),
        parser.add_argument('--absent', action='store_true',
                            default=False, help='Generate keys only when no key already exists.'),
        parser.add_argument('--onlyid', action='store_true', default=False,
                            help='Generate keys only when no key already exists.'),

    def handle(self, *args, **options):
        command = options['gpg_command']
        if command == 'generate':
            if options['absent'] and len(GPG.list_keys(False)) > 0:
                return
            input_data = GPG.gen_key_input(key_type=options['type'], key_length=int(options['length']),
                                           name_real=options['name'], name_comment=options['comment'],
                                           name_email=options['email'],
                                           expire_date=options['years'])
            key = GPG.gen_key(input_data)
            print("Fingerprint", key)
        elif command == 'show':
            if options['onlyid']:
                for key in GPG.list_keys(False):
                    print("{keyid}".format(**key))
            else:
                print("Available keys:")
                for key in GPG.list_keys(False):
                    print("id (GNUPG_KEYID) : {keyid}, longueur : {length}, empreinte : {fingerprint}".format(**key))
        elif command == 'export':
            print(GPG.export_keys(settings.GNUPG_KEYID))
        self.check_rights()

    def check_rights(self):
        os_stat = os.stat(settings.GNUPG_HOME)
        must_apply_rights = self.check_mode(os_stat, stat.S_IRUSR | stat.S_IXUSR | stat.S_IWUSR)
        must_apply_owners = self.check_owner(os_stat)
        for root, dirnames, filenames in os.walk(settings.GNUPG_HOME):
            for filename in filenames:
                os_stat = os.stat(os.path.join(root, filename))
                must_apply_rights |= self.check_mode(os_stat, stat.S_IRUSR | stat.S_IWUSR)
                must_apply_owners |= self.check_owner(os_stat)
            for dirname in dirnames:
                os_stat = os.stat(os.path.join(root, dirname))
                must_apply_rights |= self.check_mode(os_stat, stat.S_IRUSR | stat.S_IXUSR | stat.S_IWUSR)
                must_apply_owners |= self.check_owner(os_stat)

        if must_apply_rights:
            self.stderr.write('Invalid permissions. You should run the following commands to fix them')
            self.stderr.write('chmod 0700 "%s"' % settings.GNUPG_HOME)
            self.stderr.write('find "%s" -type d -exec chmod 0700 {} \;' % settings.GNUPG_HOME)
            self.stderr.write('find "%s" -type f -exec chmod 0600 {} \;' % settings.GNUPG_HOME)
        if must_apply_owners:
            user = pwd.getpwuid(os.getuid())
            if user:
                self.stderr.write('Invalid file owners. You should run the following command to fix them')
                self.stderr.write('chown -R "%s" %s' % (settings.GNUPG_HOME, user[0]))

    @staticmethod
    def check_owner(os_stat):
        return os_stat.st_uid != os.getuid()

    @staticmethod
    def check_mode(os_stat, expected):
        mask = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
        current_mode = os_stat.st_mode
        return bool((current_mode & mask) - (current_mode & expected)) or (current_mode & expected != expected)
