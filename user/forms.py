from django import forms
from .models import Task, Project

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'due_date', 'priority', 'status', 'project']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, user, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        
        # Get all projects owned by the user
        own_projects = list(Project.objects.filter(user=user))
        
        # Get projects where the user has shared tasks with edit permission
        shared_task_projects = set(Project.objects.filter(
            tasks__taskpermission__user=user,
            tasks__taskpermission__permission_type__in=['edit', 'admin']
        ).distinct())
        
        # Combine the lists
        all_available_projects = own_projects.copy()
        for project in shared_task_projects:
            if project not in own_projects:
                all_available_projects.append(project)
        
        # Update the project field queryset
        self.fields['project'].queryset = Project.objects.filter(
            id__in=[p.id for p in all_available_projects]
        )