from django.db import models
from django.contrib.auth.models import User
from datetime import date
from django.urls import reverse
from django.utils.text import slugify



# Create your models here.
class Speciality(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, default='fa-notes-medical')

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Specialities"

class Hospital(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=100)
    phone = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    photo = models.ImageField(upload_to='hospitals/', null=True, blank=True)
    has_emergency = models.BooleanField(default=False)
    is_open_24_7 = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Doctor(models.Model):
    TITLE_CHOICES = [
        ('Dr.', 'Dr.'),
        ('Prof. Dr.', 'Prof. Dr.'),
        ('Asst. Prof. Dr.', 'Asst. Prof. Dr.'),
        ('Assoc. Prof. Dr.', 'Assoc. Prof. Dr.'),
    ]
    title = models.CharField(max_length=30, choices=TITLE_CHOICES, default='Dr.')
    user = models.OneToOneField(User, on_delete=models.CASCADE,related_name='doctor_profile')
    phone = models.CharField(max_length=100, null=True, blank=True)
    speciality = models.ForeignKey(Speciality, on_delete=models.SET_NULL, null=True, blank=True, related_name='specialities')
    hospital = models.ForeignKey(Hospital, on_delete=models.SET_NULL, null=True, blank=True, related_name='hospitals')
    qualification = models.CharField(max_length=100, null=True, blank=True)
    bmdc_number = models.CharField(max_length=100, null=True, blank=True)
    consultation_fee = models.PositiveIntegerField(null=True, blank=True)
    photo = models.ImageField(upload_to='doctors/', null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    review_count = models.PositiveIntegerField(default=0)
    available_days = models.CharField(max_length=200, blank=True, help_text="e.g. Saturday, Sunday, Tuesday, Thursday")
    morning_hours = models.CharField(max_length=50, blank=True, help_text="e.g. 9:00 AM - 12:00 PM")
    afternoon_hours = models.CharField(max_length=50, blank=True, help_text="e.g. 3:00 PM - 6:00 PM")
    evening_hours = models.CharField(max_length=50, blank=True, help_text="e.g. 7:00 PM - 10:00 PM")
    is_verified = models.BooleanField(default=False)

    def is_available_today(self):
        if not self.available_days:
            return True
        today_name = date.today().strftime('%A')
        days_list = [d.strip() for d in self.available_days.split(',')]
        return today_name in days_list
    

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"
    
class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    phone = models.CharField(max_length=100, null=True, blank=True)
    address = models.CharField(max_length=100, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=100, null=True, blank=True)
    photo = models.ImageField(upload_to='patients/', null=True, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

class Appointment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    )

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    appointment_date = models.DateField()
    appointment_time = models.CharField(max_length=100, choices=[
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('evening', 'Evening'),
    ])
    status = models.CharField(max_length=100, choices=STATUS_CHOICES)
    reason = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient} with Dr. {self.doctor} on {self.appointment_date} at {self.appointment_time}"

class MedicalRecord(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='records')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='records')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='records')
    diagnosis = models.TextField()
    prescription = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.patient} with Dr. {self.doctor} on {self.appointment_date} at {self.appointment_time}"

class Blog(models.Model):
    CATEGORY_CHOICES = [
        ('Nutrition', 'Nutrition'),
        ('Fitness', 'Fitness'),
        ('Mental Health', 'Mental Health'),
        ('Sleep', 'Sleep'),
        ('Wellness', 'Wellness'),
        ('Heart Health', 'Heart Health'),
    ]
 
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    image = models.ImageField(upload_to='blog_images/', blank=True, null=True)
    short_description = models.CharField(max_length=300, help_text="Shown on the card")
    content = models.TextField(help_text="Full blog content, shown on detail page")
    published_date = models.DateField(auto_now_add=True)
 
    class Meta:
        ordering = ['-published_date']
 
    def __str__(self):
        return self.title
 
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
 
    def get_absolute_url(self):
        return reverse('blog_detail', kwargs={'slug': self.slug})


class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=100, blank=True)  # login na thakle ei diye track hobe
    created_at = models.DateTimeField(auto_now_add=True)
 
    def __str__(self):
        return f"Chat #{self.id}"
 
 
class ChatMessage(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('bot', 'Bot')]
 
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ['created_at']
 
    def __str__(self):
        return f"{self.role}: {self.text[:40]}"
 