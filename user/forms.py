from django import forms
from django.contrib.auth.models import User
from .models import Task, Project, TaskPermission

class ProjectForm(forms.ModelForm):
    assigned_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        help_text="Select users who will be assigned to this project. Hold Ctrl (or Cmd on Mac) to select multiple users."
    )

    class Meta:
        model = Project
        fields = ['name', 'description', 'assigned_users']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        # Get the user from kwargs and then remove it to avoid issues with the ModelForm
        user = kwargs.pop('user', None)
        super(ProjectForm, self).__init__(*args, **kwargs)
        
        # For admin users, show all users for assignment
        # For regular users, don't show the assignment field or limit to certain users if needed
        if user and not user.is_superuser:
            self.fields.pop('assigned_users', None)

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'due_date', 'priority', 'status', 'project']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'project': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, user, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        # Show only projects the user owns or is assigned to
        if user.is_superuser:
            self.fields['project'].queryset = Project.objects.all()
        else:
            self.fields['project'].queryset = (
                Project.objects.filter(user=user) | 
                Project.objects.filter(assigned_users=user)
            ).distinct()