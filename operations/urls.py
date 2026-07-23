from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
urlpatterns=[
path('health/',views.health,name='health'),path('login/',auth_views.LoginView.as_view(template_name='registration/login.html'),name='login'),path('logout/',views.logout_view,name='logout'),path('',views.dashboard,name='dashboard'),
path('admin-panel/',views.admin_dashboard,name='admin_dashboard'),path('admin-panel/users/add/',views.create_user,name='create_user'),path('admin-panel/import/',views.csv_import,name='csv_import'),path('admin-panel/services/',views.service_catalog,name='service_catalog'),
path('manager/',views.manager_dashboard,name='manager_dashboard'),path('manager/visit/new/',views.new_visit,name='new_visit'),path('manager/visit/<int:visit_id>/edit-services/',views.edit_visit_services,name='edit_visit_services'),path('manager/service/<int:pk>/verify/',views.verify_service,name='verify_service'),path('manager/visit/<int:visit_id>/invoice/',views.add_invoice,name='add_invoice'),
path('employee/',views.employee_dashboard,name='employee_dashboard'),path('employee/service/<int:pk>/',views.execute_service,name='execute_service'),path('employee/task/<int:pk>/<str:action>/',views.task_action,name='task_action'),path('employee/service/<int:pk>/finish/',views.finish_service,name='finish_service'),
path('feedback/<uuid:token>/',views.feedback_form,name='feedback_form')]
