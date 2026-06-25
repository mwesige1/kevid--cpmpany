from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Set up default groups and permissions'

    def handle(self, *args, **kwargs):

        # ── Create Groups ──────────────────────────────
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        staff_group, _   = Group.objects.get_or_create(name='Staff')

        self.stdout.write('✅ Groups created: Manager, Staff')

        # ── Define Custom Permissions ──────────────────
        # We use the dashboard app's content type
        from dashboard.models import Expense
        ct = ContentType.objects.get_for_model(Expense)

        permissions = [
            # Sessions & Devices
            ('view_sessions',       'Can view active sessions'),
            ('disconnect_sessions', 'Can disconnect sessions'),
            ('view_devices',        'Can view devices'),
            ('block_devices',       'Can block/unblock devices'),
            # Payments & Finance
            ('view_payments',       'Can view payments'),
            ('record_payments',     'Can record manual payments'),
            ('view_withdrawals',    'Can view withdrawals'),
            ('create_withdrawal',   'Can request withdrawals'),
            ('view_expenses',       'Can view expenses'),
            ('create_expense',      'Can record expenses'),
            ('view_analytics',      'Can view financial analytics'),
            # Management
            ('manage_packages',     'Can manage packages'),
            ('manage_vouchers',     'Can manage vouchers'),
            ('manage_customers',    'Can manage customers'),
            ('manage_leads',        'Can manage leads'),
            ('send_messages',       'Can send messages'),
            ('manage_settings',     'Can manage settings'),
        ]

        for codename, name in permissions:
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=ct,
                defaults={'name': name}
            )
            if created:
                self.stdout.write(f'  Created permission: {codename}')

        # ── Assign Default Manager Permissions ─────────
        manager_perms = Permission.objects.filter(
            content_type=ct,
            codename__in=[
                'view_sessions', 'disconnect_sessions',
                'view_devices', 'block_devices',
                'view_payments', 'record_payments',
                'view_withdrawals', 'create_withdrawal',
                'view_expenses', 'create_expense',
                'view_analytics', 'manage_packages',
                'manage_vouchers', 'manage_customers',
                'manage_leads', 'send_messages',
            ]
        )
        manager_group.permissions.set(manager_perms)

        # ── Assign Default Staff Permissions ───────────
        staff_perms = Permission.objects.filter(
            content_type=ct,
            codename__in=[
                'view_sessions', 'view_devices',
                'view_payments', 'view_expenses',
            ]
        )
        staff_group.permissions.set(staff_perms)

        self.stdout.write(self.style.SUCCESS(
            '✅ Permissions set up successfully!'
        ))
