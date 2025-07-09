from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, MoodEntry
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask import jsonify, make_response
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import calendar
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mood_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Inicjalizacja bazy danych
with app.app_context():
    db.create_all()


# Funkcje pomocnicze
def create_mood_chart(mood_data):
    # Dla skali 1-5
    labels = ['Bardzo źle (1)', 'Źle (2)', 'Neutralnie (3)', 'Dobrze (4)', 'Świetnie (5)']
    colors = ['#e74c3c', '#f39c12', '#3498db', '#2ecc71', '#27ae60']

    counts = [0, 0, 0, 0, 0]  # Dla wartości 1-5
    for score in mood_data:
        counts[score - 1] += 1  # -1 bo indeksy od 0

    plt.figure(figsize=(8, 8))
    plt.pie(counts,
            labels=labels,
            colors=colors,
            autopct=lambda p: f'{p:.1f}%\n({int(round(p * sum(counts)/100))}%)',
            startangle = 90,
            wedgeprops = {'linewidth': 1, 'edgecolor': 'white'})
    plt.title('Rozkład nastroju (ostatnie 7 dni)', pad=20)

    img = BytesIO()
    plt.savefig(img, format='png', dpi=100, bbox_inches='tight')
    img.seek(0)
    plt.close()

    return base64.b64encode(img.getvalue()).decode('utf8')


# Trasy
@app.route('/')
@login_required
def index():
    quotes = [
        {"text": "Największą słabością jest poddawanie się. Najpewniejszą drogą do sukcesu jest próbowanie jeszcze raz.", "author": "Thomas Edison"},
        {"text": "Sukces to suma małych wysiłków powtarzanych dzień po dniu.", "author": "Robert Collier"},
        {"text": "Jesteś silniejszy niż myślisz i zdolny do więcej niż sobie wyobrażasz.", "author": "Nieznany"},
        {"text": "Każdy dzień to nowa szansa, by zmienić swoje życie.", "author": "Nieznany"},
        {"text": "Małe kroki każdego dnia prowadzą do wielkich rezultatów.", "author": "Nieznany"}
    ]
    today_quote = random.choice(quotes)
    today = datetime.today().date()
    cookies_accepted = request.cookies.get('cookies_accepted', 'false') == 'true'
    today_entry = MoodEntry.query.filter_by(user_id=current_user.id, date=today).first()
    return render_template('index.html', today_entry=today_entry, now=datetime.now(), quote = today_quote,  cookies_accepted=cookies_accepted)


@app.route('/add_entry', methods=['GET', 'POST'])
@login_required
def add_entry():
    if request.method == 'POST':
        mood_score = int(request.form['mood_score'])
        notes = request.form.get('notes', '')
        entry_date = datetime.strptime(request.form['entry_date'], '%Y-%m-%d').date()
        today = datetime.today().date()

        # Walidacja daty
        if entry_date > today:
            flash('Nie można dodawać wpisów z przyszłości!', 'error')
            return redirect(url_for('add_entry'))

        existing_entry = MoodEntry.query.filter_by(
            user_id=current_user.id,
            date=entry_date
        ).first()

        if existing_entry:
            existing_entry.mood_score = mood_score
            existing_entry.notes = notes
            message = 'Wpis został zaktualizowany!'
        else:
            new_entry = MoodEntry(
                mood_score=mood_score,
                notes=notes,
                user_id=current_user.id,
                date=entry_date
            )
            db.session.add(new_entry)
            message = 'Wpis został dodany!'

        db.session.commit()
        flash(message, 'success')
        return redirect(url_for('index'))

    return render_template('add_entry.html', datetime=datetime)

@app.route('/calendar')
@login_required
def show_calendar():
    year = datetime.now().year
    month = datetime.now().month

    # Pobierz wpisy i posortuj je
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user.id,
        db.extract('year', MoodEntry.date) == year,
        db.extract('month', MoodEntry.date) == month
    ).all()

    # Przygotuj dane dla kalendarza
    mood_calendar = {}
    mood_entries = []  # Do sortowania

    for entry in entries:
        mood_calendar[entry.date.day] = entry.mood_score
        mood_entries.append({
            'day': entry.date.day,
            'score': entry.mood_score,
            'notes': entry.notes
        })

    # Sortowanie dni - najlepsze i najgorsze
    mood_entries_sorted = sorted(mood_entries, key=lambda x: x['score'])
    worst_days = mood_entries_sorted[:3]  # 3 najgorsze dni
    best_days = mood_entries_sorted[-3:]  # 3 najlepsze dni
    best_days.reverse()  # Od najlepszego

    # Generowanie kalendarza
    cal = calendar.monthcalendar(year, month)

    return render_template('calendar.html',
                           calendar=cal,
                           year=year,
                           month=month,
                           mood_calendar=mood_calendar,
                           best_days=best_days,
                           worst_days=worst_days)

@app.route('/stats')
@login_required
def show_stats():
    # Pobierz wpisy z ostatnich 7 dni
    week_ago = datetime.today().date() - timedelta(days=7)
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user.id,
        MoodEntry.date >= week_ago
    ).all()

    if entries:
        mood_scores = [entry.mood_score for entry in entries]
        average_score = sum(mood_scores) / len(mood_scores)
        chart = create_mood_chart(mood_scores)
    else:
        average_score = None
        chart = None

    return render_template('stats.html', average_score=average_score,chart=chart)

@app.route('/accept_cookies', methods=['POST'])
def accept_cookies():
    response = make_response(jsonify({'status': 'success'}))
    expiry = datetime.now() + timedelta(days=365)
    response.set_cookie(
        'cookies_accepted',
        'true',
        expires=expiry,
        httponly=True,
        samesite='Lax',
        secure=True  # Wymagane jeśli używasz HTTPS
    )
    return response

@app.route('/reject_cookies', methods=['POST'])
def reject_cookies():
    response = make_response(jsonify({'status': 'success'}))
    response.set_cookie(
        'cookies_accepted',
        'false',
        expires=0  # Wygaśnięcie natychmiastowe
    )
    return response



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)