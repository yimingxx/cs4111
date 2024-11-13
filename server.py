#!/usr/bin/env python3

"""
Columbia W4111 Intro to databases
Example webserver

To run locally

    python server.py

Go to http://localhost:8111 in your browser


A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""

import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)



# XXX: The Database URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@<IP_OF_POSTGRE_SQL_SERVER>/<DB_NAME>
#
# For example, if you had username ewu2493, password foobar, then the following line would be:
#
#     DATABASEURI = "postgresql://ewu2493:foobar@<IP_OF_POSTGRE_SQL_SERVER>/postgres"
#
# For your convenience, we already set it to the class database

# Use the DB credentials you received by e-mail
DB_USER = "yx2900"
DB_PASSWORD = "yx2900"

DB_SERVER = "w4111.cisxo09blonu.us-east-1.rds.amazonaws.com"

DATABASEURI = "postgresql://"+DB_USER+":"+DB_PASSWORD+"@"+DB_SERVER+"/proj1part2"


#
# This line creates a database engine that knows how to connect to the URI above
#
engine = create_engine(DATABASEURI)

conn = engine.connect()


@app.before_request
def before_request():
  """
  This function is run at the beginning of every web request 
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request

  The variable g is globally accessible
  """
  try:
    g.conn = engine.connect()
  except:
    print("uh oh, problem connecting to database")
    import traceback; traceback.print_exc()
    g.conn = None

@app.teardown_request
def teardown_request(exception):
  """
  At the end of the web request, this makes sure to close the database connection.
  If you don't the database could run out of memory!
  """
  try:
    g.conn.close()
  except Exception as e:
    pass


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to e.g., localhost:8111/foobar/ with POST or GET then you could use
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: http://flask.pocoo.org/docs/0.10/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#
@app.route('/')
def index():
  return render_template("index.html")

#
# This is an example of a different path.  You can see it at
# 
#     localhost:8111/another
#
# notice that the functio name is another() rather than index()
# the functions for each app.route needs to have different names
#
def generate_unique_user_id():
    return random.randint(1000, 9999)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        admin_key = request.form.get('admin_key', None)

        user_query = text("""SELECT * FROM "Users" WHERE Email = :email""")
        user = g.conn.execute(user_query, {'email': email}).fetchone()

        if user:
            user_id = user['User_ID']
            if user['Names'] != name:
                flash('Name does not match the email.', 'error')
                return redirect('/login')

            session['user_id'] = user_id
            session['name'] = name
            session['email'] = email
            flash('Logged in successfully.', 'success')

        else:
            user_id = generate_unique_user_id()
            insert_user_query = text("""
                INSERT INTO "Users" (User_ID, Names, Email, Manager_Role_Level, Student_Grade_Level) 
                VALUES (:user_id, :name, :email, :manager_role_level, :student_grade_level)
            """)
            manager_role_level = 1 if admin_key == '8111' else None
            student_grade_level = 1 if manager_role_level is None else None
            
            g.conn.execute(insert_user_query, {
                'user_id': user_id,
                'name': name,
                'email': email,
                'manager_role_level': manager_role_level,
                'student_grade_level': student_grade_level
            })
            g.conn.commit()

            session['user_id'] = user_id
            session['name'] = name
            session['email'] = email
            flash('Account created successfully!', 'success')

        if admin_key == '8111':
            session['is_admin'] = True
            flash('Logged in as administrator.', 'success')
            return redirect('/admin_dashboard')  
        else:
            session['is_admin'] = False
            flash('Logged in as a regular user.', 'success')
            return redirect('/user_dashboard')  

    return render_template('login.html')

@app.route('/user_dashboard')
def user_dashboard():
    user_id = session.get('user_id')
    if not user_id or session.get('is_admin', False):
        flash('Please log in as a regular user.', 'error')
        return redirect('/login')
    
    borrow_records_query = text("""
        SELECT "Book".Book_Name, "Return&Borrow_Record".Borrow_Date, "Return&Borrow_Record".Due_Date, "Return&Borrow_Record".Return_Date, "Book".Status
        FROM “Return&Borrow_Record”
        JOIN "Book" ON "Return&Borrow_Record".Book_ID = "Book".Book_ID
        WHERE "Return&Borrow_Record".User_ID = :user_id
    """)
    records = g.conn.execute(borrow_records_query, {'user_id': user_id}).fetchall()

    return render_template('user_dashboard.html', name=session['name'], records=records)

@app.route('/borrow', methods=['GET', 'POST'])
def borrow_book():
    user_id = session.get('user_id')
    if not user_id or session.get('is_admin', False):
        flash("Please log in as a regular user.", "error")
        return redirect('/login')

    if request.method == 'POST':
        book_id = request.form['book_id']
        borrow_date = request.form['borrow_date']
        due_date = request.form['due_date']

        book_query = text("""SELECT Status FROM “Book” WHERE Book_ID = :book_id""")
        book = g.conn.execute(book_query, {'book_id': book_id}).fetchone()

        if not book or book['Status'] != 'Available':
            flash("This book is not available for borrowing.", "error")
            return redirect('/borrow')

        update_book_query = text("""UPDATE "Book" SET Status = 'Borrowed' WHERE Book_ID = :book_id""")
        g.conn.execute(update_book_query, {'book_id': book_id})

        borrow_record_query = text("""
            INSERT INTO "Return&Borrow_Record" (User_ID, Book_ID, Borrow_Date, Due_Date) 
            VALUES (:user_id, :book_id, :borrow_date, :due_date)
        """)
        g.conn.execute(borrow_record_query, {
            'user_id': user_id,
            'book_id': book_id,
            'borrow_date': borrow_date,
            'due_date': due_date
        })
        g.conn.commit()
        flash("Book borrowed successfully!", "success")
        return redirect('/user_dashboard')

    available_books_query = text("""SELECT * FROM “Book” WHERE Status = 'Available'""")
    books = g.conn.execute(available_books_query).fetchall()
    return render_template('borrow.html', books=books)

@app.route('/return', methods=['GET', 'POST'])
def return_book():
    user_id = session.get('user_id')
    if not user_id or session.get('is_admin', False):
        flash("Please log in as a regular user.", "error")
        return redirect('/login')

    if request.method == 'POST':
        record_id = request.form['record_id']
        return_date = request.form['return_date']

        update_record_query = text("""
            UPDATE "Return&Borrow_Record" SET Return_Date = :return_date WHERE Record_ID = :record_id AND User_ID = :user_id
        """)
        g.conn.execute(update_record_query, {'return_date': return_date, 'record_id': record_id, 'user_id': user_id})
        
        book_id_query = text("""SELECT Book_ID FROM "Return&Borrow_Record" WHERE Record_ID = :record_id AND User_ID = :user_id""")
        book_id = g.conn.execute(book_id_query, {'record_id': record_id, 'user_id': user_id}).fetchone()

        if book_id:
            update_book_status_query = text("""UPDATE "Book" SET Status = 'Available' WHERE Book_ID = :book_id""")
            g.conn.execute(update_book_status_query, {'book_id': book_id[0]})
            g.conn.commit()

        flash("Book returned successfully!", "success")
        return redirect('/user_dashboard')

    borrowed_books_query = text("""
        SELECT "Return&Borrow_Record".Record_ID, "Book".Book_Name, "Return&Borrow_Record".Borrow_Date, "Return&Borrow_Record".Due_Date
        FROM "Return&Borrow_Record"
        JOIN "Book" ON "Return&Borrow_Record".Book_ID = "Book".Book_ID
        WHERE "Return&Borrow_Record".User_ID = :user_id AND "Return&Borrow_Record".Return_Date IS NULL
    """)
    borrowed_books = g.conn.execute(borrowed_books_query, {'user_id': user_id}).fetchall()
    return render_template('return.html', borrowed_books=borrowed_books)

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('is_admin', False):
        flash("Only admins can access this page.", "error")
        return redirect('/login')

    user_records = None
    user_id = None
    if request.method == 'POST':
        user_id = request.form['user_id']

        user_records_query = text("""
            SELECT "Book".Book_Name, "Return&Borrow_Record".Borrow_Date, "Return&Borrow_Record".Due_Date, "Return&Borrow_Record".Return_Date, "Book".Status
            FROM "Return&Borrow_Record"
            JOIN "Book" ON "Return&Borrow_Record".Book_ID = "Book".Book_ID
            WHERE "Return&Borrow_Record".User_ID = :user_id
        """)
        user_records = g.conn.execute(user_records_query, {'user_id': user_id}).fetchall()

    return render_template('admin_dashboard.html', user_records=user_records, user_id=user_id)


@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if not session.get('is_admin', False):
        flash("Only admins can add books.", "error")
        return redirect('/login')

    if request.method == 'POST':
        book_name = request.form['book_name']
        category = request.form['category']
        condition = request.form['condition']
        status = request.form['status']

        add_book_query = text("""
            INSERT INTO "Book" (Book_Name, Categories, Condition, Status) 
            VALUES (:book_name, :category, :condition, :status)
        """)
        g.conn.execute(add_book_query, {
            'book_name': book_name,
            'category': category,
            'condition': condition,
            'status': status
        })
        g.conn.commit()
        flash("Book added successfully!", "success")
        return redirect('/admin_dashboard')

    return render_template('add_book.html')

@app.route('/delete_book', methods=['POST'])
def delete_book():
    if not session.get('is_admin', False):
        flash("Only admins can delete books.", "error")
        return redirect('/login')

    book_id = request.form['book_id']

    delete_book_query = text("""DELETE FROM "Book" WHERE Book_ID = :book_id""")
    g.conn.execute(delete_book_query, {'book_id': book_id})
    g.conn.commit()
    flash("Book deleted successfully!", "success")
    return redirect('/admin_dashboard')

@app.route('/check_books')
def check_books():
    if not session.get('is_admin', False):
        flash("Only admins can view book conditions.", "error")
        return redirect('/login')

    books_query = text('SELECT * FROM "Book"')
    books = g.conn.execute(books_query).fetchall()

    return render_template('check_books.html', books=books)


if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):
    """
    This function handles command line parameters.
    Run the server using

        python server.py

    Show the help text using

        python server.py --help

    """

    HOST, PORT = host, port
    print("running on %s:%d" % (HOST, PORT))
    app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


  run()
