import asyncio
import base64
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
            # Set the session userid
            session['userid'] = username

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


@app.route('/attendance_in_progress')
def attendance_in_progress():
    selected_class_id = request.args.get('selected_class_id')

    classes_ref = db.reference('class')
    classes_data = classes_ref.get()

    # Get class name
    class_name = classes_data[selected_class_id]['name']

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
    lecturer_id = db.reference(f'class/{selected_class_id}/lecturer_id').get()

    if student_pkl and student_ids:
        # Filter the student pickle file based on the student IDs
        student_pkl = [student for student in student_pkl if student[0] in student_ids]

        # Filter the lecturer pickle file based on the lecturer ID
        lecturer_pkl = [lecturer for lecturer in lecturer_pkl if lecturer[0] == lecturer_id]

    # Create a video capture object
    cap = cv2.VideoCapture(0)

    # Start the face detection and recognition loop
    asyncio.create_task(detect_and_recognize(cap, student_ids, lecturer_id, selected_class_id))

    return render_template('attendance_in_progress.html', selected_class_id=selected_class_id, class_name=class_name)


@app.route('/video_feed')
def video_feed():
    # Create a video capture object
    cap = cv2.VideoCapture(0)

    # Continuously capture and display frames from the video feed
    def generate_frames():
        while True:
            ret, frame = cap.read()
            if ret:
                frame = cv2.imencode('.jpg', frame)[1].tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                break

    # Release the video capture object
    cap.release()

    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


async def detect_and_recognize(cap, student_ids, lecturer_id, selected_class_id):
    while True:
        # Capture a frame from the video feed
        ret, frame = cap.read()

        # If frame is successfully captured
        if ret:
            # Detect and recognize faces in the frame
            face_locations = face_recognition.face_locations(frame)
            face_encodings = face_recognition.face_encodings(frame, face_locations)
            names = []
            for face_encoding in face_encodings:
                name = "Unknown"
                # Check if face encoding matches a student
                for student_id, student_encoding in student_ids.items():
                    if face_recognition.compare_faces([student_encoding], face_encoding):
                        name = student_id
                        break
                # Check if face encoding matches the lecturer
                if name == "Unknown":
                    if face_recognition.compare_faces([lecturer_id], face_encoding):
                        name = lecturer_id
                names.append(name)

            # TODO: START FROM HERE and edit
            # Update the attendance data in the real-time database
            attendance_ref = db.reference(f'class/{selected_class_id}/attendance')
            attendance_data = attendance_ref.get() or {}
            for name in names:
                if name in attendance_data:
                    attendance_data[name]['count'] += 1
                else:
                    attendance_data[name] = {'count': 1, 'timestamp': firebase_admin.db.server_time()}
            attendance_ref.set(attendance_data)

        # Check if the end attendance button has been clicked
        end_attendance = db.reference(f'class/{selected_class_id}/end_attendance').get()
        if end_attendance:
            break

    # Save the attendance data to a pickle file in Firebase Storage
    attendance_bytes = pickle.dumps(attendance_data)
    attendance_pkl_ref = storage.bucket().blob(f'pickle/attendance_{selected_class_id}.pkl')
    attendance_pkl_ref.upload_from_string(attendance_bytes)




# @websocket.route('/video_feed')
# def video_feed():
#     # Set up the video capture
#     video_capture = cv2.VideoCapture(0)
#
#     # Continuously yield the video feed and face locations and IDs to the client
#     while True:
#         # Get the next frame and face locations and IDs from the attendance generator
#         frame, face_locations_and_ids = next(attendance_generator)
#
#         # Draw a rectangle around each face and display the face ID
#         for (top, right, bottom, left), face_id in face_locations_and_ids:
#             cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
#             cv2.putText(frame, face_id, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
#
#         # Encode the frame as JPEG
#         frame = cv2.imencode('.jpg', frame)[1]
#
#         # Convert the frame to a bytes object
#         frame = frame.tobytes()
#
#         # Yield the frame to the client
#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
#
#
# def start_class_attendance(frame):
#     # Perform face detection and recognition on the frame
#     face_locations = face_recognition.face_locations(frame)
#     face_encodings = face_recognition.face_encodings(frame, face_locations)
#     face_ids = []
#
#     # Loop through the face encodings and compare them to the known encodings
#     for face_encoding in face_encodings:
#         # Check if the face is a student
#         for student_id, student_encoding in student_encodings.items():
#             if face_recognition.compare_faces([student_encoding], face_encoding, tolerance=0.5)[0]:
#                 face_ids.append(student_id)
#                 break
#
#         # If the face is not a student, check if it is a lecturer
#         else:
#             for lecturer_id, lecturer_encoding in lecturer_encodings.items():
#                 if face_recognition.compare_faces([lecturer_encoding], face_encoding, tolerance=0.5)[0]:
#                     face_ids.append(lecturer_id)
#                     break
#
#                     # If the face is neither a student nor a lecturer, save it as an unknown person
#                 else:
#                     # Increment the unknown counter
#                     unknown_counter += 1
#
#                     # Save the image of the unknown face to Firebase Storage
#                     unknown_image_name = f'unknown{unknown_counter}.jpg'
#                     storage.child(f'images/{class_id}/{unknown_image_name}').put(face_encoding)
#
#                     # Save the image URL and ID to the database
#                     unknown_image_url = storage.child(f'images/{class_id}/{unknown_image_name}').get_url(None)
#                     unknown_id = f'unknown{unknown_counter}'
#                     database.child(f'classes/{class_id}/attendance/{unknown_id}').update({
#                         'id': unknown_id,
#                         'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
#                         'image_url': unknown_image_url
#                     })
#
#                     face_ids.append(unknown_id)
#
#         return face_locations, face_ids


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


@app.route('/train_model', methods=['GET', 'POST'])
def train_model():
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
                encoding = generate_encodings([image])
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

            # Update the last trained time in the Realtime Database for each id
            current_time = datetime.now()
            formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
            for id in encodings:
                db.reference(user_type).child(id[0]).update({
                    'last_trained_time': formatted_time,
                    'face_detected': id[2]
                })

        return message

    else:
        # Return the train_model template
        return render_template('train_model.html')


@app.route('/view_attendance_report')
def view_attendance_report():
    # Set up database reference
    ref = db.reference('attendance_report')

    user_type = session['user_type']
    userid = session['userid']

    if user_type == 'admin':
        # Retrieve list of all classes
        classes = ref.get()
    elif user_type == 'lecturer':
        # Retrieve list of classes taught by this lecturer
        classes = ref.order_by_child('lecturer_id').equal_to(userid).get()
    elif user_type == 'student':
        # Retrieve list of classes attended by this student
        classes = ref.order_by_child('student_ids').equal_to(userid).get()

    return render_template('view_attendance_report.html', classes=classes)


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


@app.template_filter()
def enumerate_custom(seq):
    return enumerate(seq)


def generate_encodings(image_list):
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
    app.run(debug=True, threaded=True)
