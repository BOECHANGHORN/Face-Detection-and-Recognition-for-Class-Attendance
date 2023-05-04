import base64
import itertools
import pickle
import secrets
from datetime import datetime
import bcrypt as bcrypt
import face_recognition
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, Response, flash, session
import cv2
import firebase_admin
from firebase_admin import credentials, storage, db
import threading


# Set maximum number of image files
MAX_IMAGE_FILES = 3

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Load the Firebase credentials
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': "https://fyp1-d54dc-default-rtdb.asia-southeast1.firebasedatabase.app/",
    'storageBucket': "fyp1-d54dc.appspot.com"
})


class UserType:
    ADMIN = 'admin'
    LECTURER = 'lecturer'
    STUDENT = 'student'


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

            if user_type == UserType.ADMIN:
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

# TODO: MOUNT IN CAM
# TODO: ADD IN COMPARISON MODEL

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
        class_ref = db.reference('class')
        classes_data = class_ref.get()

        user_type = session['user_type']
        user_id = session['user_id']

        if user_type == UserType.ADMIN:
            class_id = classes_data.keys()

        elif user_type == UserType.LECTURER:
            class_id = [code for code in classes_data.keys() if classes_data[code]['lecturer'] == user_id]

        # Extract the names and IDs of the classes from the data
        class_names_and_ids = [(classes_data[code]['name'], code) for code in class_id]

        return render_template('start_attendance.html', class_names_and_ids=class_names_and_ids)
    else:
        # User has submitted the form
        selected_class_id = request.form['class_selection']
        return redirect(url_for('attendance_in_progress', selected_class_id=selected_class_id))


@app.route('/attendance_in_progress/<selected_class_id>', methods=['GET', 'POST'])
def attendance_in_progress(selected_class_id):
    if request.method == 'POST':
        db_ref = session.get('attendance_report_ref')

        # Initialize database references
        attendance_report_ref = db.reference(db_ref)
        lecturer_ref = db.reference('lecturer')
        student_ref = db.reference('student')

        # Clear the attendance_report_ref from session
        session.pop('attendance_report_ref', None)

        # Get the report id from the reference
        report_id = db_ref.split('/')[-1]

        # Update the end time of the attendance report
        attendance_report_ref.update({'end_time': datetime.now().strftime("%H:%M:%S")})

        # Get all the present_ids from the attendance report reference
        present_ids = attendance_report_ref.child('present_ids').get() or {}

        # Add info for present ids
        for id, data in present_ids.items():
            user_type = data['user_type']
            name = ''
            if user_type == 'Lecturer':
                name = lecturer_ref.child(id).child('name').get()
            elif user_type == 'Student':
                name = student_ref.child(id).child('name').get()
            data['name'] = name

        # Absent handling
        student_ids = db.reference('class').child(selected_class_id).child('student_ids').get()

        absent_ids = {}

        for id in student_ids:
            if id not in present_ids:
                name = student_ref.child(id).child('name').get()
                absent_ids[id] = {'name': name, 'user_type': 'Student'}

        # Update the id lists to the database
        attendance_report_ref.update({'present_ids': present_ids,
                                      'absent_ids': absent_ids})

        # Redirect to the attendance report page for the selected class
        return redirect(url_for('attendance_report', selected_report_id=report_id))

    else:
        classes_ref = db.reference('class')
        classes_data = classes_ref.get()

        # Get class name
        class_name = classes_data[selected_class_id]['name']

        # Create attendance report instance for the class
        today = datetime.now().strftime("%d%m%y")
        current_time = datetime.now().strftime("%H%M")

        db_ref = 'attendance_report/{}_{}_{}'.format(selected_class_id, today, current_time)

        attendance_report_ref = db.reference(db_ref)

        # Add current class reference to session
        session['attendance_report_ref'] = db_ref

        attendance_report_ref.set({
            'name': class_name,
            'class_id': selected_class_id,
            'date': datetime.now().strftime("%Y-%m-%d"),
            'start_time': datetime.now().strftime("%H:%M:%S"),
            'end_time': '',
            'total_face_detected': 0
        })

    return render_template('attendance_in_progress.html', selected_class_id=selected_class_id, class_name=class_name,
                           db_ref=db_ref)


@app.route('/video_feed/<selected_class_id>')
def video_feed(selected_class_id):
    attendance_report_ref = session.get('attendance_report_ref')
    attendance_report_ref = db.reference(attendance_report_ref)

    # create an instance of the FaceRecognitionThread class
    face_thread = FaceRecognitionThread(selected_class_id, attendance_report_ref)

    # start the thread
    face_thread.start()

    # return a response object that uses the generator function
    return Response(face_thread.run(), mimetype='multipart/x-mixed-replace; boundary=frame')


# Old Approach Not Threaded
# def recognize_faces(selected_class_id, attendance_report_ref):
#     # Download the student pickle file from Firebase Storage
#     student_pkl_ref = storage.bucket().blob('pickle/student.pkl')
#     student_pkl_bytes = student_pkl_ref.download_as_bytes()
#     student_pkl = pickle.loads(student_pkl_bytes)
#
#     # Download the lecturer pickle file from Firebase Storage
#     lecturer_pkl_ref = storage.bucket().blob('pickle/lecturer.pkl')
#     lecturer_pkl_bytes = lecturer_pkl_ref.download_as_bytes()
#     lecturer_pkl = pickle.loads(lecturer_pkl_bytes)
#
#     # Get the student and lecturer IDs from the realtime database
#     student_ids = db.reference(f'class/{selected_class_id}/student_ids').get()
#     lecturer_id = db.reference(f'class/{selected_class_id}/lecturer').get()
#
#     if student_pkl and student_ids:
#         # Filter the student pickle file based on the student IDs
#         student_pkl = [student for student in student_pkl if student[0] in student_ids and student[2]]
#
#         # Filter the lecturer pickle file based on the lecturer ID
#         lecturer_pkl = [lecturer for lecturer in lecturer_pkl if lecturer[0] == lecturer_id and lecturer[2]]
#
#     student_pkl.extend(lecturer_pkl)
#
#     # Create a list of match IDs from the combined pickle file
#     match_id = [record[0] for record in student_pkl]
#     encode_list_known = list(itertools.chain.from_iterable([record[1] for record in student_pkl]))
#
#     cap = cv2.VideoCapture(0)
#     cap.set(3, 640)
#     cap.set(4, 480)
#
#     # Create a list of signed attendance and signed name
#     signed_id = []  # Used for validating duplicates
#
#     while True:
#         success, img = cap.read()
#         if not success:
#             break
#         img_s = cv2.resize(img, (0, 0), None, 0.25, 0.25)
#         img_s = cv2.cvtColor(img_s, cv2.COLOR_BGR2RGB)
#
#         face_cur_frame = face_recognition.face_locations(img_s)
#         encode_cur_frame = face_recognition.face_encodings(img_s, face_cur_frame)
#
#         if face_cur_frame:
#             for encodeFace, faceLoc in zip(encode_cur_frame, face_cur_frame):
#
#                 matches = face_recognition.compare_faces(encode_list_known, encodeFace, 0.6)
#                 face_dis = face_recognition.face_distance(encode_list_known, encodeFace)
#
#                 match_index = np.argmin(face_dis)
#
#                 if matches[match_index]:
#                     id = match_id[match_index]
#                 else:
#                     id = "Unknown"
#
#                 # Draw a rectangle around the face and display the name
#                 top, right, bottom, left = faceLoc
#                 top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4
#                 cv2.rectangle(img, (left, top), (right, bottom), (0, 0, 255), 2)
#                 cv2.putText(img, str(id), (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)
#
#                 if id != "Unknown":
#                     signed_id = markAttendance(id, signed_id, attendance_report_ref, lecturer_id)
#
#         ret, buffer = cv2.imencode('.jpg', img)
#         frame = buffer.tobytes()
#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


class FaceRecognitionThread(threading.Thread):
    def __init__(self, selected_class_id, attendance_report_ref):
        threading.Thread.__init__(self)
        self.selected_class_id = selected_class_id
        self.attendance_report_ref = attendance_report_ref

    def run(self):
        # Download the student pickle file from Firebase Storage
        student_pkl_ref = storage.bucket().blob('pickle/student.pkl')
        student_pkl_bytes = student_pkl_ref.download_as_bytes()
        student_pkl = pickle.loads(student_pkl_bytes)

        # Download the lecturer pickle file from Firebase Storage
        lecturer_pkl_ref = storage.bucket().blob('pickle/lecturer.pkl')
        lecturer_pkl_bytes = lecturer_pkl_ref.download_as_bytes()
        lecturer_pkl = pickle.loads(lecturer_pkl_bytes)

        # Get the student and lecturer IDs from the realtime database
        student_ids = db.reference(f'class/{self.selected_class_id}/student_ids').get()
        lecturer_id = db.reference(f'class/{self.selected_class_id}/lecturer').get()

        if student_pkl and student_ids:
            # Filter the student pickle file based on the student IDs
            student_pkl = [student for student in student_pkl if student[0] in student_ids and student[2]]

            # Filter the lecturer pickle file based on the lecturer ID
            lecturer_pkl = [lecturer for lecturer in lecturer_pkl if lecturer[0] == lecturer_id and lecturer[2]]

        student_pkl.extend(lecturer_pkl)

        # Create a list of match IDs from the combined pickle file
        match_id = [record[0] for record in student_pkl]
        encode_list_known = list(itertools.chain.from_iterable([record[1] for record in student_pkl]))

        cap = cv2.VideoCapture(0)
        cap.set(3, 640)
        cap.set(4, 480)

        # Create a list of signed attendance and signed name
        signed_id = []  # Used for validating duplicates

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

                    matches = face_recognition.compare_faces(encode_list_known, encodeFace, 0.6)
                    face_dis = face_recognition.face_distance(encode_list_known, encodeFace)

                    match_index = np.argmin(face_dis)

                    if matches[match_index]:
                        id = match_id[match_index]
                    else:
                        id = "Unknown"

                    # Draw a rectangle around the face and display the name
                    top, right, bottom, left = faceLoc
                    top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4
                    cv2.rectangle(img, (left, top), (right, bottom), (0, 0, 255), 2)
                    cv2.putText(img, str(id), (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)

                    if id != "Unknown":
                        signed_id = markAttendance(id, signed_id, self.attendance_report_ref, lecturer_id)

            ret, buffer = cv2.imencode('.jpg', img)
            frame = buffer.tobytes()

            # Yield the frame to the main thread to send to the web browser
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


class FlaskThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        app.run(host='0.0.0.0')


def markAttendance(id, signed_id, attendance_report_ref, lecturer_id):
    if id not in signed_id:

        signed_id.append(id)

        # Update list for database
        join_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update attendance in database
        if id == lecturer_id:
            print("lecturer_id:", id, "lecturer_join_time:", join_time, "user_type:", "Lecturer")
            attendance_report_ref.child('present_ids').child(id).update({'lecturer_join_time': join_time,
                                                                         'user_type': 'Lecturer'})
        else:
            print("student_id:", id, "student_join_time:", join_time, "user_type:", "Student")
            attendance_report_ref.child('present_ids').child(id).update({'student_join_time': join_time,
                                                                         'user_type': 'Student'})

        attendance_report_ref.update({'total_face_detected': attendance_report_ref.child(
            'total_face_detected').transaction(lambda current_value: (current_value or 0) + 1)})

    return signed_id


@app.route('/register_new_user', methods=['GET', 'POST'])
def register_new_user():
    if request.method == 'POST':

        # Get the form data from the request
        user_type = request.form['user_type']
        name = request.form['name']
        id = request.form['id']
        password = request.form['password']
        images = request.files.getlist('image')

        # Limit the number of images to 3
        images = images[:MAX_IMAGE_FILES]

        num_images = 0

        # Loop through each image and upload it to the storage bucket
        for i, image in enumerate(images):
            # Save the image to a temporary location
            image.save(f'static/Images/tmp{i + 1}.jpg')

            # Get a reference to the storage bucket and create a blob
            bucket = storage.bucket()
            blob = bucket.blob(f'{user_type}/{id}/{id}_{i + 1}.jpg')

            # Upload the image to the blob
            image.seek(0)
            blob.upload_from_file(image)

            num_images = i + 1

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
            'num_images': num_images,
            'image_url': '/'.join(blob.public_url.split('/')[:-1] + ['...']),
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
        for user_type in [UserType.LECTURER, UserType.STUDENT]:
            encodings = []

            # Get a reference from the realtime database
            collection_ref = db.reference(user_type).get()

            # Loop through the documents in the collection
            for id, data in collection_ref.items():
                # List all blobs with matching prefix
                blobs = bucket.list_blobs(prefix=f"{user_type}/{id}/{id}")

                # Loop through the blobs
                for blob in blobs:
                    # Get the image blob from the storage
                    image_blob = bucket.get_blob(blob.name)

                    # Skip processing if the image blob is None
                    if image_blob is None:
                        print(f"{blob.name} has no image")
                        continue

                    # Read the image data as an array using cv2
                    image_array = np.frombuffer(image_blob.download_as_string(), np.uint8)
                    image = cv2.imdecode(image_array, cv2.COLOR_BGRA2BGR)

                    # # Display the image
                    # cv2.imshow('Image', image)
                    # cv2.waitKey(0)

                    # Pass the image array to the generate_encodings function
                    encoding = get_encodings([image])
                    face_detected = True

                    if not encoding:
                        face_detected = False
                        message.append(f"No face detected for {user_type} : {id}, on {blob.name}")

                    # Add the id and encoding to the encodings list
                    encodings.append([id, encoding, face_detected])

            # # Debug
            # print(encodings)

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
        # Return generate encoding template
        return render_template('generate_encoding.html')


@app.route('/view_attendance_report', methods=['GET', 'POST'])
def view_attendance_report():
    if request.method == 'POST':
        # User has submitted the form
        selected_report_id = request.form['report_selection']

        return redirect(url_for('attendance_report', selected_report_id=selected_report_id))

    else:
        # Set up database reference
        class_ref = db.reference('class')
        attendance_report_ref = db.reference('attendance_report')

        user_type = session['user_type']
        user_id = session['user_id']

        # Retrieve all the classes if user is admin
        if user_type == UserType.ADMIN:
            report_id = [code for code in attendance_report_ref.get().keys()]

        # Retrieve classes based on lecturer id if user is lecturer
        elif user_type == UserType.LECTURER:
            class_code = [code for code in class_ref.get().keys() if
                          class_ref.child(code).child('lecturer').get() == user_id]

            report_id = [code for code in attendance_report_ref.get().keys() if code.split('_')[0] in class_code]

        # Retrieve classes based on student id if user is student
        elif user_type == UserType.STUDENT:
            class_code = [code for code in class_ref.get().keys() if
                          user_id in class_ref.child(code).child('student_ids').get()]

            report_id = [code for code in attendance_report_ref.get().keys() if code.split('_')[0] in class_code]

        report_data = attendance_report_ref.get()
        report_names_and_ids = [(data['name'], key) for key, data in report_data.items() if key in report_id]

        return render_template('view_attendance_report.html', report_names_and_ids=report_names_and_ids)


@app.route('/attendance_report/<selected_report_id>', methods=['GET', 'POST'])
def attendance_report(selected_report_id):
    if request.method == 'POST':
        data = request.get_json()  # Parse JSON data from request
        updated_present_ids = data['presentIds']  # Access 'presentIds' key from data
        updated_absent_ids = data['absentIds']  # Access 'absentIds' key from data

        # Get all the data from the attendance report reference
        attendance_report_ref = db.reference('attendance_report').child(selected_report_id)
        selected_report_data = attendance_report_ref.get()

        # Merge present_data and absent_data into a single dictionary
        attendance_data = {}
        for key in ['present_ids', 'absent_ids']:
            if key in selected_report_data:
                attendance_data.update(selected_report_data[key])

        # Create updated dictionaries based on updated_present_ids and updated_absent_ids
        updated_present_data = {uid: user_data for uid, user_data in attendance_data.items() if
                                uid in updated_present_ids}
        updated_absent_data = {uid: user_data for uid, user_data in attendance_data.items() if
                               uid in updated_absent_ids}

        print(updated_present_data)
        print(updated_absent_data)

        # Update the new data in the attendance_report node
        attendance_report_ref.update({
            'present_ids': updated_present_data,
            'absent_ids': updated_absent_data
        })

        return ""

    else:
        attendance_report_ref = db.reference('attendance_report')

        # # DUMMY DATA
        # attendance_report_ref.child(selected_report_id).update({
        #     'present_ids': {
        #         '0001': {'lecturer_join_time': '2023-04-08 21:06:32', 'name': 'Eugene', 'user_type': 'Lecturer'},
        #         '1181103320': {'name': 'Boe Chang Horn', 'student_join_time': '2023-04-08 21:06:33',
        #                        'user_type': 'Student'}},
        #     'absent_ids': {'1181103087': {'name': 'Jason', 'user_type': 'Student'},
        #                    'shabi': {'name': 'Eugene', 'user_type': 'Student'}},
        #
        # })

        # Get all the data from the attendance report reference
        selected_report_data = attendance_report_ref.child(selected_report_id).get()

        # Pass the data to the HTML template
        present_data = selected_report_data.get('present_ids', {})
        absent_data = selected_report_data.get('absent_ids', {})
        class_id = selected_report_data['class_id']
        date = selected_report_data['date']
        end_time = selected_report_data['end_time']
        class_name = selected_report_data['name']
        start_time = selected_report_data['start_time']
        total_face_detected = selected_report_data['total_face_detected']

        return render_template('attendance_report.html',
                               selected_report_id=selected_report_id,
                               present_ids=present_data,
                               absent_ids=absent_data,
                               class_id=class_id,
                               date=date,
                               end_time=end_time,
                               class_name=class_name,
                               start_time=start_time,
                               total_face_detected=total_face_detected)


@app.route('/edit_classes')
def edit_classes():
    user_type = session.get('user_type')
    user_id = session.get('user_id')

    class_ref = db.reference('class')
    classes_data = class_ref.get()

    classes = []

    if classes_data:
        for class_id, class_data in classes_data.items():
            # Admin: Get all classes
            # Lecturer: Only get classes which is assigned
            if user_type == UserType.ADMIN or class_ref.child(class_id).child('lecturer').get() == user_id:
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


@app.route('/edit_details', methods=['GET', 'POST'])
def edit_details():
    user_type = session['user_type']
    user_id = session['user_id']

    if request.method == 'POST':
        # Get the form data from the request
        name = request.form['name']
        password = request.form['password']
        images = request.files.getlist('image')

        # Limit the number of images to 3
        images = images[:MAX_IMAGE_FILES]

        # Loop through each image and upload it to the storage bucket
        for i, image in enumerate(images):
            # Save the image to a temporary location
            image.save(f'static/Images/tmp{i + 1}.jpg')

            # Get a reference to the storage bucket and create a blob
            bucket = storage.bucket()
            blob = bucket.blob(f'{user_type}/{user_id}/{user_id}_{i + 1}.jpg')

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
        ref.child(user_id).set({
            'name': name,
            'password': hashed_password_base64,
            'salt': salt_base64,
            'image_url': '/'.join(blob.public_url.split('/')[:-1] + ['...']),
        })

        return redirect(url_for('edit_details'))

    else:
        # Get a reference to the bucket
        bucket = storage.bucket()

        # List all blobs with matching prefix
        blobs = bucket.list_blobs(prefix=f"{user_type}/{user_id}/{user_id}")

        # Create an empty list to store the base64 encoded images
        image_data = []

        # Loop through the blobs
        for blob in blobs:
            # Get the image blob from the storage
            image_blob = bucket.get_blob(blob.name)

            # Convert the image blob to a base64 encoded string
            if image_blob is not None:
                image_data.append(base64.b64encode(image_blob.download_as_bytes()).decode('utf-8'))

        return render_template('edit_details.html', image_data=image_data)


# TODO: low priority
@app.route('/capture_face')
def capture_face():
    return render_template('capture_face.html')


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
    app.run(debug=True, threaded=True)
