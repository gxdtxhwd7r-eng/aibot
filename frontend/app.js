const advertisement = document.querySelector('#advertisement');
const generateButton = document.querySelector('#generate-button');
const clearButton = document.querySelector('#clear-button');
const regenerateButton = document.querySelector('#regenerate-button');
const copyButton = document.querySelector('#copy-button');
const counter = document.querySelector('#counter');
const errorBox = document.querySelector('#error');
const result = document.querySelector('#result');
const successResult = document.querySelector('#success-result');
const blockedResult = document.querySelector('#blocked-result');

function updateCounter() {
  counter.textContent = `${advertisement.value.length.toLocaleString('ru-RU')} / 20 000`;
}

function setLoading(loading) {
  generateButton.disabled = loading;
  generateButton.classList.toggle('loading', loading);
  generateButton.querySelector('.button-label').textContent = loading ? 'Анализируем объявление…' : 'Создать сообщение';
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function resetOutput() {
  errorBox.hidden = true;
  result.hidden = true;
  successResult.hidden = true;
  blockedResult.hidden = true;
}

async function generateMessage() {
  resetOutput();
  if (!advertisement.value.trim()) {
    showError('Вставьте текст объявления.');
    advertisement.focus();
    return;
  }

  setLoading(true);
  try {
    const response = await fetch('/api/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({advertisement: advertisement.value}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Не удалось получить ответ от AI. Проверьте подключение и API.');

    result.hidden = false;
    if (data.status === 'do_not_contact') {
      document.querySelector('#blocked-reason').textContent = data.reason;
      blockedResult.hidden = false;
    } else {
      document.querySelector('#car').textContent = data.car;
      document.querySelector('#hook').textContent = data.hook;
      document.querySelector('#message').textContent = data.message;
      successResult.hidden = false;
    }
    result.scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) {
    showError(error.message || 'Не удалось получить ответ от AI. Проверьте подключение и API.');
  } finally {
    setLoading(false);
  }
}

advertisement.addEventListener('input', updateCounter);
generateButton.addEventListener('click', generateMessage);
regenerateButton.addEventListener('click', generateMessage);
clearButton.addEventListener('click', () => { advertisement.value = ''; resetOutput(); updateCounter(); advertisement.focus(); });
copyButton.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(document.querySelector('#message').textContent);
    copyButton.textContent = 'Скопировано';
    setTimeout(() => { copyButton.textContent = 'Скопировать сообщение'; }, 1600);
  } catch { showError('Не удалось скопировать. Выделите сообщение вручную.'); }
});

