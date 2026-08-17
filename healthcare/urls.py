from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('', views.home, name='home'),
    path('patient/signup', views.patient_signup, name='patient_signup'),
    path('patient/profile', views.patient_profile, name='patient_profile'),
    path('patient/login', views.patient_login, name='patient_login'),
    path('patient/logout', views.patient_logout, name='patient_logout'),
    path('doctor/signup', views.doctor_signup, name='doctor_signup'),
    path('doctor/login', views.doctor_login, name='doctor_login'),
    path('doctor/profile', views.doctor_profile, name='doctor_profile'),
    path('doctor/logout', views.doctor_logout, name='doctor_logout'),
    path('doctor/verified', views.doctor_verified, name='doctor_verified'),
    path('doctors/', views.doctors_page, name='doctors'),
    path('hospitals/', views.hospitals_page, name='hospitals'), 
    path('speciality/', views.specialties_page, name='speciality'),
    path('blog/', views.blog_list, name='blog'),
    path('about/', views.about_page, name='about'),
    path('book_appointment/<int:doctor_id>', views.book_appointment, name='book_appointment'),
    path('appointments/', views.patient_appointments, name='patient_appointments'),
    path('doctor/dashboard', views.doctor_dashboard, name='doctor_dashboard'),
    path('patient/dashboard', views.patient_dashboard, name='patient_dashboard'),
    path('doctor/all_appointments', views.doctor_all_appointments, name='doctor_all_appointments'),
    path('update_appointment_status/<int:appointment_id>/<str:new_status>', views.update_appointment_status, name='update_appointment_status'),
    path('medical_report/<int:appointment_id>', views.medical_report, name='medical_report'),
    path('view_patient_history/<int:patient_id>', views.view_patient_history, name='view_patient_history'),
    path('doctor/patients', views.doctor_patients, name='doctor_patients'),
    path('patient/full_history', views.patient_full_history, name='patient_full_history'),
    # path('blog/', views.blog_list, name='blog_list'),
    path('blog/<slug:slug>', views.blog_detail, name='blog_detail'),
    path('api/chat/', views.chat_api, name='chat_api'),
    

    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)