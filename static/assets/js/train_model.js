const trainButton = document.querySelector('.train-button');
const flashArea = document.querySelector('.flash-area');

trainButton.addEventListener('click', () => {
  fetch('/train_model')
    .then(response => response.text())
    .then(text => {
      flashArea.innerHTML = text;
    });
});