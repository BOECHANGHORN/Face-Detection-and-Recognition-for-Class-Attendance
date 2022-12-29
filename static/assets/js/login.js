// Get the form element
var form = document.querySelector('.card-body form');

// Add a submit event listener
form.addEventListener('submit', function(event) {
  // Get the username and password values
  var username = form.elements.username.value;
  var password = form.elements.password.value;

  // Validate the form data
  if (username.length === 0 || password.length === 0) {
    // Display an error message
    alert('Please enter a username and password');
    event.preventDefault();
  }
});
