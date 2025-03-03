from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from .models import Task, Project, TaskPermission
from .forms import TaskForm, ProjectForm

# Updated helper function: Owners don't get edit/delete by default
def check_task_permission(user, task, required_permission='view'):
    if user.is_superuser:
        return True  # Admins have full access
    try:
        permission = TaskPermission.objects.get(user=user, task=task)
        if required_permission == 'view':
            return permission.permission_type in ['view', 'edit', 'delete']
        elif required_permission == 'edit':
            return permission.permission_type in ['edit', 'delete']
        elif required_permission == 'delete':
            return permission.permission_type == 'delete'
    except TaskPermission.DoesNotExist:
        # Default: Users can view their own tasks, but not edit/delete without explicit permission
        if task.user == user and required_permission == 'view':
            return True
        return False
    return False

def is_admin(user):
    return user.is_superuser

def landing_page(request):
    return render(request, 'landing.html')

def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('task_list')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            storage = messages.get_messages(request)
            storage.used = True
            messages.success(request, 'Login successful!')
            return redirect('task_list')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def user_logout(request):
    logout(request)
    storage = messages.get_messages(request)
    storage.used = True
    messages.info(request, 'You have been logged out.')
    return redirect('landing_page')

@login_required
def task_list(request):
    projects_with_tasks = []

    if request.user.is_superuser:
        all_projects = Project.objects.all().prefetch_related('tasks')
        for project in all_projects:
            tasks = project.tasks.all()
            for task in tasks:
                task.has_edit_permission = True  # Admin can edit all
                task.has_delete_permission = True  # Admin can delete all
            projects_with_tasks.append({
                'project': project,
                'tasks': tasks,
                'is_owner': project.user == request.user,
                'owner_username': project.user.username
            })
    else:
        own_projects = Project.objects.filter(user=request.user).prefetch_related('tasks')
        shared_tasks = Task.objects.filter(taskpermission__user=request.user).select_related('project').distinct()
        shared_project_ids = set(shared_tasks.values_list('project', flat=True))
        shared_projects = Project.objects.filter(id__in=shared_project_ids).prefetch_related('tasks')

        for project in own_projects:
            tasks = project.tasks.all()
            for task in tasks:
                task.has_edit_permission = check_task_permission(request.user, task, 'edit')
                task.has_delete_permission = check_task_permission(request.user, task, 'delete')
            projects_with_tasks.append({
                'project': project,
                'tasks': tasks,
                'is_owner': True,
                'owner_username': request.user.username
            })

        for project in shared_projects:
            if project.user != request.user:
                tasks = Task.objects.filter(project=project, taskpermission__user=request.user).distinct()
                for task in tasks:
                    task.has_edit_permission = check_task_permission(request.user, task, 'edit')
                    task.has_delete_permission = check_task_permission(request.user, task, 'delete')
                projects_with_tasks.append({
                    'project': project,
                    'tasks': tasks,
                    'is_owner': False,
                    'owner_username': project.user.username
                })

    return render(request, 'task_list.html', {
        'projects_with_tasks': projects_with_tasks,
        'is_admin': request.user.is_superuser
    })

@login_required
def create_project(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.user = request.user
            project.save()
            messages.success(request, 'Project created successfully!')
            return redirect('task_list')
    else:
        form = ProjectForm()
    return render(request, 'project_form.html', {'form': form, 'action': 'Create'})

@login_required
def update_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Project updated successfully!')
            return redirect('task_list')
    else:
        form = ProjectForm(instance=project)
    return render(request, 'project_form.html', {'form': form, 'action': 'Update'})

@login_required
def delete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    project.delete()
    messages.success(request, 'Project deleted successfully!')
    return redirect('task_list')

@login_required
def create_task(request, project_id=None):
    if request.method == "POST":
        form = TaskForm(request.user, request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, 'Task created successfully!')
            return redirect('task_list')
    else:
        initial_data = {}
        if project_id:
            project = get_object_or_404(Project, id=project_id)
            if project.user == request.user or request.user.is_superuser:
                initial_data = {'project': project}
            else:
                has_permission = Task.objects.filter(
                    project=project,
                    taskpermission__user=request.user,
                    taskpermission__permission_type__in=['edit', 'delete']
                ).exists()
                if has_permission:
                    initial_data = {'project': project}
                else:
                    raise PermissionDenied("You don't have permission to add tasks to this project.")
        form = TaskForm(request.user, initial=initial_data)
    return render(request, 'task_form.html', {'form': form, 'action': 'Create'})

@login_required
def update_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if not check_task_permission(request.user, task, 'edit'):
        raise PermissionDenied("You don't have permission to edit this task.")
    if request.method == "POST":
        form = TaskForm(request.user, request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Task updated successfully!')
            return redirect('task_list')
    else:
        form = TaskForm(request.user, instance=task)
    return render(request, 'task_form.html', {'form': form, 'action': 'Update'})

@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if not check_task_permission(request.user, task, 'delete'):
        raise PermissionDenied("You don't have permission to delete this task.")
    task.delete()
    messages.success(request, 'Task deleted successfully!')
    return redirect('task_list')

@login_required
@user_passes_test(is_admin)
def manage_task_permissions(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == "POST":
        if 'action' in request.POST and request.POST['action'] == 'remove':
            user_id = request.POST.get('user_id')
            TaskPermission.objects.filter(task=task, user_id=user_id).delete()
            messages.success(request, 'Permission removed successfully!')
        else:
            user_id = request.POST.get('user_id')
            permission_type = request.POST.get('permission_type')
            if user_id and permission_type:
                user = get_object_or_404(User, id=user_id)
                TaskPermission.objects.update_or_create(
                    user=user,
                    task=task,
                    defaults={'permission_type': permission_type, 'assigned_by': request.user}
                )
                messages.success(request, f'Permissions updated for {user.username}')
        return redirect('task_list')
    available_users = User.objects.exclude(id=task.user.id)
    current_permissions = TaskPermission.objects.filter(task=task)
    return render(request, 'manage_permissions.html', {
        'task': task,
        'available_users': available_users,
        'current_permissions': current_permissions
    })

@login_required
@user_passes_test(is_admin)
def set_task_permission(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == "POST":
        user_id = request.POST.get('user_id')
        permission_type = request.POST.get('permission_type')
        user = get_object_or_404(User, id=user_id)

        if task.user == user:
            messages.error(request, 'Cannot modify permissions for the task owner.')
        else:
            if permission_type:
                TaskPermission.objects.update_or_create(
                    task=task,
                    user=user,
                    defaults={'permission_type': permission_type, 'assigned_by': request.user}
                )
                messages.success(request, 'Permission updated successfully.')
            else:
                TaskPermission.objects.filter(task=task, user=user).delete()
                messages.success(request, 'Permission removed successfully.')
        return redirect('task_list')
    return redirect('task_list')