import sqlite3
from flask import Flask, render_template, request, url_for, flash, redirect, session
from werkzeug.exceptions import abort
import bcrypt
from bcrypt import hashpw, checkpw, gensalt
import pickle
import pandas as pd
import requests
import numpy as np
from flask_paginate import Pagination, get_page_parameter

app = Flask(__name__)


def get_db_connection():
    connec = sqlite3.connect('database.db')
    connec.row_factory = sqlite3.Row
    return connec


def get_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return users


def check_password(password, hashed_password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

def fetch_poster(movie_id):
    url = "https://api.themoviedb.org/3/movie/{}?api_key=8265bd1679663a7ea12ac168da84d2e8&language=en-US".format(movie_id)
    data = requests.get(url)
    data = data.json()
    poster_path = data['poster_path']
    full_path = "https://image.tmdb.org/t/p/w500/" + poster_path
    return full_path

def update_balance(user_id, amount):
    conn = get_db_connection()
    conn.execute('UPDATE balances SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def recommend(movie):
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[-1])[1:4]
    recommended_movies = []
    recommended_movies_posters = []
    for i in movies_list:
        movie_id = movies.iloc[i[0]].movie_id

        recommended_movies.append(movies.iloc[i[0]].title)
        # fetch poster from api
        recommended_movies_posters.append(fetch_poster(movie_id))
    return recommended_movies, recommended_movies_posters
    
def is_movie_purchased(user_id, movie_name):
    if 'user_id' not in session:
        return False
    conn = get_db_connection()
    purchased_movies = conn.execute('SELECT * FROM purchased_movies WHERE user_id = ?', (int(user_id),)).fetchall()
    conn.close()
    for purchased_movie in purchased_movies:
        if purchased_movie['movie_name'] == movie_name:
            return True
    return False

def get_balance(user_id):
    conn = get_db_connection()
    balance = conn.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return balance[0] if balance else 0

def filter_movies(all_movies, search_query):
    filtered_movies = []
    for movie in all_movies:
        if search_query.lower() in movie.lower():
            filtered_movies.append(movie)
    return filtered_movies

allowed = ['mp4']
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

movie_dict = pickle.load(open('movie_dict.pkl', 'rb'))
movies = pd.DataFrame(movie_dict)
similarity = pickle.load(open('similarity.pkl', 'rb'))

movies_info_about_what = pickle.load(open('movies-info-about-what.pkl', 'rb'))
movies_info = pd.DataFrame(movies_info_about_what)
movies_info_about_what_2 = pickle.load(open('movies-info-release_date-tagline-production_companies-production_countries.pkl', 'rb'))
movies_info_2 = pd.DataFrame(movies_info_about_what_2)

@app.route('/', methods=['GET', 'POST'])
def index():
    connec = get_db_connection()
    if request.method == 'POST':
        if 'user_id' in session:
            is_logged_in = True
        else:
            is_logged_in = False
        selected_movie_name = request.form['movie_name']
        if selected_movie_name not in movies['title'].values:
            flash("Sorry, this movie is not available on out site.")
            return render_template('index.html', is_logged_in=is_logged_in, movie_names=movies['title'].values)
        else:
            names, posters = recommend(selected_movie_name)
            selected_movie_poster = fetch_poster(movies[movies['title'] == selected_movie_name]['movie_id'].values[0])
            movie_iddd = movies[movies['title'] == selected_movie_name]['movie_id'].values[0]
            reviews = connec.execute('SELECT * FROM reviews WHERE movie_id = ?', (movie_iddd,)).fetchall()
            avg_rating = connec.execute('SELECT AVG(rating) as avg_rating FROM reviews WHERE movie_id = ?', (movie_iddd,)).fetchone()['avg_rating']
            return redirect(url_for('recommendation', movie_iddd=movie_iddd, selected_movie_name=selected_movie_name))
    if 'user_id' in session:
        user_id = session['user_id']
        return render_template('index.html', user_id=user_id, is_logged_in=True, movie_names=movies['title'].values)
    else:
        connec.close()
        return render_template('index.html', is_logged_in=False, movie_names=movies['title'].values)

@app.route('/recommendation/<int:movie_iddd>/<string:selected_movie_name>', methods=['GET', 'POST'])
def recommendation(movie_iddd, selected_movie_name):
    connec = get_db_connection()
    names, posters = recommend(selected_movie_name)
    selected_movie_poster = fetch_poster(movies[movies['title'] == selected_movie_name]['movie_id'].values[0])
    reviews = connec.execute('SELECT * FROM reviews WHERE movie_id = ?', (movie_iddd,)).fetchall()
    avg_rating = connec.execute('SELECT AVG(rating) as avg_rating FROM reviews WHERE movie_id = ?', (movie_iddd,)).fetchone()['avg_rating']
    movie_iddd_info = int(np.where(movies['title'].values == selected_movie_name)[0])
    movie_info_overview = movies_info['overview'][movie_iddd_info]
    movie_info_genre = movies_info['genres'][movie_iddd_info]
    movie_info_keywords = movies_info['keywords'][movie_iddd_info]
    movie_info_cast = movies_info['cast'][movie_iddd_info]
    movie_info_director = movies_info['crew'][movie_iddd_info]
    if movie_iddd_info in movies_info_2['release_date'].index and pd.notnull(movies_info_2['release_date'][movie_iddd_info]): # в некоторых фильмaх какие-то значения могут отсутствовать для определённых атрибутов 
        movie_info_release_date = movies_info_2['release_date'][movie_iddd_info]
    else:
        movie_info_release_date = "No information"
    if movie_iddd_info in movies_info_2['tagline'].index and pd.notnull(movies_info_2['tagline'][movie_iddd_info]):
        movie_info_tagline = movies_info_2['tagline'][movie_iddd_info]
    else:
        movie_info_tagline = "No information"
    if movie_iddd_info in movies_info_2['production_companies'].index and pd.notnull(movies_info_2['production_companies'][movie_iddd_info]):
        movie_info_production_companies = movies_info_2['production_companies'][movie_iddd_info]
    else:
        movie_info_production_companies = "No information"
    if movie_iddd_info in movies_info_2['production_countries'].index and pd.notnull(movies_info_2['production_countries'][movie_iddd_info]):
        movie_info_production_countries = movies_info_2['production_countries'][movie_iddd_info]
    else:
        movie_info_production_countries = "No information"
    movie_iddd_similar = [movies[movies['title'] == name]['movie_id'].values[0] for name in names]
    conn = get_db_connection()
    trailer = conn.execute('SELECT video_name FROM trailers WHERE movie_id = ?', (movie_iddd,)).fetchone()
    conn.close()
    trailer_url = None
    if trailer:
        trailer_url = url_for('static', filename='uploads/' + trailer['video_name'])
    if 'user_id' in session:
        is_logged_in = True
    else:
        is_logged_in = False
    return render_template('recommendation.html', movie_iddd=movie_iddd, names=names, posters=posters, selected_movie_name=selected_movie_name, selected_movie_poster=selected_movie_poster, is_logged_in=is_logged_in, is_movie_purchased=is_movie_purchased, reviews=reviews, avg_rating=avg_rating, movie_info_overview=movie_info_overview, 
                           movie_info_genre=movie_info_genre, movie_info_keywords=movie_info_keywords, movie_info_cast=movie_info_cast, movie_info_director=movie_info_director, movie_iddd_similar=movie_iddd_similar, movie_info_release_date=movie_info_release_date, movie_info_tagline=movie_info_tagline, movie_info_production_companies=movie_info_production_companies, movie_info_production_countries=movie_info_production_countries, trailer_url=trailer_url)

@app.route('/upload', methods=['POST'])
def upload():
    if 'video' not in request.files:
        flash('No video file found')
        return redirect(url_for('profile'))
    video = request.files['video']
    if video.filename == '':
        flash('No video selected')
        return redirect(url_for('profile'))
    if video and allowed_file(video.filename):
        video.save('static/uploads/' + video.filename)
        movie_id = request.form['movie_id']
        video_name = request.form['video_name']

        conn = get_db_connection()
        conn.execute('INSERT INTO trailers (movie_id, video_name) VALUES (?, ?)', (movie_id, video_name))
        conn.commit()
        conn.close()
        flash('Trailer uploaded successfully')
    else:
        flash('Invalid video file')
    return redirect(url_for('profile'))
    
@app.route('/all_movies', methods=['GET'])
def all_movies():
    if 'user_id' in session:
        is_logged_in = True
    else:
        is_logged_in = False
    all_movies = movies['title'].values
    search_query = request.args.get('search', '')
    per_page = 9
    page = request.args.get(get_page_parameter(), type=int, default=1)
    filtered_movies = filter_movies(all_movies, search_query)
    pagination = Pagination(page=page, per_page=per_page, total=len(filtered_movies), css_framework='bootstrap4')

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    movies_subset = filtered_movies[start_idx:end_idx]
    movies_iddd = []
    movies_posters = []
    for movie_title in movies_subset:
        movie_id = movies[movies['title'] == movie_title]['movie_id'].values[0]
        movies_iddd.append(movie_id)
        movies_posters.append(fetch_poster(movie_id))
    return render_template('all_movies.html', movies=movies_subset, movies_posters=movies_posters, pagination=pagination, is_logged_in=is_logged_in, page=page, per_page=per_page, movies_iddd=movies_iddd)

@app.route('/add_review', methods=['POST'])
def add_review():
    if request.method == 'POST':
        user_id = session.get('user_id')
        if not user_id:
            flash('You need to be logged in to add a review.')
            return redirect(url_for('login'))

        conn = get_db_connection()
        user = conn.execute('SELECT first_name, last_name FROM users WHERE id = ?', (user_id,)).fetchone()
        first_name = user['first_name']
        last_name = user['last_name']

        movie_id = request.form['movie_id']
        rating = request.form['rating']
        comment = request.form['comment']

        conn.execute('INSERT INTO reviews (user_id, movie_id, rating, comment, first_name1, last_name1) VALUES (?, ?, ?, ?, ?, ?)',
                     (user_id, movie_id, rating, comment, first_name, last_name))

        conn.commit()
        conn.close()
        flash('Review added successfully.')
        # return redirect(url_for('index', movie_id=movie_id))
        selected_movie_name = request.form['selected_movie_name']
        movie_iddd = movies[movies['title'] == selected_movie_name]['movie_id'].values[0]
        return redirect(url_for('recommendation', movie_iddd=movie_iddd, selected_movie_name=selected_movie_name))
    return redirect(url_for('index'))

@app.route('/delete_review', methods=['POST'])
def delete_review():
    if request.method == 'POST':
        review_id = request.form['review_id']

        conn = get_db_connection()
        conn.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
        conn.commit()
        conn.close()

        flash('Review deleted successfully.')
        selected_movie_name = request.form['selected_movie_name']
        movie_iddd = movies[movies['title'] == selected_movie_name]['movie_id'].values[0]
        return redirect(url_for('recommendation', movie_iddd=movie_iddd, selected_movie_name=selected_movie_name))
    return redirect(url_for('index'))

@app.route('/edit_review', methods=['POST'])
def edit_review():
    if request.method == 'POST':
        review_id = request.form['review_id']
        new_rating = request.form['new_rating']
        new_comment = request.form['new_comment']

        conn = get_db_connection()
        conn.execute('UPDATE reviews SET rating = ?, comment = ? WHERE id = ?',
                     (new_rating, new_comment, review_id))
        conn.commit()
        conn.close()

        flash('Review updated successfully.')
        selected_movie_name = request.form['selected_movie_name']
        movie_iddd = movies[movies['title'] == selected_movie_name]['movie_id'].values[0]
        return redirect(url_for('recommendation', movie_iddd=movie_iddd, selected_movie_name=selected_movie_name))
    return redirect(url_for('index'))

@app.route('/about')
def about():
    if 'user_id' in session:
        is_logged_in = True
    else:
        is_logged_in = False
    return render_template('about.html', is_logged_in=is_logged_in)


@app.route('/create', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        password = request.form['password']
        repeat_password = request.form['repeat_password']

        conn = get_db_connection()
        existing_user = conn.execute('SELECT * FROM users WHERE first_name = ? AND last_name = ?',
                                     (first_name, last_name,)).fetchone()
        if existing_user:
            flash('User with this first name and last name is already registered.')
        elif not first_name:
            flash('First Name is required!')
        elif not last_name:
            flash('Last Name is required!')
        elif not password:
            flash('Password is required!')
        elif not repeat_password:
            flash('Repeat password is required!')
        elif password != repeat_password:
            flash('Passwords do not match!')
        else:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            conn.execute('INSERT INTO users (first_name, last_name, password, repeat_password) VALUES (?,?,?,?)',
                         (first_name, last_name, hashed_password, repeat_password))
            conn.commit()
            conn.close()
            flash('Signed in successfully!')
            return redirect(url_for('index'))
    if 'user_id' in session:
        is_logged_in = True
    else:
        is_logged_in = False
    return render_template('create.html', is_logged_in=is_logged_in)


@app.route('/login')
def show_login_form():
    if 'user_id' in session:
        is_logged_in = True
    else:
        is_logged_in = False
    return render_template('login.html', is_logged_in=is_logged_in)


@app.route('/login', methods=['POST'])
def login():
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    password = request.form['password']

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE first_name = ? AND last_name = ?',
                        (first_name, last_name,)).fetchone()
    conn.close()
    if user and check_password(password, user['password']):
        session['user_id'] = user['id']
        session['first_name'] = user['first_name']
        session['last_name'] = user['last_name']
        flash('You were successfully logged in')
        return redirect(url_for('index'))
    else:
        error = 'Invalid username, surname or password'
        return render_template('login.html', error=error)

# НОВЕ 2
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out successfully!')
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_db_connection()
        balance = get_balance(user_id)
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        purchased_movies = conn.execute('SELECT * FROM purchased_movies WHERE user_id = ?', (user_id,)).fetchall()
        conn.close()
        if user:
            return render_template('profile.html', balance=balance, user=user, is_logged_in=True, purchased_movies=purchased_movies)
        else:
            abort(404)
    else:
        abort(401)
@app.route('/buy', methods=['GET', 'POST'])
def buy_movie():
    if 'user_id' in session:
        is_logged_in = True
        if request.method == 'POST':
            selected_movie_name = request.form['selected_movie_name']
            user_id = session['user_id']
            balance = get_balance(user_id)
            if balance < 1:
                flash("You don't have enough funds to purchase this movie.")
                return render_template('index.html',  selected_movie_name=selected_movie_name, balance=balance, is_logged_in=True, movie_names=movies['title'].values)
            conn = get_db_connection()
            conn.execute('INSERT INTO purchased_movies (user_id, movie_name) VALUES (?, ?)', (user_id, selected_movie_name))
            conn.commit()
            conn.close()
            update_balance(user_id, -1)
            flash("You have successfully purchased the movie for $1!")
            return redirect(url_for('profile'))
    else:
        is_logged_in = False
        flash('You have to log in to the site in order to buy movies!')
        return redirect(url_for('index'))

@app.route('/add_funds', methods=['POST'])
def add_funds():
    user_id = session['user_id']
    amount = 10  # Dollars
    conn = get_db_connection()
    balance = conn.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,)).fetchone()
    if balance:
        conn.execute('UPDATE balances SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    else:
        conn.execute('INSERT INTO balances (user_id, balance) VALUES (?, ?)', (user_id, amount))
    conn.commit()
    conn.close()
    flash('Funds added successfully!')
    return redirect(url_for('profile'))


if __name__ == '__main__':
    app.secret_key = 'super secret key'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.run(debug=True, port=5000)
