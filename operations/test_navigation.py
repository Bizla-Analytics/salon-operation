from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class AdminNavigationTests(TestCase):
    def test_admin_has_visible_desktop_and_mobile_sign_out(self):
        user = User.objects.create_user("admin_nav", password="test")
        user.profile.role = "ADMIN"
        user.profile.save()
        self.client.force_login(user)

        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="desktop-session-bar"')
        self.assertContains(response, 'class="mobile-signout"')
        self.assertContains(response, f'href="{reverse("logout")}"')

        self.assertRedirects(self.client.get(reverse("logout")), reverse("login"))
