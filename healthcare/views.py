from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Count, Q
from .models import Speciality, Hospital, Doctor, Patient, Appointment, MedicalRecord, Blog
from django.contrib import messages
from datetime import date
from django.utils import timezone
from django.db.models import Sum
from geopy.distance import geodesic
import json
import anthropic
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import ChatSession, ChatMessage, Speciality


SYSTEM_PROMPT = """You are a helpful medical triage assistant for Dr.Finder, a Bangladeshi healthcare platform.

Your job:
1. Ask the patient about their symptoms in a warm, simple way (Bengali or English, matching their language).
2. Based on their symptoms, suggest which medical specialty they should see (e.g. Cardiologist, Neurologist, General Physician, Dermatologist, Pediatrician, ENT, Orthopedics, Gynecologist).
3. If symptoms sound like a medical emergency (chest pain, difficulty breathing, severe bleeding, loss of consciousness, stroke signs), tell them clearly and urgently to call 999 or go to the nearest emergency hospital immediately - do not continue normal conversation.
4. Never diagnose a specific disease or prescribe medication. You only suggest which type of specialist to see.
5. Keep responses short and conversational (2-4 sentences).
6. Once you have a clear specialty suggestion, end your message with a line in this exact format so the app can detect it:
SPECIALTY_SUGGESTION: <specialty name>

Only include the SPECIALTY_SUGGESTION line when you are confident, not on every message.
"""


@csrf_exempt
@require_POST
def chat_api(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'error': 'Invalid request body'}, status=400)

    user_message = data.get('message', '').strip()
    if not user_message:
        return JsonResponse({'error': 'Empty message'}, status=400)

    # Session ber kora ba banano (login thakle user, na thakle browser session)
    if request.user.is_authenticated:
        session, _ = ChatSession.objects.get_or_create(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
        session, _ = ChatSession.objects.get_or_create(session_key=request.session.session_key)

    # Age er conversation history (last 10 message, context er jonno)
    history = list(session.messages.order_by('-created_at')[:10])
    history.reverse()

    api_messages = []
    for m in history:
        role = "assistant" if m.role == "bot" else "user"
        api_messages.append({"role": role, "content": m.text})

    api_messages.append({"role": "user", "content": user_message})

    # User message DB-te save
    ChatMessage.objects.create(session=session, role='user', text=user_message)

    # Claude API key check
    if not settings.ANTHROPIC_API_KEY:
        return JsonResponse({'error': 'AI service not configured. Missing API key.'}, status=500)

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=api_messages,
        )
        bot_reply = response.content[0].text
    except Exception as e:
        return JsonResponse({'error': f'AI service error: {str(e)}'}, status=500)

    # Bot reply DB-te save
    ChatMessage.objects.create(session=session, role='bot', text=bot_reply)

    # SPECIALTY_SUGGESTION line thakle detect kore alada field-e pathai
    suggested_specialty = None
    display_reply = bot_reply

    if 'SPECIALTY_SUGGESTION:' in bot_reply:
        parts = bot_reply.split('SPECIALTY_SUGGESTION:')
        display_reply = parts[0].strip()
        specialty_name = parts[1].strip()

        matched = Speciality.objects.filter(name__icontains=specialty_name).first()
        if matched:
            suggested_specialty = {'id': matched.id, 'name': matched.name}

    return JsonResponse({
        'reply': display_reply,
        'suggested_specialty': suggested_specialty,
    })



# Create your views here.
def home(request):
    speciality_filter = request.GET.get('speciality')
    location_filter = request.GET.get('location')

    if speciality_filter:
            doctors = doctors.filter(speciality__id=speciality_filter)

    
    context = {
        'featured_doctors': Doctor.objects.filter(is_verified=True).order_by('-rating')[:3],
        'top_specialities': Speciality.objects.annotate(doctor_count=Count('specialities', filter=Q(specialities__is_verified=True)))[:8],
        'specialities': Speciality.objects.all(),
    
    }
    return render(request, 'healthcare/home.html', context)

def patient_signup(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            return render(request, 'healthcare/patient_signup.html', {'error': 'Passwords do not match'})

        if User.objects.filter(email=email).exists():
            return render(request, 'healthcare/patient_signup.html', {'error': 'Email already exists'})

        if Patient.objects.filter(phone=phone).exists():
            return render(request, 'healthcare/patient_signup.html', {'error': 'Phone number already exists'})

        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name,
        )

        Patient.objects.create(user=user, phone=phone) 

        login(request, user)
        messages.success(request, 'Account created successfully')
        return redirect('home')
    else:
        return render(request, 'healthcare/patient_signup.html')


def patient_login(request):
    if request.method == 'POST':
        login_input = request.POST.get('login_input')
        password = request.POST.get('password')

        user = None

        if '@' in login_input:
            try:
                matched_user = User.objects.get(email=login_input)
                user = authenticate(request, username=matched_user.username, password=password)
            except User.DoesNotExist:
                user = None
        else:
            try:
                patient = Patient.objects.get(phone=login_input) 
                user = authenticate(request, username=patient.user.username, password=password)  
            except Patient.DoesNotExist:  
                user = None

        if user is not None:
            login(request, user)
            messages.success(request, 'Logged in successfully')
            return redirect('home')
        else:
            return redirect('patient_login')

    else:
        return render(request, 'healthcare/patient_login.html')
    
@login_required
def patient_profile(request):
    try:
        patient = request.user.patient_profile
    except patient.DoesNotExist:
        return redirect('patient_login')

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        date_of_birth = request.POST.get('date_of_birth')
        gender = request.POST.get('gender')

        full_name = request.POST.get('full_name')
        if full_name:
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            request.user.first_name = first_name
            request.user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            request.user.save()

        patient.phone = phone
        patient.address = address
        patient.date_of_birth = date_of_birth
        patient.gender = gender

        if request.FILES.get('photo'):
            patient.photo = request.FILES.get('photo')

        patient.save()
        messages.success(request, 'Profile updated successfully')
        return redirect('patient_profile')

    medical_records = patient.records.all().order_by('-created_at')
    
    return render(request, 'healthcare/patient_profile.html', {
        'patient': patient,
        'medical_records': medical_records,

    })

@login_required
def view_patient_history(request, patient_id):
    doctor = request.user.doctor_profile

    patient = get_object_or_404(Patient, id=patient_id)
    medical_reports = patient.records.all().order_by('-created_at')

    context = {
        'patient': patient,
        'medical_reports': medical_reports,
    }
    return render(request, 'healthcare/view_patient_history.html', context)




def patient_logout(request):
    logout(request)
    messages.success(request, 'Logged out successfully')
    return redirect('home')

               

def doctor_signup(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        speciality = request.POST.get('speciality')   
        hospital = request.POST.get('hospital')
        qualification = request.POST.get('qualification')
        bmdc_number = request.POST.get('bmdc_number')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        context = {
            'specialities': Speciality.objects.all(),  
            'hospitals': Hospital.objects.all(),         
        }

        if password1 != password2:
            context['error'] = 'Passwords do not match'
            return render(request, 'healthcare/doctor_signup.html', context)

        if User.objects.filter(email=email).exists():
            context['error'] = 'Email already exists'
            return render(request, 'healthcare/doctor_signup.html', context)

        if Doctor.objects.filter(phone=phone).exists():
            context['error'] = 'Phone number already exists'
            return render(request, 'healthcare/doctor_signup.html', context)

        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name,
        )

        Doctor.objects.create( 
            title=title,
            user=user,
            phone=phone,
            speciality_id=speciality,
            hospital_id=hospital,
            qualification=qualification,
            bmdc_number=bmdc_number,
            is_verified=False,
        )

        login(request, user)
        messages.success(request, 'Account created successfully')
        return redirect('doctor_verified')

    context = {
        'specialities': Speciality.objects.all(),
        'hospitals': Hospital.objects.all(),
    }
    return render(request, 'healthcare/doctor_signup.html', context)

def doctor_login(request):
    if request.method == 'POST':
        login_input = request.POST.get('login_input')
        password = request.POST.get('password')
        user = None

        if '@' in login_input:
            try:
                user = User.objects.get(email=login_input)
                user = authenticate(request, username=user.username, password=password)
            except User.DoesNotExist:
                user = None
        else:
            try:
                doctor = Doctor.objects.get(phone=login_input)  
                user = authenticate(request, username=doctor.user.username, password=password) 
            except Doctor.DoesNotExist:  
                user = None

        if user is not None:
            login(request, user)
            messages.success(request, 'Logged in successfully')
            return redirect('doctor_dashboard')
        else:
            return redirect('doctor_login')
    else:
        return render(request, 'healthcare/doctor_login.html')

def doctor_profile(request):
    doctor = request.user.doctor_profile

    if request.method == 'POST':
        title = request.POST.get('title')
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        date_of_birth = request.POST.get('date_of_birth')
        gender = request.POST.get('gender')
        photo = request.FILES.get('photo')
        consultation_fee = request.POST.get('consultation_fee')
        qualification = request.POST.get('qualification')
        selected_days = request.POST.getlist('available_days')
        doctor.available_days = ', '.join(selected_days)
        doctor.morning_hours = request.POST.get('morning_hours')
        doctor.afternoon_hours = request.POST.get('afternoon_hours')
        doctor.evening_hours = request.POST.get('evening_hours')




        full_name = request.POST.get('full_name')
        if full_name:
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            request.user.first_name = first_name
            request.user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            request.user.save()
            doctor.user.first_name = first_name
            doctor.user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            doctor.user.save()

        doctor.phone = phone
        doctor.address = address
        doctor.date_of_birth = date_of_birth
        doctor.gender = gender
        doctor.consultation_fee = consultation_fee
        doctor.qualification = qualification


        if request.FILES.get('photo'):
            doctor.photo = request.FILES.get('photo')

        doctor.save()
        messages.success(request, 'Profile updated successfully')
        return redirect('doctor_profile')
    context = {
        'doctor': doctor,
        'all_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
        'doctor_days_list': doctor.available_days.split(', '),
    }
    return render(request, 'healthcare/doctor_profile.html', context)
    
    # return render(request, 'healthcare/doctor_profile.html', {'doctor': doctor})

def doctor_logout(request):
    logout(request)
    messages.success(request, 'Logged out successfully')
    return redirect('home')

def doctor_verified(request):
    return render(request, 'healthcare/doctor_verified.html')


def doctors_page(request):
    doctors = Doctor.objects.filter(is_verified=True)
    total_count = doctors.count()

    speciality_filter = request.GET.get('speciality')
    location_filter = request.GET.get('location')
    hospital_filter = request.GET.get('hospital')
    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')

    if speciality_filter:
        doctors = doctors.filter(speciality__id=speciality_filter)

    if hospital_filter:
        doctors = doctors.filter(hospital__id=hospital_filter)

    if location_filter and location_filter != 'Current Location':
        doctors = doctors.filter(hospital__address__icontains=location_filter)

    doctor_list = []

    if user_lat and user_lng:
        user_location = (float(user_lat), float(user_lng))
        for doctor in doctors:
            hospital_location = (doctor.hospital.latitude, doctor.hospital.longitude)
            distance_km = geodesic(user_location, hospital_location).km
            doctor_list.append({'doctor': doctor, 'distance_km': round(distance_km, 1)})
        doctor_list.sort(key=lambda item: item['distance_km'])
    else:
        doctor_list = [{'doctor': d, 'distance_km': None} for d in doctors]

    context = {
        'doctor_list': doctor_list,
        'specialities': Speciality.objects.all(),
        'total_count': total_count,
        'selected_specialty': speciality_filter,
        'selected_location': location_filter,
        'has_location': bool(user_lat and user_lng),
    }
    return render(request, 'healthcare/doctors.html', context)

# def hospitals_page(request):
#     hospitals = Hospital.objects.all()

#     location_filter = request.GET.get('location')
#     if location_filter:
#         hospitals = hospitals.filter(address__icontains=location_filter)

#     context = {
#         'hospitals': hospitals,
#         'selected_location': location_filter,
#     }     

#     return render(request, 'healthcare/hospitals.html', context)

def hospitals_page(request):
    hospitals = Hospital.objects.all()

    location_filter = request.GET.get('location')
    emergency_only = request.GET.get('emergency') 
    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')

    if location_filter:
        hospitals = hospitals.filter(address__icontains=location_filter)

    if emergency_only:
        hospitals = hospitals.filter(has_emergency=True)

    has_location = bool(user_lat and user_lng)
    hospital_list = []

    if has_location:
        try:
            user_location = (float(user_lat), float(user_lng))
            for hospital in hospitals:
                if hospital.latitude and hospital.longitude:
                    hospital_location = (hospital.latitude, hospital.longitude)
                    distance_km = geodesic(user_location, hospital_location).km
                    hospital_list.append({'hospital': hospital, 'distance_km': round(distance_km, 1)})
                else:
                    hospital_list.append({'hospital': hospital, 'distance_km': None})
            hospital_list.sort(key=lambda item: (item['distance_km'] is None, item['distance_km']))
        except ValueError:
            hospital_list = [{'hospital': h, 'distance_km': None} for h in hospitals]
            has_location = False
    else:
        hospital_list = [{'hospital': h, 'distance_km': None} for h in hospitals]

    context = {
        'hospital_list': hospital_list,
        'selected_location': location_filter,
        'emergency_only': emergency_only,
        'has_location': has_location,
    }
    return render(request, 'healthcare/hospitals.html', context)

def specialties_page(request):
    search_query = request.GET.get('search_query')

    specialities = Speciality.objects.annotate(doctor_count=Count('specialities', filter=Q(specialities__is_verified=True)))
    if search_query:
        specialities = specialities.filter(name__icontains=search_query)

    context = {
        'specialities': specialities,
        'search_query': search_query,
    }
    return render(request, 'healthcare/speciality.html', context)


# def blog_page(request):
#     return render(request, 'healthcare/blog.html')

def blog_list(request):
    blogs = Blog.objects.all()
    return render(request, 'healthcare/blog.html', {'blogs': blogs})
 
 
def blog_detail(request, slug):
    blog = get_object_or_404(Blog, slug=slug)
    related_blogs = Blog.objects.filter(category=blog.category).exclude(id=blog.id)[:3]
    return render(request, 'healthcare/blog_detail.html', {
        'blog': blog,
        'related_blogs': related_blogs,
    })

def about_page(request):
    context = {
        'verified_doctor_count': Doctor.objects.filter(is_verified=True).count(),
        'hospital_count': Hospital.objects.count(),
        'happy_patient_count': Appointment.objects.filter(status='completed').count(),

    }
    return render(request, 'healthcare/about.html', context)

@login_required

def book_appointment(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)

    try:
        patient = request.user.patient_profile
    except:
        messages.error(request, 'Only patients can book appointments.')
        return redirect('doctors')

    if request.method == 'POST':
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        reason = request.POST.get('reason')

        Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason=reason,
            status='pending',
        )

        messages.success(request, 'Appointment request sent! Waiting for doctor confirmation.')
        return redirect('patient_appointments')

    return render(request, 'healthcare/book_appointment.html', {'doctor': doctor})

@login_required
def patient_appointments(request):
    patient = request.user.patient_profile
    appointments = patient.appointments.all().order_by('-appointment_date')

    return render(request, 'healthcare/patient_appointments.html', {'appointments': appointments})


def calculate_age(date_of_birth):
    if not date_of_birth:
        return 'N/A'
    today = date.today()
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


@login_required
def doctor_dashboard(request):
    try:
        doctor = request.user.doctor_profile
    except:
        messages.error(request, 'Only doctors can access the dashboard.')
        return redirect('home')

    today = timezone.now().date()
    all_appointments = doctor.appointments.all()

    todays_appointments = all_appointments.filter(appointment_date=today).order_by('appointment_time')
    pending_count = all_appointments.filter(status='pending').count()

    this_month_earnings = all_appointments.filter(
        status='completed',
        appointment_date__month=today.month,
        appointment_date__year=today.year
    ).aggregate(total=Sum('doctor__consultation_fee'))['total'] or 0

   
    appointments_with_age = []
    for appt in todays_appointments:
        appointments_with_age.append({
            'appointment': appt,
            'age': calculate_age(appt.patient.date_of_birth),
        })

    context = {
        'doctor': doctor,
        'todays_appointments': appointments_with_age,
        'todays_patient_count': todays_appointments.count(),
        'pending_count': pending_count,
        'this_month_earnings': this_month_earnings,
    }
    return render(request, 'healthcare/doctor_dashboard.html', context)

# @login_required
# def doctor_dashboard(request):
#     try:
#         doctor = request.user.doctor_profile
#     except:
#         messages.error(request, 'Only doctors can access the dashboard.')
#         return redirect('home')

#     appointments = doctor.appointments.all().order_by('-appointment_date')

#     context = {
#         'doctor': doctor,
#         'appointments': appointments,
#         'pending_count': appointments.filter(status='pending').count(),
#     }
#     return render(request, 'healthcare/doctor_dashboard.html', context)


@login_required
def update_appointment_status(request, appointment_id, new_status):
    appointment = get_object_or_404(Appointment, id=appointment_id)

    if appointment.doctor.user != request.user:
        messages.error(request, 'You are not authorized to update this appointment.')
        return redirect('doctor_dashboard')

    if new_status in ['accepted', 'rejected', 'completed']:
        appointment.status = new_status
        appointment.save()
        messages.success(request, f'Appointment marked as {new_status}.')

    return redirect('doctor_dashboard')

@login_required

def medical_report(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)

    if appointment.doctor.user != request.user:
        messages.error(request, 'You are not authorized to view this report.')
        return redirect('doctor_dashboard')

    if request.method == 'POST':
        diagnosis = request.POST.get('diagnosis')
        prescribed_medicines = request.POST.get('prescribed_medicines')
        notes = request.POST.get('notes')
        MedicalRecord.objects.create(
            appointment=appointment,
            patient=appointment.patient,
            doctor=appointment.doctor,
            diagnosis=diagnosis,
            prescription=prescribed_medicines,
            notes=notes,
        )
        appointment.status = 'completed'
        appointment.save()
        messages.success(request, 'Medical report submitted successfully.')
        return redirect('doctor_dashboard')

    return render(request, 'healthcare/medical_report.html', {'appointment': appointment})


@login_required
def doctor_all_appointments(request):
    try:
        doctor = request.user.doctor_profile
    except:
        messages.error(request, 'Only doctors can view this page.')
        return redirect('home')

    appointments = doctor.appointments.all().order_by('-appointment_date', '-appointment_time')

    appointments_with_age = []
    for appt in appointments:
        appointments_with_age.append({
            'appointment': appt,
            'age': calculate_age(appt.patient.date_of_birth),
        })

    context = {
        'doctor': doctor,
        'appointments_with_age': appointments_with_age,
    }
    return render(request, 'healthcare/doctor_all_appointments.html', context)


@login_required
def doctor_patients(request):
    try:
        doctor = request.user.doctor_profile
    except:
        messages.error(request, 'Only doctors can view this page.')
        return redirect('home')
    patient_ids = doctor.appointments.values_list('patient_id', flat=True).distinct()
    patients = Patient.objects.filter(id__in=patient_ids)
    context = {
        'doctor': doctor,
        'patients': patients,
    }
    return render(request, 'healthcare/doctor_patients.html', context)

@login_required
def patient_dashboard(request):
    try:
        patient = request.user.patient_profile
    except:
        messages.error(request, 'Only patients can view this page.')
        return redirect('home')

    today = timezone.now().date()
    all_appointments = patient.appointments.all()

    upcoming_appointments = all_appointments.filter(appointment_date__gte=today, status__in=['pending','accepted']).order_by('appointment_time', 'appointment_date')
    recent_records = patient.records.all().order_by('-created_at')[:3]
    context = {
        'patient': patient,
        'upcoming_appointments': upcoming_appointments,
        'total_appointments': all_appointments.count(),
        'pending_appointments': all_appointments.filter(status='pending').count(),
        'completed_appointments': all_appointments.filter(status='completed').count(),
        'recent_records': recent_records,

    }
    return render(request, 'healthcare/patient_dashboard.html', context)

@login_required
def patient_full_history(request):
    try:
        patient = request.user.patient_profile
    except:
        messages.error(request, 'Only patients can view this page.')
        return redirect('home')

    records = patient.records.all().order_by('-created_at')
    context = {
        'patient': patient,
        'records': records,
    }
    return render(request, 'healthcare/patient_full_history.html', context)


def emergency_page(request):
    hospitals = Hospital.objects.filter(has_emergency=True)

    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')

    hospital_list = []

    if user_lat and user_lng:
        user_location = (float(user_lat), float(user_lng))
        for hospital in hospitals:
            hospital_location = (hospital.latitude, hospital.longitude)
            distance_km = geodesic(user_location, hospital_location).km
            hospital_list.append({'hospital': hospital, 'distance_km': round(distance_km, 1)})
        hospital_list.sort(key=lambda item: item['distance_km'])
    else:
        hospital_list = [{'hospital': h, 'distance_km': None} for h in hospitals]

    context = {
        'hospital_list': hospital_list,
        'has_location': bool(user_lat and user_lng),
    }
    return render(request, 'healthcare/emergency.html', context)