from flask import render_template, current_app as app, url_for, flash
from flask import request, redirect, session
from requests import post
import json
import os
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr


from .create_app import oauth
from .models import (
    Application,
    CompanyPost,
    Job_Position,
    Student,
    Company,
    Admin,
    db,
    AdminMessage,
    PendingStudentRegistration
)


ADMIN_SECRET_KEY = "abhi"



@app.route('/') 
def home(): 
    return render_template('home.html')


@app.route('/about') 
def about(): 
    return render_template('about.html')



@app.route('/terms_and_conditions')
def terms_and_conditions():
    return render_template('terms_and_conditions.html')


########################################################################################
# Student Routes
########################################################################################


@app.route('/student/')
@app.route('/student/home')
def student_home():
    return render_template('student_home.html')



@app.route('/auth/google')
def google_verify_email():
    """Start Google OpenID Connect verification for student registration."""
    google = oauth.create_client('google')
    if not google or not google.client_id or not google.client_secret:
        flash('Google verification is not configured yet. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your environment.', 'error')
        return redirect(url_for('student_register'))
    redirect_uri = url_for('google_verify_callback', _external=True, _scheme='https' if request.is_secure else 'http')
    return google.authorize_redirect(redirect_uri, prompt='select_account')


@app.route('/auth/google/callback')
def google_verify_callback():
    """Accept only a Google account whose ID token confirms email_verified=true."""
    google = oauth.create_client('google')
    if not google:
        flash('Google verification is not configured. Please contact the site administrator.', 'error')
        return redirect(url_for('student_register'))
    try:
        token = google.authorize_access_token()
        userinfo = token.get('userinfo') or google.userinfo()
        email = (userinfo.get('email') or '').strip().lower()
        verified = userinfo.get('email_verified') is True
        if not email or not verified:
            flash('Google did not confirm that this email address is verified. Try another account.', 'error')
            return redirect(url_for('student_register'))
        session['google_verified_email'] = email
        flash('Google email verified. Complete the registration form using this exact email address.', 'success')
    except Exception:
        app.logger.exception('Google OAuth verification failed')
        flash('Google verification failed. Please try again.', 'error')
    return redirect(url_for('student_register'))


@app.route('/auth/google/cancel')
def google_verify_cancel():
    session.pop('google_verified_email', None)
    flash('Google email verification was cancelled.', 'error')
    return redirect(url_for('student_register'))


@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    verified_email = session.get('google_verified_email')
    if request.method == 'POST':
        submitted_email = request.form.get('Student_email', '').strip().lower()
        if not verified_email or submitted_email != verified_email:
            flash('Verify this exact email address with Google before completing registration.', 'error')
            return redirect(url_for('student_register'))
        if Student.query.filter_by(Student_email=submitted_email).first():
            flash('An account already exists for this email. Please log in instead.', 'error')
            return redirect(url_for('student_login'))
        rollno = request.form.get('Student_rollno', '').strip()
        if Student.query.filter_by(Student_rollno=rollno).first():
            flash('An account already exists for this roll number.', 'error')
            return redirect(url_for('student_register'))

        try:
            payload = {
                'Student_name': request.form['Student_name'].strip(),
                'Student_email': submitted_email,
                'Student_password': request.form['Student_password'],
                'Student_phone': request.form['Student_phone'].strip(),
                'Student_address': request.form['Student_address'].strip(),
                'Student_rollno': rollno,
                'Student_college': request.form['Student_college'].strip(),
                'Student_clg_NIRF': int(request.form['Student_clg_NIRF']),
                'Student_branch': request.form['Student_branch'].strip(),
                'Student_semester': int(request.form['Student_semester']),
                'Student_CGPA_Scale': request.form['Student_CGPA_Scale'],
                'Student_CGPA': float(request.form['Student_CGPA']),
                'Student_skills': request.form.get('Student_skills', '').strip(),
            }
            if not all(payload.get(k) for k in (
                'Student_name', 'Student_email', 'Student_password', 'Student_phone',
                'Student_address', 'Student_rollno', 'Student_college', 'Student_branch'
            )):
                raise ValueError('Required fields are missing.')

            # Replace any previous unconfirmed registration for this email.
            PendingStudentRegistration.query.filter_by(email=submitted_email).delete()
            token = secrets.token_urlsafe(32)
            pending = PendingStudentRegistration(
                token=token,
                email=submitted_email,
                payload_json=json.dumps(payload)
            )
            db.session.add(pending)
            db.session.commit()

            confirm_url = url_for('confirm_student_registration', token=token, _external=True)
            try:
                send_registration_confirmation_email(payload, confirm_url)
            except Exception:
                db.session.delete(pending)
                db.session.commit()
                app.logger.exception('Could not send registration confirmation email')
                flash('We could not send the confirmation email. Check SMTP settings and try again.', 'error')
                return redirect(url_for('student_register'))

            session.pop('google_verified_email', None)
            flash('Registration details received. Open the confirmation link sent to your email to activate your account.', 'success')
            return redirect(url_for('student_register'))
        except (KeyError, ValueError):
            db.session.rollback()
            flash('Please check the form values and try again.', 'error')
        except Exception:
            db.session.rollback()
            app.logger.exception('Student registration confirmation setup failed')
            flash('Registration could not be started. Check whether the email or roll number is already in use.', 'error')

    return render_template('student_register.html', verified_email=verified_email)


def send_registration_confirmation_email(user, confirm_url):
    """Send a registration confirmation email using SMTP settings from environment."""
    host = os.environ.get('MAIL_SERVER', '').strip()
    port = int(os.environ.get('MAIL_PORT', '587'))
    username = os.environ.get('MAIL_USERNAME', '').strip()
    password = os.environ.get('MAIL_PASSWORD', '')
    sender = os.environ.get('MAIL_DEFAULT_SENDER', username).strip()
    sender_name = os.environ.get('MAIL_SENDER_NAME', 'Placement Portal').strip()

    if not all((host, username, password, sender)):
        raise RuntimeError('MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD and MAIL_DEFAULT_SENDER must be configured.')

    html_body = render_template('emails/registration_confirmation.html',
                                user=user, confirm_url=confirm_url,
                                portal_name=sender_name)
    message = EmailMessage()
    message['Subject'] = 'Confirm your Placement Portal registration'
    message['From'] = formataddr((sender_name, sender))
    message['To'] = user['Student_email']
    message.set_content(
        f"Hello {user['Student_name']},\n\n"
        "Please confirm your Placement Portal registration by opening this link:\n"
        f"{confirm_url}\n\n"
        "If you did not request this registration, you can ignore this email."
    )
    message.add_alternative(html_body, subtype='html')

    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as server:
            server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(username, password)
            server.send_message(message)


@app.route('/student/confirm-registration/<token>', methods=['GET', 'POST'])
def confirm_student_registration(token):
    pending = PendingStudentRegistration.query.filter_by(token=token).first()
    if not pending:
        return render_template('registration_confirmation_result.html',
                               success=False,
                               message='This confirmation link is invalid, expired, or has already been used.'), 400

    if request.method == 'GET':
        return render_template('confirm_student_registration.html', token=token, email=pending.email)

    try:
        payload = json.loads(pending.payload_json)
        if Student.query.filter_by(Student_email=pending.email).first():
            db.session.delete(pending)
            db.session.commit()
            return render_template('registration_confirmation_result.html',
                                   success=False,
                                   message='An account already exists for this email. Please log in.')
        if Student.query.filter_by(Student_rollno=payload['Student_rollno']).first():
            db.session.delete(pending)
            db.session.commit()
            return render_template('registration_confirmation_result.html',
                                   success=False,
                                   message='This roll number is already registered. Please contact the portal administrator.')
        student = Student(
            Student_name=payload['Student_name'],
            Student_email=payload['Student_email'],
            Student_password=payload['Student_password'],
            Student_phone=payload['Student_phone'],
            Student_address=payload['Student_address'],
            Student_rollno=payload['Student_rollno'],
            Student_college=payload['Student_college'],
            Student_clg_NIRF=payload['Student_clg_NIRF'],
            Student_branch=payload['Student_branch'],
            Student_semester=payload['Student_semester'],
            Student_CGPA_Scale=payload['Student_CGPA_Scale'],
            Student_CGPA=payload['Student_CGPA'],
            Student_skills=payload.get('Student_skills', ''),
            Student_jobs_applied=0
        )
        db.session.add(student)
        db.session.delete(pending)
        db.session.commit()
        return render_template('registration_confirmation_result.html',
                               success=True,
                               message='Your email is confirmed and your Placement Portal account is now active.')
    except Exception:
        db.session.rollback()
        app.logger.exception('Could not finalize confirmed student registration')
        return render_template('registration_confirmation_result.html',
                               success=False,
                               message='We could not activate your account. Please try again or contact the portal administrator.'), 500


@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'GET':
        return render_template('student_login.html')

    email = request.form['Student_email']
    password = request.form['Student_password']

    student = Student.query.filter_by(Student_email=email).first()

    if student and student.Student_password == password:
        session.clear() 
        session['student_logged_in'] = True
        session['student_id'] = student.Student_id
        session['student_name'] = student.Student_name
        return redirect(url_for('student_dashboard'))

    return redirect(url_for('student_login'))



@app.route('/student/dashboard')
def student_dashboard():
    if not session.get('student_logged_in'):
        return redirect(url_for('student_login'))

    student_id = session.get('student_id')
    student = Student.query.get_or_404(student_id)

    applications = Application.query.filter_by(
        Student_id=student.Student_id
    ).all()

    return render_template(
        'student_dashboard.html',
        User=student,
        applications=applications
    )


@app.route('/student/logout')
def student_logout():   
    session.pop('student_id', None)
    session.pop('student_name', None)
    return redirect(url_for('student_home'))

@app.route('/student/update_profile', methods=['GET', 'POST'])  
def student_update_profile():
    if 'student_id' not in session:
        return redirect(url_for('student_home'))

    student = Student.query.get(session['student_id'])

    if request.method == 'POST':
        student.Student_name = request.form['Student_name']
        student.Student_phone = request.form['Student_phone']
        student.Student_address = request.form['Student_address']
        student.Student_branch = request.form['Student_branch']
        student.Student_semester = int(request.form['Student_semester'])
        student.Student_CGPA = float(request.form['Student_CGPA'])
        student.Student_skills = request.form.get('Student_skills', "")

        db.session.commit()
        return redirect(url_for('student_dashboard'))

    return render_template('student_update_profile.html', User=student)

@app.route('/student/details/<int:student_id>')
def student_details(student_id):
    student = Student.query.get(student_id)
    if not student:
        return render_template('no_such_student.html'), 404
    return render_template('student_details.html', User=student)


@app.route('/student/forgot_password', methods=['GET', 'POST'])
def student_forgot_password():
    if request.method == 'POST':
        email = request.form.get('Student_email')
        
        user = Student.query.filter_by(Student_email=email).first()
        
        if user:
            user.Student_password = "" 
            db.session.commit()
            
            return redirect(url_for('student_reset_password', email=email))
            
    return render_template('student_forgot_password.html')

@app.route('/student/reset_password/<email>', methods=['GET', 'POST'])
def student_reset_password(email):
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        user = Student.query.filter_by(Student_email=email).first()
        
        if user:
            user.Student_password = new_password # Update with new password
            db.session.commit()
            return redirect(url_for('student_login'))
            
    return render_template('student_reset_password.html', email=email)


########################################################################################
# Admin Routes
########################################################################################




@app.route('/admin/', methods=['GET', 'POST'])
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template('admin_login.html')

    admin_name = request.form.get('admin_name')
    secret_key = request.form.get('secret_key')

    if secret_key == ADMIN_SECRET_KEY:
        session['admin_logged_in'] = True
        session['admin_name'] = admin_name

        return redirect(url_for('admin_home'))

    return redirect(url_for('admin_login'))



@app.route('/admin/home')
def admin_home():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    students = Student.query.all()
    companies = Company.query.all()

    admin_name = session.get('admin_name', 'Admin')

    return render_template(
        'admin_home.html',
        students=students,
        companies=companies,
        admin_name=admin_name
    )



@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


from sqlalchemy import or_

@app.route('/admin/view_students')
def admin_view_students():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    query = request.args.get('q', '').strip()

    if query:
        students = Student.query.filter(
            or_(
                Student.Student_rollno.ilike(f"%{query}%"),
                Student.Student_name.ilike(f"%{query}%"),
                Student.Student_id.ilike(f"%{query}%")
            )
        ).all()
    else:
        students = Student.query.all()

    return render_template(
        'admin_view_students.html',
        students=students,
        query=query
    )


@app.route('/admin/block/<int:sid>')
def admin_block_student(sid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    student = Student.query.get_or_404(sid)
    student.Student_blocked = True
    db.session.commit()

    return redirect(url_for('admin_view_students'))


@app.route('/admin/unblock/<int:sid>')
def admin_unblock_student(sid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    student = Student.query.get_or_404(sid)
    student.Student_blocked = False
    db.session.commit()

    return redirect(url_for('admin_view_students'))



@app.route('/admin/view_companies')
@app.route('/admin/view_company')
def admin_view_companies():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    query = request.args.get('q', '').strip()

    if query:
        companies = Company.query.filter(
            or_(
                Company.Company_name.ilike(f"%{query}%"),
                Company.Company_email.ilike(f"%{query}%"),
                Company.Company_id.ilike(f"%{query}%")
            )
        ).all()
    else:
        companies = Company.query.all()

    return render_template(
        'admin_view_companies.html',
        companies=companies,
        query=query
    )


@app.route('/contact-admin', methods=['GET', 'POST'])
def contact_admin():
    if request.method == 'GET':
        return render_template('contact_admin.html')

    msg = AdminMessage(
        sender_name=request.form['name'],
        sender_email=request.form['email'],
        subject=request.form['subject'],
        message=request.form['message']
    )

    db.session.add(msg)
    db.session.commit()

    return redirect(url_for('contact_admin'))



@app.route('/admin/post/<int:pid>/applications')
def admin_view_application(pid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    post = CompanyPost.query.get_or_404(pid)

    applications = Application.query.filter_by(
        Job_id=post.Post_id
    ).all()

    return render_template(
        'view_application.html',
        post=post,
        applications=applications
    )

@app.route('/admin/messages')
def admin_view_messages():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    messages = AdminMessage.query.order_by(AdminMessage.id.desc()).all()

    return render_template(
        'admin_view_messages.html',
        messages=messages
    )


@app.route('/admin/message/solve/<int:mid>')
def admin_solve_message(mid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    msg = AdminMessage.query.get_or_404(mid)
    msg.is_solved = True
    db.session.commit()

    return redirect(url_for('admin_view_messages'))


@app.route('/admin/message/unsolve/<int:mid>')
def admin_unsolve_message(mid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    msg = AdminMessage.query.get_or_404(mid)
    msg.is_solved = False
    db.session.commit()

    return redirect(url_for('admin_view_messages'))

@app.route('/admin/message/delete/<int:mid>')
def admin_delete_message(mid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    msg = AdminMessage.query.get_or_404(mid)
    db.session.delete(msg)
    db.session.commit()

    return redirect(url_for('admin_view_messages'))







########################################################################################
# Company Routes
########################################################################################

@app.route('/company')
def company_portal():
    return render_template('company_portal.html')


@app.route('/company/register', methods=['GET', 'POST'])
def company_register():
    if request.method == 'GET':
        return render_template('company_register.html')

    company = Company(
        Company_name=request.form['name'],
        Company_email=request.form['email'],
        Company_password=request.form['password'],
        Company_phone=request.form['phone'],
        Company_address=request.form['address'],
        Company_website=request.form['website'],
        Company_description=request.form['description'],
        Company_approved=False,
        Company_blocked=False
    )

    db.session.add(company)
    db.session.commit()

    return redirect(url_for('company_login'))

@app.route('/company/logout')
def company_logout():
    session.clear()
    return redirect(url_for('company_login'))

@app.route('/company/dashboard')
def company_dashboard():
    if not session.get('company_logged_in'):
        return redirect(url_for('company_login'))

    company_id = session.get('company_id')

    if not company_id:
        session.clear()
        return redirect(url_for('company_login'))

    company = Company.query.get(company_id)

    if not company:
        session.clear()
        return redirect(url_for('company_login'))

    posts = CompanyPost.query.filter_by(
        Company_id=company.Company_id
    ).all()

    return render_template(
        'company_dashboard.html',
        company=company,
        drives=posts , 
        today =datetime.today().date()  
    )
    
@app.route('/company/approval-pending')
def company_approval_pending():
    company_id = session.get('company_id')

    if company_id:
        company = Company.query.get(company_id)
        if company and company.Company_approved:
            return redirect(url_for('company_dashboard'))

    return render_template('admin_not_yet_approved_company.html', company=company)

@app.route('/admin/company/allow/<int:cid>')
def admin_allow_company(cid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    company = Company.query.get_or_404(cid)
    company.Company_approved = True
    db.session.commit()

    return redirect(url_for('admin_view_companies'))


@app.route('/company/login', methods=['GET', 'POST'])
def company_login():
    if request.method == 'GET':
        return render_template('company_login.html')

    email = request.form['email']
    password = request.form['password']

    company = Company.query.filter_by(
        Company_email=email,
        Company_password=password
    ).first()

    if not company:
        return redirect(url_for('company_login'))

    if not company.Company_approved:
        return redirect(url_for('company_approval_pending'))

    session['company_logged_in'] = True
    session['company_id'] = company.Company_id   
    return redirect(url_for('company_dashboard'))


@app.route('/admin/companies/pending')
def admin_pending_companies():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    companies = Company.query.filter_by(Company_approved=False).all()
    return render_template('admin_pending_companies.html', companies=companies)



@app.route('/admin/post/approve/<int:pid>')
def admin_approve_post(pid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    post = CompanyPost.query.get_or_404(pid)
    post.Admin_approved = True
    db.session.commit()

    return redirect(url_for('admin_view_applications'))


from datetime import date, datetime

def parse_optional_float(val):
    return float(val) if val and val.strip() != "" else None

@app.route('/company/create-drive', methods=['GET', 'POST'])
def company_create_drive():
    if not session.get('company_logged_in'):
        return redirect(url_for('company_login'))

    if request.method == 'GET':
        return render_template('company_create_drive.html')

    from datetime import datetime

    deadline_date = datetime.strptime(
        request.form['deadline'], '%Y-%m-%d'
    ).date()

    post = CompanyPost(
        Company_id=session['company_id'],
        Job_title=request.form['job_title'],
        Job_description=request.form['job_description'],

        Min_CGPA_10=parse_optional_float(request.form.get('cgpa_10')),
        Min_CGPA_4=parse_optional_float(request.form.get('cgpa_4')),
        Min_Percentage=parse_optional_float(request.form.get('percentage')),

        Eligible_Branch=request.form['branch'],
        Course=request.form['course'],
        Eligible_Year=request.form['year'],

        Skills_required=request.form['skills'],
        Responsibilities=request.form['responsibilities'],

        Application_deadline=deadline_date,
        Vacancies=request.form['vacancies'],
        Salary=request.form['salary'],
        Work_type=request.form['work_type'],
        Job_type=request.form['job_type'],
        Contract_period=request.form['contract_period'],

        Admin_approved=False
    )

    db.session.add(post)
    db.session.commit()

    return redirect(url_for('company_dashboard'))

from sqlalchemy import and_

@app.route('/company/post/<int:pid>/applications')
def company_view_applications(pid):
    if not session.get('company_logged_in'):
        return redirect(url_for('company_login'))

    post = CompanyPost.query.get_or_404(pid)

    if post.Company_id != session.get('company_id'):
        return redirect(url_for('company_dashboard'))

    sid = request.args.get('sid', '').strip()
    college = request.args.get('college', '').strip()
    min_cgpa = request.args.get('min_cgpa', '').strip()
    max_cgpa = request.args.get('max_cgpa', '').strip()

    query = Application.query.join(Student).filter(
        Application.Post_id == pid
    )

    if sid:
        query = query.filter(Student.Student_id == int(sid))

    if college:
        query = query.filter(
            Student.Student_college.ilike(f"%{college}%")
        )

    if min_cgpa:
        query = query.filter(Student.Student_CGPA >= float(min_cgpa))

    if max_cgpa:
        query = query.filter(Student.Student_CGPA <= float(max_cgpa))

    applications = query.all()

    return render_template(
        'company_view_applications.html',
        post=post,
        applications=applications
    )

@app.route('/admin/applications')
def admin_view_applications():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    posts = CompanyPost.query.all()

    return render_template(
        'admin_view_applications.html',
        posts=posts
    )



    

@app.route('/admin/post/disallow/<int:pid>')
def admin_disallow_post(pid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    post = CompanyPost.query.get_or_404(pid)

    post.Admin_approved = False
    db.session.commit()

    return redirect(url_for('admin_view_applications'))

@app.route('/admin/company/block/<int:cid>')
def admin_block_company(cid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    company = Company.query.get_or_404(cid)

    company.Company_blocked = True
    company.Company_approved = False

    CompanyPost.query.filter_by(
        Company_id=company.Company_id
    ).update(
        {CompanyPost.Admin_approved: False}
    )

    db.session.commit()

    return redirect(url_for('admin_view_companies'))


@app.route('/admin/company/unblock/<int:cid>')
def admin_unblock_company(cid):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    company = Company.query.get_or_404(cid)
    company.Company_blocked = False

    db.session.commit()
    return redirect(url_for('admin_view_companies'))



@app.route('/student/apply/<int:pid>', methods=['POST'])
def student_apply_post(pid):
    if not session.get('student_logged_in'):
        return redirect(url_for('student_login'))

    student_id = session.get('student_id')

    post = CompanyPost.query.filter_by(
        Post_id=pid,
        Admin_approved=True
    ).first_or_404()

    existing = Application.query.filter_by(
        Student_id=student_id,
        Post_id=pid
    ).first()

    if existing:
        return redirect(url_for('student_view_post_details', pid=pid))

    application = Application(
        Student_id=student_id,
        Post_id=pid,
        Application_status='Applied'
    )

    db.session.add(application)

    student = Student.query.get(student_id)
    student.Student_jobs_applied += 1

    db.session.commit()

    return redirect(url_for('student_dashboard'))


@app.route('/student/posts')
def student_view_posts():
    if not session.get('student_logged_in'):
        return redirect(url_for('student_login'))

    student_id = session.get('student_id')

    posts = CompanyPost.query.filter_by(
        Admin_approved=True
    ).order_by(CompanyPost.Application_deadline).all()

    applied_post_ids = {
        app.Post_id
        for app in Application.query.filter_by(Student_id=student_id).all()
    }

    return render_template(
        'student_view_posts.html',
        posts=posts,
        applied_post_ids=applied_post_ids
    )

    
    
@app.route('/student/post/<int:pid>')
def student_view_post_details(pid):
    if not session.get('student_logged_in'):
        return redirect(url_for('student_login'))

    student_id = session.get('student_id')

    post = CompanyPost.query.filter_by(
        Post_id=pid,
        Admin_approved=True
    ).first_or_404()

    already_applied = Application.query.filter_by(
        Student_id=student_id,
        Post_id=pid
    ).first() is not None

    return render_template(
        'student_post_details.html',
        post=post,
        already_applied=already_applied
    )