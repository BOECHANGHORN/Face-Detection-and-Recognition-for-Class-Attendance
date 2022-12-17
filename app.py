from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('login.html')


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
