from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Branch, BranchDuty


@override_settings(STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class AccountTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(code='A', name='Branch A')
        self.user = User.objects.create_user('self_user', password='Old-test-pass!27', first_name='Original')
        self.user.profile.branch = self.branch
        self.user.profile.save()
        self.other = User.objects.create_user('other_user', password='Other-test-pass!27')
        self.client.force_login(self.user)

    def details(self, **extra):
        return dict(action='details', first_name='Updated', last_name='Person',
                    email='updated@example.com', mobile='+91 98765 43210', **extra)

    def password(self, old='Old-test-pass!27', new='Fresh-test-pass!92', confirmation=None):
        return dict(action='password', old_password=old, new_password1=new,
                    new_password2=confirmation if confirmation is not None else new)

    def test_profile_and_icon_menu_available_for_every_role_without_branch_duty(self):
        for role in ['ADMIN', 'GENERAL_MANAGER', 'MANAGER', 'EMPLOYEE']:
            self.user.profile.role = role
            self.user.profile.save()
            response = self.client.get(reverse('my_profile'))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'aria-label="Open profile menu"')
            self.assertContains(response, f'href="{reverse("my_profile")}"')
            self.assertContains(response, 'role="switch" aria-label="Dark mode"')
            self.assertContains(response, 'data-theme-key="hairship-theme-')
            self.assertContains(response, 'Save details')
            self.assertContains(response, 'Change password')
        self.user.is_superuser = True
        self.user.save()
        self.assertEqual(self.client.get(reverse('my_profile')).status_code, 200)

    def test_self_details_update_cannot_target_another_user_or_change_authorization(self):
        response = self.client.post(reverse('my_profile'), self.details(
            user_id=self.other.pk, username='other_user', role='ADMIN',
            branch='', is_superuser='true', is_staff='true', active='false',
            employee_code='OVERRIDE', job_title='Director', password='unsafe',
        ))
        self.assertRedirects(response, reverse('my_profile'))
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Person')
        self.assertEqual(self.user.email, 'updated@example.com')
        self.assertEqual(self.user.profile.mobile, '+91 98765 43210')
        self.assertEqual(self.user.username, 'self_user')
        self.assertEqual(self.user.profile.role, 'EMPLOYEE')
        self.assertEqual(self.user.profile.branch, self.branch)
        self.assertEqual(self.user.profile.employee_code, '')
        self.assertEqual(self.user.profile.job_title, '')
        self.assertTrue(self.user.profile.active)
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.is_staff)
        self.assertTrue(self.user.check_password('Old-test-pass!27'))
        self.assertEqual(self.other.first_name, '')

    def test_invalid_details_do_not_save(self):
        data = self.details()
        data.update(email='invalid', mobile='not a phone')
        response = self.client.post(reverse('my_profile'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['details_form'].errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Original')
        self.assertEqual(self.user.profile.mobile, '')

    def test_password_change_checks_current_password_and_keeps_current_session(self):
        response = self.client.post(reverse('my_profile'), self.password())
        self.assertRedirects(response, reverse('my_profile'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Fresh-test-pass!92'))
        self.assertFalse(self.user.check_password('Old-test-pass!27'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.assertFalse(Client().login(username=self.user.username, password='Old-test-pass!27'))
        self.assertTrue(Client().login(username=self.user.username, password='Fresh-test-pass!92'))

    def test_password_errors_do_not_change_password_or_details(self):
        for data in [self.password(old='wrong'), self.password(confirmation='different'),
                     self.password(new='short'), self.password(new='1234567890')]:
            data['first_name'] = 'Must not change'
            response = self.client.post(reverse('my_profile'), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['password_form'].errors)
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password('Old-test-pass!27'))
            self.assertEqual(self.user.first_name, 'Original')

    def test_profile_requires_authentication_active_profile_and_csrf(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('my_profile')).status_code, 302)
        self.assertEqual(self.client.post(reverse('my_profile'), self.details()).status_code, 302)
        self.client.force_login(self.user)
        self.user.profile.active = False
        self.user.profile.save()
        self.assertEqual(self.client.get(reverse('my_profile')).status_code, 403)
        self.user.profile.active = True
        self.user.profile.save()
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(reverse('my_profile'), self.password()).status_code, 403)


@override_settings(STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ManagerStaffTests(TestCase):
    def setUp(self):
        self.a = Branch.objects.create(code='A', name='Branch A')
        self.b = Branch.objects.create(code='B', name='Branch B')
        self.manager = self.person('manager', 'MANAGER', self.a)
        self.local = self.person('local', 'EMPLOYEE', self.a)
        self.away = self.person('away', 'EMPLOYEE', self.a)
        self.leave = self.person('leave', 'EMPLOYEE', self.a)
        self.visitor = self.person('cover', 'EMPLOYEE', self.b)
        self.foreign = self.person('foreign', 'EMPLOYEE', self.b)
        self.gm = self.person('gm', 'GENERAL_MANAGER', None)
        self.duty(self.away, self.b)
        self.duty(self.leave, status='LEAVE')
        self.duty(self.visitor, self.a)

    def person(self, username, role, branch):
        user = User.objects.create_user(username)
        user.profile.role = role
        user.profile.branch = branch
        user.profile.save()
        return user

    def duty(self, user, branch=None, status='WORK'):
        return BranchDuty.objects.create(user=user, branch=branch, status=status,
                                        date=timezone.localdate(), updated_by=self.manager)

    def test_manager_sees_branch_staff_leave_and_cover_not_other_branches(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('manager_staff') + '?branch=' + str(self.b.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual({p.pk for p in response.context['staff']},
                         {self.local.pk, self.away.pk, self.leave.pk, self.visitor.pk})
        self.assertContains(response, 'On leave')
        self.assertContains(response, 'Working at another branch')
        self.assertContains(response, f'href="{reverse("manager_staff")}"')
        self.assertNotContains(response, self.foreign.username)
        self.assertEqual(self.client.post(reverse('manager_staff'), {}).status_code, 405)

    def test_compact_staff_layout_preserves_contact_and_work_details(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('manager_staff'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="page-head staff-page-head"')
        self.assertContains(response, '<h1>All staff</h1>')
        self.assertContains(response, 'class="staff-card-head"', count=4)
        for label in ['Username', 'Email', 'Mobile', 'Open services here']:
            self.assertContains(response, f'<dt>{label}</dt>', count=4)
        self.assertContains(response, 'On leave')
        self.assertContains(response, 'Working at another branch')

    def test_employee_and_unrostered_general_manager_cannot_access_staff_list(self):
        for user in [self.local, self.gm]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('manager_staff')).status_code, 403)
        self.duty(self.gm, self.a)
        self.client.force_login(self.gm)
        self.assertEqual(self.client.get(reverse('manager_staff')).status_code, 200)

    def test_roster_changes_manager_scope_and_leave_blocks_staff_access(self):
        duty = self.duty(self.manager, self.b)
        self.client.force_login(self.manager)
        response = self.client.get(reverse('manager_staff'))
        self.assertEqual(response.context['branch'], self.b)
        self.assertNotIn(self.local.pk, {p.pk for p in response.context['staff']})
        duty.status = 'LEAVE'
        duty.branch = None
        duty.save()
        self.assertEqual(self.client.get(reverse('manager_staff')).status_code, 403)
