const trainButton = document.querySelector('.train-button');
const flashArea = document.querySelector('.flash-area');

trainButton.addEventListener('click', () => {
  fetch('/generate_encoding')
    .then(response => response.text())
    .then(text => {
      flashArea.innerHTML = text;
    });
});