// Add a submit event listener to the form
document.getElementById('register-form').addEventListener('submit', function(event) {
// Get the name and ID input fields
const name = document.getElementById('name');
const id = document.getElementById('id');

// Validate that the name and ID fields are not empty
if (name.value.trim() === '' || id.value.trim() === '') {
  // If either field is empty, prevent the form from being submitted and show an error message
  event.preventDefault();
  alert('Name and ID are required');
}
});