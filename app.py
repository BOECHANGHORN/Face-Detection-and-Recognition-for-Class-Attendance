from flask import Flask, render_template, request, redirect, url_for
import mysql.connector

app = Flask(__name__)
app.config['MYSQL_URI'] = 'mysql://root:password123@localhost/Attendance_System'

@app.route('/')
def index():
    return render_template('login.html')


# password123
# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         # Get the form data
#         username = request.form['username']
#         password = request.form['password']
#
#         # Connect to the database
#         conn = mysql.connector.connect(user='root', password='password123', host='localhost', database='Attendance_System')
#         cursor = conn.cursor()
#
#         # Check the credentials
#         cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
#         result = cursor.fetchone()
#         if result:
#             # Redirect to the attendance page
#             return redirect(url_for('attendance'))
#         else:
#             # Redirect back to the login page
#             return redirect(url_for('login'))
#     else:
#         # Render the login template
#         return render_template('login.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get the form data
        username = request.form['username']
        password = request.form['password']

        # Check the credentials
        # TODO: ADD DATABASE
        if username == 'admin' and password == 'admin':
            # Redirect to the attendance page
            return redirect(url_for('attendance'))
        else:
            # Redirect back to the login page
            return redirect(url_for('login'))
    else:
        # Render the login template
        return render_template('login.html')


@app.route('/attendance')
def attendance():
    return render_template('dashboard.html')


if __name__ == '__main__':
    app.run(debug=True, threaded=True)
