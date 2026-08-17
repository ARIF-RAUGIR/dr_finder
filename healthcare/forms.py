from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class patientsignup(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

class doctorsignup(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')    

        
