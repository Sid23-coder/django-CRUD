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
        return True
    try:
        permission = TaskPermission.objects.get(user=user, task=task)
        if required_permission == 'view':
            return permission.permission_type in ['view', 'edit', 'delete']
        elif required_permission == 'edit':
            return permission.permission_type in ['edit', 'delete']
        elif required_permission == 'delete':
            return permission.permission_type == 'delete'
    except TaskPermission.DoesNotExist:
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
            messages.success(request, 'Login successful!')
            return redirect('task_list')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def user_logout(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('landing_page')

@login_required
def task_list(request):
    if request.user.is_superuser:
        tasks = Task.objects.all().select_related('project', 'user', 'project__user').order_by('project')
        for task in tasks:
            task.has_edit_permission = True
            task.has_delete_permission = True
        projects = Project.objects.all().prefetch_related('assigned_users', 'user')
        display_projects = []
        for project in projects:
            for assigned_user in project.assigned_users.all():
                display_project = {
                    'id': project.id,
                    'name': project.name,
                    'original_project': project,
                    'creator': project.user.username,
                    'assigned_to': assigned_user.username,
                    'tasks': [task for task in tasks if task.project_id == project.id]
                }
                display_projects.append(display_project)
            if not project.assigned_users.exists():
                display_project = {
                    'id': project.id,
                    'name': project.name,
                    'original_project': project,
                    'creator': project.user.username,
                    'assigned_to': project.user.username,
                    'tasks': [task for task in tasks if task.project_id == project.id]
                }
                display_projects.append(display_project)
    else:
        own_tasks = Task.objects.filter(user=request.user)
        shared_tasks = Task.objects.filter(taskpermission__user=request.user)
        assigned_project_tasks = Task.objects.filter(project__assigned_users=request.user)
        tasks = (own_tasks | shared_tasks | assigned_project_tasks).distinct().select_related('project', 'user', 'project__user').order_by('project')
        for task in tasks:
            task.has_edit_permission = check_task_permission(request.user, task, 'edit')
            task.has_delete_permission = check_task_permission(request.user, task, 'delete')
        user_projects = Project.objects.filter(assigned_users=request.user).select_related('user').prefetch_related('assigned_users')
        owned_projects = Project.objects.filter(user=request.user).select_related('user').prefetch_related('assigned_users')
        all_user_projects = (user_projects | owned_projects).distinct()
        display_projects = []
        for project in all_user_projects:
            if project.user == request.user and request.user in project.assigned_users.all():
                display_project = {
                    'id': project.id,
                    'name': project.name,
                    'original_project': project,
                    'creator': project.user.username,
                    'assigned_to': request.user.username,
                    'tasks': [task for task in tasks if task.project_id == project.id]
                }
                display_projects.append(display_project)
            elif request.user in project.assigned_users.all():
                display_project = {
                    'id': project.id,
                    'name': project.name,
                    'original_project': project,
                    'creator': project.user.username,
                    'assigned_to': request.user.username,
                    'tasks': [task for task in tasks if task.project_id == project.id]
                }
                display_projects.append(display_project)
            elif project.user == request.user:
                display_project = {
                    'id': project.id,
                    'name': project.name,
                    'original_project': project,
                    'creator': project.user.username,
                    'assigned_to': project.user.username,
                    'tasks': [task for task in tasks if task.project_id == project.id]
                }
                display_projects.append(display_project)

    return render(request, 'task_list.html', {
        'display_projects': display_projects,
        'is_admin': request.user.is_superuser,
    })

@login_required
def create_project(request):
    if request.method == "POST":
        form = ProjectForm(request.POST, user=request.user)
        if form.is_valid():
            project = form.save(commit=False)
            # Set the project owner
            if request.user.is_superuser and 'owner' in request.POST:
                owner_id = request.POST.get('owner')
                project.user = User.objects.get(id=owner_id)
            else:
                project.user = request.user
            project.save()
            
            # Handle user assignments
            if request.user.is_superuser and 'assigned_users' in request.POST:
                # Get the list of selected user IDs from checkboxes
                assigned_user_ids = request.POST.getlist('assigned_users')
                assigned_users = User.objects.filter(id__in=assigned_user_ids)
                # Assign only the selected users
                project.assigned_users.set(assigned_users)
                # Ensure the owner is included (if not already selected)
                # if project.user not in assigned_users:
                #     project.assigned_users.add(project.user)
                # messages.success(
                #     request,
                #     f'Project created successfully for {project.user.username} with {project.assigned_users.count()} assigned users.'
                # )
            else:
                # For non-admins, assign only to themselves
                project.assigned_users.set([request.user])
                messages.success(request, 'Project created successfully.')
            
            # Create an initial task
            Task.objects.create(
                title=f"Initial task for {project.name}",
                description="Placeholder task - edit or delete as needed",
                user=project.user,
                project=project,
                due_date=date.today(),
                priority='Low',
                status='Pending'
            )
            return redirect('task_list')
    else:
        form = ProjectForm(user=request.user)
    
    context = {
        'form': form,
        'action': 'Create',
        'is_admin': request.user.is_superuser,
    }
    if request.user.is_superuser:
        context['all_users'] = User.objects.all()
        context['current_assigned_users'] = []
    
    return render(request, 'project_form.html', context)

@login_required
def update_project(request, project_id):
    if request.user.is_superuser:
        project = get_object_or_404(Project, id=project_id)
    else:
        project = get_object_or_404(Project, id=project_id, user=request.user)
        
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project, user=request.user)
        if form.is_valid():
            project = form.save(commit=False)
            project.save()
            
            if request.user.is_superuser and 'assigned_users' in request.POST:
                # Get the list of selected user IDs from checkboxes
                assigned_user_ids = request.POST.getlist('assigned_users')
                assigned_users = User.objects.filter(id__in=assigned_user_ids)
                # Clear existing assignments and set only selected users
                project.assigned_users.clear()
                project.assigned_users.set(assigned_users)
                # Ensure the owner is included (if not already selected)
                if project.user not in assigned_users:
                    project.assigned_users.add(project.user)
                messages.success(
                    request,
                    f'Project updated successfully with {project.assigned_users.count()} assigned users.'
                )
            else:
                # For non-admins, ensure they remain assigned
                if request.user not in project.assigned_users.all():
                    project.assigned_users.clear()
                    project.assigned_users.add(request.user)
                messages.success(request, 'Project updated successfully!')
            
            return redirect('task_list')
    else:
        form = ProjectForm(instance=project, user=request.user)
    
    context = {
        'form': form,
        'action': 'Update',
        'is_admin': request.user.is_superuser,
    }
    if request.user.is_superuser:
        context['all_users'] = User.objects.all()
        context['current_assigned_users'] = project.assigned_users.all()
    
    return render(request, 'project_form.html', context)

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
    user = task.user
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
        current_permission = 'view'
    return render(request, 'manage_permissions.html', {
        'task': task,
        'project_name': task.project.name,
        'current_permission': current_permission
    })

@login_required
@user_passes_test(is_admin)
def set_task_permission(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    user = task.user
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