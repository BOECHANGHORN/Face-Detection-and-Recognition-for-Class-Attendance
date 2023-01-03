// function showAttendanceData(class_id) {
//     $.ajax({
//         url: '/get_attendance_data',
//         data: {class_id: class_id},
//         success: function(response) {
//             // Display attendance data in page
//             var attendanceData = JSON.parse(response);
//             var html = '';
//             $.each(attendanceData, function(studentId, studentData) {
//                 html += '<tr>';
//                 html += '<td>' + studentId + '</td>';
//                 html += '<td>' + studentData.name + '</td>';
//                 html += '<td>' + (studentData.present ? 'Yes' : 'No') + '</td>';
//                 html += '</tr>';
//             });
//             $('#attendance-table tbody').html(html);
//         }
//     });
//     $('.edit-button').click(function() {
//         var studentId = $(this).data('student-id');
//         $('#present_' + studentId).prop('disabled', false);
//     });
//     $('#save-button').click(function() {
//         var data = {};
//         $('input[type=checkbox]').each(function() {
//             var studentId = $(this).attr('id').split('_')[1];
//             data[studentId] = {
//                 present: $(this).is(':checked')
//             }
//         });
//
//         $.ajax({
//             url: '/update_attendance',
//             data: {class_id: class_id, attendance_data: data},
//             success: function(response) {
//                 // Update success message
//                 success: function(response) {
//                     if (response == 'Success') {
//                         // Display success message
//                         flash('Attendance data updated successfully', 'success')
//                     } else {
//                         // Display error message
//                         flash('There was an error updating the attendance data', 'error')
//                     }
//                 }
//             }
//         });
//     });
//
// }
