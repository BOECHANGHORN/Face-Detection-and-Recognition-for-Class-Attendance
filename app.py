import base64
import itertools
import pickle
from datetime import datetime
import bcrypt as bcrypt
import face_recognition
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, Response, flash, session
import cv2
import firebase_admin
from firebase_admin import credentials, storage, db

app = Flask(__name__)
app.secret_key = 'fyp1facerecognitionattendancesystem'

# Load the Firebase credentials
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': "https://fyp1-d54dc-default-rtdb.asia-southeast1.firebasedatabase.app/",
    'storageBucket': "fyp1-d54dc.appspot.com"
})


@app.route('/')
def index():
    # Clear the session data
    session.clear()
    return render_template('login.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get the form data
        username = request.form['username']
        password = request.form['password']
        user_type = request.form['user_type']

        # Retrieve the stored hashed password and salt for the given username and user type
        password_and_salt = get_password_and_salt(username, user_type)

        # Return an error message if the user's data was not found
        if password_and_salt is None:
            flash('Incorrect username and password for the user type')
            return redirect(url_for('login'))

        # Unpack the password and salt from the tuple
        stored_hashed_password_base64, salt_base64 = password_and_salt

        # Decode the stored hashed password and salt from base64
        stored_hashed_password = base64.b64decode(stored_hashed_password_base64.encode('utf-8'))
        salt = base64.b64decode(salt_base64.encode('utf-8'))

        # Hash the provided password with the salt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)

        # Check if the hashed password matches the stored hashed password
        if hashed_password == stored_hashed_password:
            # Set the session user_id
            session['user_id'] = username

            # Set the session user_type
            session['user_type'] = user_type

            if user_type == 'admin':
                # Redirect to the dashboard page
                return redirect(url_for('dashboard'))
            else:
                # Redirect to the view attendance report page
                return redirect(url_for('view_attendance_report'))
        else:
            # Redirect back to the login page
            return redirect(url_for('login'))
    else:
        # Render the login template
        return render_template('login.html')


def get_password_and_salt(username, user_type):
    # Get a reference to the user's data in the Realtime Database
    ref = db.reference(user_type).child(username)

    # Get the user's data from the Realtime Database
    data = ref.get()

    # Return None if the user's data was not found
    if data is None:
        return None

    # Return the stored hashed password and salt
    return data['password'], data['salt']


@app.route('/dashboard')
def dashboard():
    ref = db.reference('class')
    # Get the data from the realtime database
    classes = ref.get()

    # TODO: dashboard features

    return render_template('dashboard.html', classes=classes)


@app.route('/start_attendance', methods=['GET', 'POST'])
def start_attendance():
    if request.method == 'GET':
        # Get all data from the "class" node in the realtime database
        classes_ref = db.reference('class')
        classes_data = classes_ref.get()

        # Extract the names and IDs of the classes from the data
        class_names_and_ids = [(data['name'], key) for key, data in classes_data.items()]

        return render_template('start_attendance.html', class_names_and_ids=class_names_and_ids)
    else:
        # User has submitted the form
        selected_class_id = request.form['class_selection']
        return redirect(url_for('attendance_in_progress', selected_class_id=selected_class_id))



@app.route('/attendance_in_progress/<selected_class_id>')
def attendance_in_progress(selected_class_id):

    classes_ref = db.reference('class')
    classes_data = classes_ref.get()

    # Get class name
    class_name = classes_data[selected_class_id]['name']

    return render_template('attendance_in_progress.html', selected_class_id=selected_class_id, class_name=class_name)


# TODO: face recog pipeline
@app.route('/video_feed/<selected_class_id>')
def video_feed(selected_class_id):
    return Response(recognize_faces(selected_class_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


def recognize_faces(selected_class_id):
    # Download the student pickle file from Firebase Storage
    student_pkl_ref = storage.bucket().blob('pickle/student.pkl')
    student_pkl_bytes = student_pkl_ref.download_as_bytes()
    student_pkl = pickle.loads(student_pkl_bytes)

    # Download the lecturer pickle file from Firebase Storage
    lecturer_pkl_ref = storage.bucket().blob('pickle/lecturer.pkl')
    lecturer_pkl_bytes = lecturer_pkl_ref.download_as_bytes()
    lecturer_pkl = pickle.loads(lecturer_pkl_bytes)

    # Get the student and lecturer IDs from the realtime database
    student_ids = db.reference(f'class/{selected_class_id}/student_ids').get()
    lecturer_id = db.reference(f'class/{selected_class_id}/lecturer').get()

    if student_pkl and student_ids:
        # Filter the student pickle file based on the student IDs
        student_pkl = [student for student in student_pkl if student[0] in student_ids and student[2]]

        # Filter the lecturer pickle file based on the lecturer ID
        lecturer_pkl = [lecturer for lecturer in lecturer_pkl if lecturer[0] == lecturer_id and lecturer[2]]

    student_pkl.extend(lecturer_pkl)

    # Create a list of match IDs from the combined pickle file
    match_id = [record[0] for record in student_pkl]
    encode_list_known = list(itertools.chain.from_iterable([record[1] for record in student_pkl]))

    print(encode_list_known)

    cap = cv2.VideoCapture(0)
    cap.set(3, 640)
    cap.set(4, 480)

    while True:
        success, img = cap.read()
        if not success:
            break
        img_s = cv2.resize(img, (0, 0), None, 0.25, 0.25)
        img_s = cv2.cvtColor(img_s, cv2.COLOR_BGR2RGB)

        face_cur_frame = face_recognition.face_locations(img_s)
        encode_cur_frame = face_recognition.face_encodings(img_s, face_cur_frame)

        if face_cur_frame:
            for encodeFace, faceLoc in zip(encode_cur_frame, face_cur_frame):

                matches = face_recognition.compare_faces(encode_list_known, encodeFace)
                face_dis = face_recognition.face_distance(encode_list_known, encodeFace)

                match_index = np.argmin(face_dis)

                if matches[match_index]:
                    name = match_id[match_index]
                else:
                    name = "Unknown"

                # Draw a rectangle around the face and display the name
                top, right, bottom, left = faceLoc
                top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4
                cv2.rectangle(img, (left, top), (right, bottom), (0, 0, 255), 2)
                cv2.putText(img, str(name), (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)

                # mark attendance

        ret, buffer = cv2.imencode('.jpg', img)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/register_new_user', methods=['GET', 'POST'])
def register_new_user():
    if request.method == 'POST':
        # Get the form data from the request
        user_type = request.form['user_type']
        name = request.form['name']
        id = request.form['id']
        password = request.form['password']
        image = request.files['image']

        # TODO: comment this if not needed for validation
        # Save the image to a temporary location
        image.save('static/Images/tmp.jpg')

        # Get a reference to the storage bucket and create a blob
        bucket = storage.bucket()
        blob = bucket.blob(f'{user_type}/{id}/{id}.jpg')

        # Upload the image to the blob
        image.seek(0)
        blob.upload_from_file(image)

        # Generate a salt and hash the password using the salt
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)

        # Encode the hashed password and salt as base64-encoded strings
        hashed_password_base64 = base64.b64encode(hashed_password).decode('utf-8')
        salt_base64 = base64.b64encode(salt).decode('utf-8')

        # Add the user data to the Realtime Database
        ref = db.reference(user_type)
        ref.child(id).set({
            'name': name,
            'password': hashed_password_base64,
            'salt': salt_base64,
            'image_url': blob.public_url
        })

        # Redirect to the success page
        return redirect(url_for('register_success'))
    else:
        # Render the register form template
        return render_template('register_new_user.html')


@app.route('/register_success')
def register_success():
    return render_template('register_success.html')


@app.route('/generate_encoding', methods=['GET', 'POST'])
def generate_encoding():
    if request.method == 'POST':
        # Get a reference to the bucket
        bucket = storage.bucket()

        message = []

        # Loop through the lecturer and student folders
        for user_type in ['lecturer', 'student']:
            encodings = []

            # Get a reference from the realtime database
            collection_ref = db.reference(user_type).get()

            # Loop through the documents in the collection
            for id, data in collection_ref.items():
                # Get the image blob from the storage
                image_blob = bucket.get_blob(f'{user_type}/{id}/{id}.jpg')

                # Skip processing if the image blob is None
                if image_blob is None:
                    continue

                # Read the image data as an array using cv2
                image_array = np.frombuffer(image_blob.download_as_string(), np.uint8)
                image = cv2.imdecode(image_array, cv2.COLOR_BGRA2BGR)

                # Pass the image array to the generate_encodings function
                encoding = get_encodings([image])
                face_detected = True

                if not encoding:
                    face_detected = False
                    message.append(f"No face detected for {user_type} : {id}")

                # Add the id and encoding to the encodings list
                encodings.append([id, encoding, face_detected])

            # Serialize the encoding list and name it with the user_type
            serialized_encoding = pickle.dumps(encodings)
            serialized_file = f'pickle/{user_type}.pkl'

            # Upload the serialized encoding list to the storage
            bucket.blob(serialized_file).upload_from_string(serialized_encoding)

            # Update the last encode time in the Realtime Database for each id
            current_time = datetime.now()
            formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
            for id in encodings:
                db.reference(user_type).child(id[0]).update({
                    'last_encode_time': formatted_time,
                    'face_detected': id[2]
                })

        return message

    else:
        # Return the generate encoding template
        return render_template('generate_encoding.html')


@app.route('/view_attendance_report', methods=['GET', 'POST'])
def view_attendance_report():
    # TODO: view attendance report feature

    # Set up database reference
    # ref = db.reference('attendance_report')
    #
    # user_type = session['user_type']
    # user_id = session['user_id']

    # if user_type == 'admin':
    #     # Retrieve list of all classes
    #     classes = ref.get()
    # elif user_type == 'lecturer':
    #     # Retrieve list of classes taught by this lecturer
    #     classes = ref.order_by_child('lecturer_id').equal_to(user_id).get()
    # elif user_type == 'student':
    #     # Retrieve list of classes attended by this student
    #     classes = ref.order_by_child('student_ids').equal_to(user_id).get()

    if request.method == 'POST':
        return redirect(url_for('attendance_report'))
    else:
        return render_template('view_attendance_report.html')  # , classes=classes)


@app.route('/edit_classes')
def edit_classes():
    user_type = session.get('user_type')
    user_id = session.get('user_id')

    classes_ref = db.reference('class')
    if user_type == 'lecturer':
        classes_ref = classes_ref.order_by_child('lecturer').equal_to(user_id)
    else:
        classes_ref = classes_ref.order_by_key()

    classes = []
    classes_data = classes_ref.get()
    if classes_data:
        for class_id, class_data in classes_data.items():
            class_data['id'] = class_id
            classes.append(class_data)

    return render_template('edit_classes.html', classes=classes)


@app.route('/create_new_class', methods=['GET', 'POST'])
def create_new_class():
    if request.method == 'POST':
        class_id = request.form['class_id']
        class_name = request.form['class_name']
        lecturer = request.form['lecturer']
        student_ids = request.form.getlist('student_ids')

        class_ref = db.reference(f'class/{class_id}')
        class_ref.set({
            'name': class_name,
            'lecturer': lecturer,
            'student_ids': student_ids
        })

        return redirect(url_for('edit_classes'))

    students_ref = db.reference('student')
    students = []
    students_data = students_ref.get()
    if students_data:
        for student_id, student_data in students_data.items():
            student_data['id'] = student_id
            students.append(student_data)

    return render_template('create_new_class.html', students=students)


@app.route('/edit_class/<class_id>', methods=['GET', 'POST'])
def edit_class(class_id):
    if request.method == 'POST':
        class_name = request.form['class_name']
        lecturer = request.form['lecturer']
        student_ids = request.form.getlist('student_ids')

        class_ref = db.reference(f'class/{class_id}')
        class_ref.update({
            'name': class_name,
            'lecturer': lecturer,
            'student_ids': student_ids
        })

        return redirect(url_for('edit_classes'))

    class_ref = db.reference(f'class/{class_id}')
    class_data = class_ref.get()

    students_ref = db.reference('student')
    students = []
    students_data = students_ref.get()
    if students_data:
        for student_id, student_data in students_data.items():
            student_data['id'] = student_id
            students.append(student_data)

    return render_template('edit_class.html', class_data=class_data, students=students)


# TODO: finish those features
@app.route('/edit_details')
def edit_details():
    return render_template('edit_details.html')


@app.route('/add_image')
def add_image():
    return render_template('add_image.html')


@app.route('/attendance_report')
def attendance_report():
    return render_template('attendance_report.html')


@app.template_filter()
def enumerate_custom(seq):
    return enumerate(seq)


def get_encodings(image_list):
    encode_list = []
    for image in image_list:
        # Convert color space from BGR to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Calculate the 128-dimensional face encodings for the first face detected
        encode = face_recognition.face_encodings(image)
        if encode:
            encode_list.append(encode[0])

    return encode_list


if __name__ == '__main__':
    app.run(debug=True)
