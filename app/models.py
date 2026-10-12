from .create_app import db

class Admin(db.Model): 
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    admin_name = db.Column(db.String(100))

class Student(db.Model):
    __tablename__ = 'student'
    Student_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Student_rollno = db.Column(db.String(20), unique=True, nullable=False)
    Student_name = db.Column(db.String(100), nullable=False)
    Student_email = db.Column(db.String(100), unique=True, nullable=False) 
    Student_password = db.Column(db.String(100), nullable=False)
    Student_phone = db.Column(db.String(15), nullable=False) 
    Student_address = db.Column(db.String(200), nullable=False)
    Student_branch = db.Column(db.String(50), nullable=False)
    Student_semester = db.Column(db.Integer, nullable=False)
    Student_CGPA_Scale = db.Column(db.String(20), nullable=False)
    # 10 / 4 / 100 / Other
    Student_CGPA = db.Column(db.Float, nullable=False)
    Student_college = db.Column(db.String(100), nullable=False)
    Student_clg_NIRF = db.Column(db.Integer, nullable=False)
    Student_blocked = db.Column(db.Boolean, default=False)
    Student_skills = db.Column(db.String(1000), nullable=True)
    Student_jobs_applied = db.Column(db.Integer, default=0)
    Student_interviews = db.Column(db.Integer, default=0)
    Student_offers = db.Column(db.Integer, default=0)


class Company(db.Model): 
    __tablename__ = 'company'
    Company_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Company_name = db.Column(db.String(100), unique=True, nullable=False)
    Company_email = db.Column(db.String(100), unique=True, nullable=False) 
    Company_password = db.Column(db.String(100), nullable=False)
    Company_phone = db.Column(db.String(15), unique=True, nullable=False) 
    Company_address = db.Column(db.String(200), nullable=False)
    Company_website = db.Column(db.String(150), unique=True, nullable=False)
    Company_description = db.Column(db.String(1000), nullable=False)
    Company_blocked = db.Column(db.Boolean, default=False)
    Company_no_of_students_hired = db.Column(db.Integer, default=0)
    Company_approved = db.Column(db.Boolean, default=False)


class Job_Position(db.Model): 
    __tablename__ = 'job_position'
    Job_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Job_title = db.Column(db.String(100), nullable=False)
    Job_description = db.Column(db.String(1000), nullable=False)
    Job_requirements = db.Column(db.String(1000), nullable=False)
    Job_location = db.Column(db.String(100), nullable=False)
    Job_salary = db.Column(db.Float, nullable=False)
    Job_type = db.Column(db.String(50), nullable=False) # e.g., Full-time, Part-time, Internship
    Company_id = db.Column(db.Integer, db.ForeignKey('company.Company_id'), nullable=False)
    Company = db.relationship('Company', backref=db.backref('job_positions', lazy=True))

class Application(db.Model):
    __tablename__ = 'application'

    Application_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    Student_id = db.Column(
        db.Integer,
        db.ForeignKey('student.Student_id'),
        nullable=False
    )

    Post_id = db.Column(
        db.Integer,
        db.ForeignKey('company_post.Post_id'),
        nullable=False
    )

    Application_status = db.Column(
        db.String(50),
        default='Pending'
    )

    Student = db.relationship(
        'Student',
        backref=db.backref('applications', lazy=True)
    )

    Post = db.relationship(
        'CompanyPost',
        backref=db.backref('applications', lazy=True)
    )

class CompanyPost(db.Model):
    __tablename__ = 'company_post'

    Post_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Company_id = db.Column(db.Integer, db.ForeignKey('company.Company_id'), nullable=False)

    Job_title = db.Column(db.String(100), nullable=False)
    Job_description = db.Column(db.String(2000), nullable=False)

    Min_CGPA_10 = db.Column(db.Float, nullable=True)
    Min_CGPA_4 = db.Column(db.Float, nullable=True)
    Min_Percentage = db.Column(db.Float, nullable=True)

    Eligible_Branch = db.Column(db.String(100), nullable=False)
    Course = db.Column(db.String(50), nullable=False)
    Eligible_Year = db.Column(db.String(10), nullable=False)

    Skills_required = db.Column(db.String(500), nullable=False)
    Responsibilities = db.Column(db.String(2000), nullable=False)

    Application_deadline = db.Column(db.Date, nullable=False)
    Vacancies = db.Column(db.Integer, nullable=False)
    Salary = db.Column(db.String(100), nullable=False)
    Work_type = db.Column(db.String(30), nullable=False)
    Job_type = db.Column(db.String(30), nullable=False)
    Contract_period = db.Column(db.String(50), nullable=False)

    Admin_approved = db.Column(db.Boolean, default=False)

    Company = db.relationship(
        'Company',
        backref=db.backref('posts', lazy=True)
    )
    

class Placement(db.Model):
    __tablename__ = 'placement'

    Placement_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    Student_id = db.Column(
        db.Integer,
        db.ForeignKey('student.Student_id'),
        nullable=False
    )

    Company_id = db.Column(
        db.Integer,
        db.ForeignKey('company.Company_id'),
        nullable=False
    )

    Post_id = db.Column(
        db.Integer,
        db.ForeignKey('company_post.Post_id'),
        nullable=False
    )

    Placement_date = db.Column(db.Date, nullable=False)

    Student = db.relationship('Student')
    Company = db.relationship('Company')
    Post = db.relationship('CompanyPost')    



class Interview(db.Model): 
    __tablename__ = 'interview'
    Interview_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Student_id = db.Column(db.Integer, db.ForeignKey('student.Student_id'), nullable=False)
    Company_id = db.Column(db.Integer, db.ForeignKey('company.Company_id'), nullable=False)
    Job_id = db.Column(db.Integer, db.ForeignKey('job_position.Job_id'), nullable=False)
    Interview_date = db.Column(db.Date, nullable=False)
    Interview_mode = db.Column(db.String(50), nullable=False) # e.g., Online, Offline
    Interview_status = db.Column(db.String(50), nullable=False, default='Scheduled') # e.g., Scheduled, Completed, Cancelled
    Student = db.relationship('Student', backref=db.backref('interviews', lazy=True))
    Company = db.relationship('Company', backref=db.backref('interviews', lazy=True))
    Job_Position = db.relationship('Job_Position', backref=db.backref('interviews', lazy=True))


class Reported_Student(db.Model): 
    __tablename__ = 'reported_student'
    Report_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Student_id = db.Column(db.Integer, db.ForeignKey('student.Student_id'), nullable=False)
    Report_reason = db.Column(db.String(500), nullable=False)
    Reported_by_Company = db.Column(db.String(100), nullable=False)
    Student = db.relationship('Student', backref=db.backref('reports', lazy=True))


class AdminMessage(db.Model):
    __tablename__ = 'admin_messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_name = db.Column(db.String(100), nullable=False)
    sender_email = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(2000), nullable=False)
    is_solved = db.Column(db.Boolean, default=False)


class PendingStudentRegistration(db.Model):
    __tablename__ = 'pending_student_registration'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), nullable=False, index=True)
    payload_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
