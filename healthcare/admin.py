from django.contrib import admin
from .models import Speciality, Hospital, Doctor, Patient, Appointment, MedicalRecord, Blog


# Register your models here.
admin.site.register(Speciality)
admin.site.register(Hospital)
admin.site.register(Doctor)
admin.site.register(Patient)
admin.site.register(Appointment)
admin.site.register(MedicalRecord)
admin.site.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'published_date')
    prepopulated_fields = {'slug': ('title',)}


