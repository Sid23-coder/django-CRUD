from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('tasks/', views.task_list, name='task_list'),  # Single route for both users and admins
    
    # Project URLs
    path('projects/create/', views.create_project, name='create_project'),
    path('projects/<int:project_id>/update/', views.update_project, name='update_project'),
    path('projects/<int:project_id>/delete/', views.delete_project, name='delete_project'),
    
    # Task URLs
    path('tasks/create/', views.create_task, name='create_task'),
    path('tasks/create/<int:project_id>/', views.create_task, name='create_task'),
    path('tasks/<int:task_id>/update/', views.update_task, name='update_task'),
    path('tasks/<int:task_id>/delete/', views.delete_task, name='delete_task'),
    path('tasks/<int:task_id>/set_permission/', views.set_task_permission, name='set_task_permission'),
    
    # Permission management
    path('tasks/<int:task_id>/permissions/', views.manage_task_permissions, name='manage_task_permissions'),
]