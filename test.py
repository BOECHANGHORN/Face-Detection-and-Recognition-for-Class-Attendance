import asyncio
import cv2
import face_recognition
import io


# import face_recognition
# import flask
#
# # Load the Haar cascade for eye detection
# eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')
#
# # Initialize a Flask app
# app = flask.Flask(__name__)
#
# @app.route('/')
# def index():
#     # Capture frames from the camera
#     capture = cv2.VideoCapture(0)
#
#     face_encodings = []
#     while len(face_encodings) < 30:
#         # Read a frame from the camera
#         _, frame = capture.read()
#
#         # Convert the frame to grayscale
#         gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#
#         # Detect eyes in the frame
#         eyes = eye_cascade.detectMultiScale(gray, 1.3, 5)
#
#         # If eyes are not detected, alert the user to open their eyes
#         if len(eyes) == 0:
#             cv2.putText(frame, "Please open your eyes", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
#
#         # Detect facial landmarks in the frame using the face_recognition library
#         landmarks = face_recognition.face_landmarks(frame)
#
#         # If facial landmarks are not detected, alert the user to show a frontal face
#         if landmarks is None:
#             cv2.putText(frame, "Please show a frontal face", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
#
#         # If eyes and facial landmarks are detected, extract face encodings using the face_recognition library
#         else:
#             encodings = face_recognition.face_encodings(frame)
#
#             # Add the encodings to the list of face encodings
#             face_encodings.extend(encodings)
#
#         # Display the frame
#         cv2.imshow('Frame', frame)
#
#         # Break the loop if the user presses 'q'
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break
#
#     # Release the camera
#     capture.release()
#     cv2.destroyAllWindows()
#
#     # Save the face encodings to a file
#     np.save('face_encodings.npy', face_encodings)
#
#     # Return a success message
#     return "Successfully recorded face encodings"
#
# if __name__ == '__main__':
#     app.run()


@app.route('/attendance')
def attendance():
    # Start a new asyncio task to perform the face recognition processing
    asyncio.create_task(process_face_recognition())

    # Return the video stream to the client
    return Response(get_video_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


async def process_face_recognition():
    while True:
        # Get the current frame from the video stream
        frame = get_current_frame()

        # Convert the frame to a format suitable for face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces in the frame
        face_locations = face_recognition.face_locations(rgb_frame)

        # Draw rectangles around the detected faces
        for (top, right, bottom, left) in face_locations:
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)

        # Get the face encodings for the detected faces
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        # Match the detected faces to known faces
        face_names = []
        for face_encoding in face_encodings:
            # Check if the face is a match for any known faces
            match = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
            name = "Unknown"
            if True in match:
                # Find the index of the matching face
                match_index = match.index(True)
                name = known_face_names[match_index]
            face_names.append(name)

        # Update the video stream with the processed frame
        update_video_stream(frame)

        # Sleep for a short period of time before processing the next frame
        await asyncio.sleep(0.1)


def get_video_stream():
    # Create a video capture object
    cap = cv2.VideoCapture(0)

    # Set the frame width and height
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Create a memory buffer for the video stream
    buffer = io.BytesIO()

    # Set the boundary for the video frames
    boundary = b'frame'

    while True:
        # Read the next frame from the video capture object
        ret, frame = cap.read()

        # Encode the frame as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)

        # Write the boundary and the frame to the buffer
        buffer.write(b'--frame\r\n')
        buffer.write(b'Content-Type: image/jpeg\r\n\r\n')
        buffer.write(jpeg.tobytes())
        buffer.write(b'\r\n')

        # Yield the buffer as a stream
        yield buffer.getvalue()

        # Reset the buffer for the next frame
        buffer.seek(0)
        buffer.truncate(0)


def get_current_frame():
    # Get the current frame from the video capture object
    ret, frame = cap.read()
    return frame


def update_video_stream(frame):
    # Encode the frame as JPEG
    ret, jpeg = cv2.imencode('.jpg', frame)

    # Write the boundary and the frame to the buffer
    buffer.write(b'--frame\r\n')
    buffer.write(b'Content-Type: image/jpeg\r\n\r\n')
    buffer.write(jpeg.tobytes())
    buffer.write(b'\r\n')
