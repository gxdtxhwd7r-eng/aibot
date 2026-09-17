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
    await copyText(document.querySelector('#message').textContent);
    copyButton.textContent = 'Скопировано ✓';
    setTimeout(() => { copyButton.textContent = 'Скопировать сообщение'; }, 1600);
  } catch { showError('Не удалось скопировать. Выделите сообщение вручную.'); }
});

const tabs = document.querySelectorAll('.tab');
const fileInput = document.querySelector('#xlsx-file');
const dropZone = document.querySelector('#drop-zone');
let pollTimer;
tabs.forEach(tab => tab.addEventListener('click', () => {
  tabs.forEach(item => item.classList.toggle('active', item === tab));
  document.querySelector('#manual-mode').hidden = tab.dataset.tab !== 'manual';
  document.querySelector('#batch-mode').hidden = tab.dataset.tab !== 'batch';
  if (tab.dataset.tab === 'batch') loadLeads(); else clearTimeout(pollTimer);
}));
fileInput.addEventListener('change', () => { document.querySelector('#file-name').textContent = fileInput.files[0]?.name || 'Файл не выбран'; });
['dragenter','dragover'].forEach(name => dropZone.addEventListener(name, event => { event.preventDefault(); dropZone.classList.add('dragging'); }));
['dragleave','drop'].forEach(name => dropZone.addEventListener(name, event => { event.preventDefault(); dropZone.classList.remove('dragging'); }));
dropZone.addEventListener('drop', event => { if (event.dataTransfer.files[0]) { fileInput.files = event.dataTransfer.files; fileInput.dispatchEvent(new Event('change')); } });

document.querySelector('#import-button').addEventListener('click', async () => {
  const error = document.querySelector('#import-error'); error.hidden = true;
  if (!fileInput.files[0]) { error.textContent = 'Выберите файл XLSX.'; error.hidden = false; return; }
  const button = document.querySelector('#import-button'); button.disabled = true; button.textContent = 'Загружаем…';
  try {
    const body = new FormData(); body.append('file', fileInput.files[0]);
    const response = await fetch('/api/import', {method:'POST', body}); const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Не удалось импортировать файл.');
    const labels = {total_rows:'Строк',created:'Добавлено',duplicates:'Повторы',blocked:'Не связываться',queued:'В обработке',errors:'Ошибки'};
    const stats = document.querySelector('#import-stats'); stats.innerHTML = Object.entries(labels).map(([key,label]) => `<div><b>${data[key]}</b><span>${label}</span></div>`).join(''); stats.hidden = false; await loadLeads();
  } catch (failure) { error.textContent = failure.message; error.hidden = false; }
  finally { button.disabled = false; button.textContent = 'Загрузить и обработать'; }
});
function safe(value) { const node=document.createElement('span'); node.textContent=value||'—'; return node.innerHTML; }
function webLink(lead) { const value=lead.source_url||lead.cm_url||''; return /^https?:\/\//i.test(value)?value:''; }
async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Clipboard API is commonly denied on plain HTTP; use the legacy selection fallback.
    }
  }
  const textarea=document.createElement('textarea');
  textarea.value=text;
  textarea.setAttribute('readonly','');
  textarea.style.position='fixed';
  textarea.style.left='-9999px';
  textarea.style.opacity='0';
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0,textarea.value.length);
  let copied=false;
  try { copied=document.execCommand('copy'); } finally { textarea.remove(); }
  if (!copied) throw new Error('Copy command was rejected');
}
async function copyLeadMessage(button,message) {
  const error=document.querySelector('#import-error');
  try {
    await copyText(message);
    error.hidden=true;
    button.textContent='Скопировано ✓';
    setTimeout(()=>{ if(button.isConnected)button.textContent='Скопировать сообщение'; },1700);
  } catch {
    error.textContent='Не удалось скопировать сообщение. Выделите текст сообщения вручную.';
    error.hidden=false;
  }
}
async function loadLeads() {
  try {
    const response=await fetch('/api/leads'); if(!response.ok)return; const data=await response.json(); const active=data.status.new+data.status.processing;
    document.querySelector('#progress').textContent=active?`Обрабатывается: ${active}`:`Готово: ${data.status.ready}, исключено: ${data.status.do_not_contact}`;
    document.querySelector('#leads').innerHTML=data.items.map(lead=>`<article class="lead ${lead.analysis_status==='do_not_contact'?'lead-blocked':''}"><div class="lead-title"><div><h3>${safe([lead.brand,lead.model].filter(Boolean).join(' '))}</h3><p>${safe(lead.year)} · ${safe(lead.mileage)} км · ${safe(lead.price)} ₽</p></div><span>${safe(lead.source||'CM.Expert')}</span></div><p class="lead-city">${safe(lead.city)} · ${safe(lead.analysis_status)}</p>${['do_not_contact','error'].includes(lead.analysis_status)?`<div class="lead-reason">${safe(lead.reason)}</div>`:`<h4>Зацепка AI</h4><p>${safe(lead.hook)}</p><h4>Готовое сообщение</h4><p class="lead-message">${safe(lead.message)}</p>`}<div class="lead-actions">${lead.message?`<button data-copy="${lead.id}">Скопировать сообщение</button>`:''}${webLink(lead)?`<a href="${safe(webLink(lead))}" target="_blank" rel="noopener noreferrer">Открыть объявление</a>`:''}<button data-status="contacted" data-id="${lead.id}">Связались</button><button data-status="skipped" data-id="${lead.id}">Пропустить</button></div></article>`).join('')||'<p class="empty">Пока нет импортированных объявлений.</p>';
    document.querySelectorAll('[data-copy]').forEach(button=>{
      const lead=data.items.find(item=>item.id===Number(button.dataset.copy));
      button.onclick=()=>copyLeadMessage(button,lead.message);
    });
    document.querySelectorAll('[data-status]').forEach(button=>button.onclick=async()=>{await fetch(`/api/leads/${button.dataset.id}/status`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:button.dataset.status})});loadLeads();});
    clearTimeout(pollTimer); if(active)pollTimer=setTimeout(loadLeads,1800);
  } catch { document.querySelector('#progress').textContent='Не удалось обновить список'; }
}
