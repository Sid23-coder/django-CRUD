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
from datetime import date

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
        # Default: Users can view their own tasks, but not edit/delete
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
    tasks = []
    if request.user.is_superuser:
        tasks = Task.objects.all()
        for task in tasks:
            task.has_edit_permission = True
            task.has_delete_permission = True
    else:
        # Own tasks (view only by default) + tasks with explicit permissions
        own_tasks = Task.objects.filter(user=request.user)
        shared_tasks = Task.objects.filter(taskpermission__user=request.user).distinct()
        tasks = list(own_tasks) + list(shared_tasks)
        for task in tasks:
            task.has_edit_permission = check_task_permission(request.user, task, 'edit')
            task.has_delete_permission = check_task_permission(request.user, task, 'delete')

    # Remove duplicates while preserving order
    seen_ids = set()
    unique_tasks = [t for t in tasks if not (t.id in seen_ids or seen_ids.add(t.id))]

    return render(request, 'task_list.html', {
        'tasks': unique_tasks,
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
            Task.objects.create(
                title=f"Initial task for {project.name}",
                description="Placeholder task - edit or delete as needed",
                user=request.user,
                project=project,
                due_date=date.today(),
                priority='Low',
                status='Pending'
            )
            messages.success(
                request,
                'Project created successfully with an initial task. Add more tasks or edit/delete this one.'
            )
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
    user = task.user  # Automatically set to the task owner
    if request.method == "POST":
        permission_type = request.POST.get('permission_type', '')
        if permission_type in ['view', 'edit', 'delete']:
            TaskPermission.objects.update_or_create(
                user=user,
                task=task,
                defaults={'permission_type': permission_type, 'assigned_by': request.user}
            )
            messages.success(request, f"Permissions updated for {user.username}")
        elif permission_type == '':
            TaskPermission.objects.filter(user=user, task=task).delete()
            messages.success(request, f"Permissions removed for {user.username}")
        return redirect('task_list')

    try:
        current_permission = TaskPermission.objects.get(user=user, task=task).permission_type
    except TaskPermission.DoesNotExist:
        current_permission = 'view'  # Default for owner
    return render(request, 'manage_permissions.html', {
        'task': task,
        'project_name': task.project.name,
        'current_permission': current_permission
    })

@login_required
@user_passes_test(is_admin)
def set_task_permission(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    user = task.user  # Automatically set to the task owner
    if request.method == "POST":
        permission_type = request.POST.get('permission_type', '')
        if permission_type in ['view', 'edit', 'delete']:
            TaskPermission.objects.update_or_create(
                task=task,
                user=user,
                defaults={'permission_type': permission_type, 'assigned_by': request.user}
            )
            messages.success(request, 'Permission updated successfully.')
        elif permission_type == '':
            TaskPermission.objects.filter(task=task, user=user).delete()
            messages.success(request, 'Permission removed successfully.')
        return redirect('task_list')
    return redirect('task_list')