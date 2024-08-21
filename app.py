import logging
import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SendGridMail  # Rename import
from sqlalchemy.exc import IntegrityError
from twilio.rest import Client

# Logging config
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Application Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

# Flask extensions initialization
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)

# Mail Configuration for SendGrid SMTP
app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'apikey'  # This is the literal string "apikey"
app.config['MAIL_PASSWORD'] = os.getenv('SENDGRID_API_KEY')
app.config['MAIL_DEFAULT_SENDER'] = 'info@triddle.dev'

# Twilio Configuration
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
client = Client(account_sid, auth_token)


# Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)  # Add this line
    password = db.Column(db.String(60), nullable=False)


class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    frequency = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Removed dosage, added frequency


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


# Create the database tables
with app.app_context():
    db.create_all()


# Functions for sending reminders
def send_sms_reminder(to, body):
    client.messages.create(
        to=to,  # Pass the phone number directly
        from_='+18333420817',  # Your Twilio phone number
        body=body
    )


def send_reminder_email(subject, recipient, body):
    message = SendGridMail(
        from_email='info@triddle.dev',
        to_emails=recipient,
        subject=subject,
        html_content=body
    )
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(f'Status Code: {response.status_code}')
        print(f'Body: {response.body}')
        print(f'Headers: {response.headers}')
    except Exception as e:
        print(f'An error occurred: {str(e)}')


# Routes
@app.route('/test_email')
@login_required
def test_email():
    send_reminder_email(
        subject='Test Email from Task Reminder App',
        recipient=current_user.email,
        body='This is a test email to verify that SendGrid SMTP relay is working.'
    )
    flash('Test email sent!', 'success')
    return redirect(url_for('home'))


@app.route('/send_reminders')
@login_required
def send_reminders():
    if current_user.phone:  # Ensure the user has a phone number
        send_sms_reminder(
            to=current_user.phone,
            body='This is a test SMS to verify that SMS reminders are working.'
        )
        flash('SMS reminders have been sent!', 'success')
    else:
        flash('No phone number on file. Please update your profile.', 'warning')
    return redirect(url_for('home'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if the email already exists
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already registered. Please use a different email.', 'danger')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        try:
            db.session.commit()
            flash('Your account has been created! You can now log in.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()  # Rollback the transaction if there's an error
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('register'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return render_template('logout.html')  # Render the logout confirmation page


@app.route('/medications')
@login_required
def medications():
    meds = Medication.query.filter_by(user_id=current_user.id).all()
    return render_template('medications.html', medications=meds)


@app.route('/add_medication', methods=['GET', 'POST'])
@login_required
def add_medication():
    if request.method == 'POST':
        name = request.form.get('name')
        frequency = request.form.get('frequency')
        new_med = Medication(name=name, frequency=frequency, user_id=current_user.id)
        db.session.add(new_med)
        db.session.commit()
        flash('Medication added successfully!', 'success')
        return redirect(url_for('medications'))
    return render_template('add_medication.html')


@app.route('/delete_medication/<int:id>')
@login_required
def delete_medication(id):
    med = Medication.query.get_or_404(id)
    if med.user_id != current_user.id:
        abort(403)
    db.session.delete(med)
    db.session.commit()
    flash('Medication deleted successfully!', 'success')
    return redirect(url_for('medications'))


@app.route('/appointments')
@login_required
def appointments():
    appts = Appointment.query.filter_by(user_id=current_user.id).all()
    return render_template('appointments.html', appointments=appts)


@app.route('/add_appointment', methods=['GET', 'POST'])
@login_required
def add_appointment():
    if request.method == 'POST':
        location = request.form.get('location')
        date_str = request.form.get('date')

        # Convert the date string to a datetime object
        date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')

        new_appt = Appointment(location=location, date=date, user_id=current_user.id)
        db.session.add(new_appt)
        db.session.commit()
        flash('Appointment added successfully!', 'success')
        return redirect(url_for('appointments'))
    return render_template('add_appointment.html')


@app.route('/delete_appointment/<int:id>')
@login_required
def delete_appointment(id):
    appt = Appointment.query.get_or_404(id)
    if appt.user_id != current_user.id:
        abort(403)
    db.session.delete(appt)
    db.session.commit()
    flash('Appointment deleted successfully!', 'success')
    return redirect(url_for('appointments'))


@app.route('/get_medication_suggestions')
def get_medication_suggestions():
    term = request.args.get('term')
    if not term:
        return jsonify([])

    try:
        # Query RxNorm API with the correct endpoint
        url = "https://rxnav.nlm.nih.gov/REST/drugs.json"
        params = {
            'name': term,
            'expand': 'psn'  # Optional: Expand results to include prescribable names
        }
        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        suggestions = []

        # Navigate the JSON response to extract the drug names
        if 'drugGroup' in data and 'conceptGroup' in data['drugGroup']:
            for group in data['drugGroup']['conceptGroup']:
                if 'conceptProperties' in group:
                    for concept in group['conceptProperties']:
                        suggestions.append(concept['name'])  # Append the drug name to suggestions

        logging.info(f"Query: {term}, Suggestions: {suggestions}")
        return jsonify(suggestions)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error querying RxNorm API: {e}")
    return jsonify([])


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
