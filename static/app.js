import { timestamp, hasSpeech, renderTranscript, downloadName, estimateCost } from './transcript.mjs';

const $ = id => document.getElementById(id);
const extensions = /\.(mp3|wav|m4a|ogg|opus|flac|aac|mp4|webm|aiff|aif|amr|wma)$/i;
const booleanOptions = ['smart_format', 'punctuate', 'paragraphs', 'multichannel', 'filler_words', 'profanity_filter', 'mip_opt_out'];
let config = null, selectedFile = null, audioURL = null, duration = null, busy = false, result = null, run = null;
let timer = null;
let balanceLoading = false;

function error(message) { $('error').textContent = message; $('error').hidden = !message; }
function fileSize(bytes) {
  const small = bytes < 1024 * 1024;
  const value = bytes / (small ? 1024 : 1024 * 1024);
  return `${value.toLocaleString('pt-BR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} ${small ? 'KB' : 'MB'}`;
}
function options() {
  return { model: $('model').value, language: $('language').value,
    ...Object.fromEntries(booleanOptions.map(key => [key, $(key).checked])),
    diarize_model: $('diarize').checked ? $('diarize_model').value : '',
    utt_split: Number($('utt_split').value), terms: $('terms').value, replacements: $('replacements').value };
}
function updateSubmit() {
  $('submit').disabled = busy || !selectedFile || !config?.configured;
  $('clear').disabled = busy || (!result && !selectedFile);
}
function updateCost() {
  if (!config) return;
  const opts = options();
  const cost = estimateCost(config.pricing, duration, opts);
  $('cost').textContent = !selectedFile ? 'Selecione um arquivo' : cost == null ? 'Consultar tarifa no console' : `≈ ${cost.toLocaleString('pt-BR', { style: 'currency', currency: 'USD', minimumFractionDigits: 4 })}`;
  $('cost-note').textContent = 'Referência Pay As You Go de 21/09/2026. O saldo é consultado separadamente acima.';
  if (opts.multichannel) $('cost-note').textContent = 'Cada canal é cobrado separadamente. O navegador não informa a quantidade de canais.';
  else if (opts.mip_opt_out) $('cost-note').textContent = 'A exclusão do programa de melhoria pode alterar o preço. Consulte sua conta.';
  else if (opts.model === 'nova-2' || opts.language === 'auto') $('cost-note').textContent = 'Não estimamos esta combinação. Confira a tarifa na Deepgram antes de enviar.';
  else if (selectedFile && duration == null) $('cost-note').textContent = 'Não foi possível ler a duração no navegador. Você ainda pode enviar o arquivo.';
}
function updateCompatibility() {
  const english = $('language').value === 'en';
  for (const id of ['filler_words', 'profanity_filter']) { $(id).disabled = !english; if (!english) $(id).checked = false; }
  $('diarize_model').disabled = !$('diarize').checked;
  const nova3 = $('model').value === 'nova-3';
  $('terms-label').textContent = nova3 ? 'Adicional pago' : 'Keywords';
  $('terms-hint').textContent = nova3 ? 'Um termo por linha, sem pesos. Até 50 termos; no Nova-3, a API limita o total a 500 tokens. Adicional: US$ 0,0013/min.' : 'Um termo por linha, sem pesos. Enviado como Keywords do Nova-2. Consulte a tarifa da sua conta.';
  $('language-hint').hidden = !['auto', 'multi'].includes($('language').value);
  $('language-hint').textContent = $('language').value === 'multi' ? 'Reconhece alternância entre português, inglês, espanhol, francês, alemão, hindi, russo, japonês, italiano e holandês.' : 'Detecta o idioma predominante; não é o modo de alternância entre idiomas.';
  updateCost();
}
function populateLanguages() {
  const previous = $('language').value || 'pt-BR';
  const model = config.models.find(item => item.id === $('model').value);
  $('language').replaceChildren(...config.languages.filter(item => model.languages.includes(item.id)).map(item => new Option(item.name, item.id)), new Option('Detectar automaticamente', 'auto'));
  if (model.multilingual) $('language').add(new Option('Vários idiomas (multilíngue)', 'multi'));
  $('language').value = [...$('language').options].some(item => item.value === previous) ? previous : 'pt-BR';
  $('model-hint').textContent = model.description;
  updateCompatibility();
}
async function loadConfig() {
  try {
    const response = await fetch('/api/config', { cache: 'no-store' });
    if (!response.ok) throw new Error();
    config = await response.json();
    const previous = $('model').value;
    $('model').replaceChildren(...config.models.map(item => new Option(item.name, item.id)));
    if (previous) $('model').value = previous;
    populateLanguages();
    $('connection').textContent = config.configured ? 'Chave configurada' : 'Chave não configurada';
    $('connection').classList.toggle('ready', config.configured);
    $('setup').hidden = config.configured;
    if (!selectedFile) $('file-meta').textContent = `Um arquivo por vez · até ${config.max_upload_mb} MB`;
    error(''); updateSubmit(); loadBalance();
  } catch {
    config = null; updateSubmit();
    $('connection').textContent = 'Servidor indisponível';
    $('balance-value').textContent = 'Indisponível';
    $('balance-note').textContent = 'Confira o container e atualize a página.';
    $('refresh-balance').disabled = true;
    error('Não foi possível carregar a configuração. Confira o container e atualize a página.');
  }
}
async function loadBalance() {
  if (balanceLoading) return;
  if (!config?.configured) {
    $('balance-value').textContent = '—';
    $('balance-note').textContent = 'Configure sua chave para consultar os créditos.';
    $('refresh-balance').disabled = true;
    return;
  }
  balanceLoading = true;
  $('refresh-balance').disabled = true;
  $('balance-section').setAttribute('aria-busy', 'true');
  $('balance-section').classList.remove('unavailable');
  $('balance-value').textContent = 'Consultando…';
  $('balance-note').textContent = 'Buscando o saldo informado pela Deepgram.';
  try {
    const response = await fetch('/api/balance', { cache: 'no-store', headers: { 'X-App-Token': config.token }, signal: AbortSignal.timeout(35000) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível consultar o saldo.');
    $('balance-value').textContent = data.balances.map(item => {
      const amount = Number(item.amount);
      try { return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: item.units, minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(amount); }
      catch { return `${amount.toLocaleString('pt-BR', { maximumFractionDigits: 4 })} ${item.units}`; }
    }).join(' · ');
    const checked = new Date(data.checked_at).toLocaleTimeString('pt-BR');
    $('balance-note').textContent = `Consultado às ${checked}. O saldo pode levar um tempo para refletir o último uso.`;
  } catch (failure) {
    $('balance-value').textContent = 'Indisponível';
    $('balance-section').classList.add('unavailable');
    $('balance-note').textContent = failure.name === 'TimeoutError' ? 'A consulta demorou demais. Tente atualizar novamente.' : failure instanceof TypeError ? 'Falha de conexão ao consultar o saldo. Tente atualizar novamente.' : failure.message;
  } finally {
    balanceLoading = false;
    $('refresh-balance').disabled = false;
    $('balance-section').setAttribute('aria-busy', 'false');
  }
}
$('refresh-balance').addEventListener('click', loadBalance);
function releaseAudio() {
  $('audio').pause(); $('audio').removeAttribute('src'); $('audio').load(); $('audio').hidden = true;
  if (audioURL) URL.revokeObjectURL(audioURL);
  audioURL = null; duration = null;
}
function chooseFile(file) {
  if (busy || !file) return;
  if (!extensions.test(file.name)) { error('Selecione um arquivo MP3, WAV, M4A, OGG, OPUS, FLAC, AAC, MP4, WEBM, AIFF, AMR ou WMA.'); return; }
  if (!file.size || file.size > (config?.max_upload_mb || 500) * 1024 * 1024) { error(`O arquivo deve ter conteúdo e no máximo ${config?.max_upload_mb || 500} MB.`); return; }
  error(''); releaseAudio(); selectedFile = file;
  $('file-title').textContent = file.name;
  $('file-hint').textContent = 'Clique para trocar o arquivo';
  const size = fileSize(file.size);
  $('file-meta').textContent = size;
  audioURL = URL.createObjectURL(file);
  $('audio').src = audioURL; $('audio').hidden = false;
  updateSubmit(); updateCost();
}
$('audio').addEventListener('loadedmetadata', () => {
  duration = Number.isFinite($('audio').duration) && $('audio').duration > 0 ? $('audio').duration : null;
  if (selectedFile) $('file-meta').textContent = `${fileSize(selectedFile.size)}${duration ? ' · ' + timestamp(duration) : ''}`;
  updateCost();
});
$('audio').addEventListener('error', () => { duration = null; $('audio').hidden = true; updateCost(); });
$('file').addEventListener('change', () => chooseFile($('file').files[0]));
for (const type of ['dragenter', 'dragover']) $('dropzone').addEventListener(type, event => { event.preventDefault(); if (!busy) $('dropzone').classList.add('dragging'); });
for (const type of ['dragleave', 'drop']) $('dropzone').addEventListener(type, event => { event.preventDefault(); $('dropzone').classList.remove('dragging'); });
$('dropzone').addEventListener('drop', event => { if (busy) return; if (event.dataTransfer.files.length !== 1) { error('Arraste apenas um arquivo por vez.'); return; } chooseFile(event.dataTransfer.files[0]); });
window.addEventListener('dragover', event => event.preventDefault());
window.addEventListener('drop', event => event.preventDefault());
$('model').addEventListener('change', populateLanguages);
$('language').addEventListener('change', updateCompatibility);
$('diarize').addEventListener('change', updateCompatibility);
$('input-fields').addEventListener('input', updateCost);
$('reload-config').addEventListener('click', loadConfig);

function rendered() {
  return renderTranscript(result, $('format').value, { times: $('timestamps').checked, speakers: $('speakers').checked, filename: run.filename });
}
function showResult() {
  const json = $('format').value === 'json';
  $('timestamps').disabled = json; $('speakers').disabled = json;
  $('preview').classList.toggle('code', json || $('format').value === 'md');
  if (!result) return;
  $('preview').textContent = rendered();
  $('preview').hidden = false; $('empty').hidden = true;
  $('download').disabled = false; $('copy').disabled = false;
}
for (const id of ['format', 'timestamps', 'speakers']) $(id).addEventListener('change', showResult);
$('download').addEventListener('click', () => {
  if (!result) return;
  const format = $('format').value;
  const mime = { txt: 'text/plain', md: 'text/markdown', json: 'application/json' }[format];
  const url = URL.createObjectURL(new Blob([rendered()], { type: `${mime};charset=utf-8` }));
  const link = document.createElement('a'); link.href = url; link.download = downloadName(run.filename, format);
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  $('result-status').textContent = 'Download solicitado. Você pode escolher outro formato sem transcrever novamente.';
});
$('copy').addEventListener('click', async () => {
  if (!result) return;
  try { await navigator.clipboard.writeText(rendered()); $('result-status').textContent = 'Texto copiado.'; }
  catch { $('result-status').textContent = 'A cópia foi bloqueada pelo navegador. Selecione o texto ou baixe o arquivo.'; }
});
function clearResult() {
  result = null; run = null; $('preview').textContent = ''; $('preview').hidden = true;
  $('empty').hidden = false; $('result-meta').hidden = true; $('result-meta').textContent = '';
  $('result-status').textContent = ''; $('download').disabled = true; $('copy').disabled = true;
}
$('clear').addEventListener('click', () => {
  if (busy) return;
  clearResult(); selectedFile = null; $('file').value = ''; releaseAudio(); error('');
  $('file-title').textContent = 'Selecione ou arraste um áudio';
  $('file-hint').textContent = 'MP3, WAV, M4A, OGG, OPUS, FLAC e outros';
  $('file-meta').textContent = `Um arquivo por vez · até ${config?.max_upload_mb || 500} MB`;
  $('submit').innerHTML = 'Transcrever áudio <span aria-hidden="true">→</span>';
  updateSubmit(); updateCost(); $('file').focus();
});
function send(file, options) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/transcribe'); xhr.setRequestHeader('X-App-Token', config.token);
    // The file goes up as the raw body, so the app never buffers it. Headers carry only
    // latin-1, and both filenames and keyterms are accented here, hence the encoding.
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name));
    xhr.setRequestHeader('X-Options', encodeURIComponent(JSON.stringify(options)));
    xhr.responseType = 'json';
    xhr.upload.addEventListener('progress', event => {
      if (event.lengthComputable) { const percent = Math.round(event.loaded / event.total * 100); $('progress').value = percent; $('progress-label').textContent = `Enviando ao aplicativo local… ${percent}%`; }
    });
    xhr.upload.addEventListener('load', () => {
      $('progress').removeAttribute('value'); $('progress-label').textContent = 'Transcrevendo na Deepgram…';
      const start = Date.now();
      timer = setInterval(() => { $('progress-hint').textContent = `${timestamp((Date.now() - start) / 1000)} de espera · Mantenha esta página aberta. A Deepgram não informa um percentual de processamento.`; }, 1000);
    });
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300 && xhr.response?.result) resolve(xhr.response.result);
      else reject(new Error((xhr.response?.error || 'Não foi possível concluir a transcrição. Confira o console antes de reenviar.') + (xhr.response?.request_id ? ` ID da requisição: ${xhr.response.request_id}` : '')));
    };
    xhr.onerror = () => reject(new Error('A conexão com o aplicativo foi interrompida. A transcrição pode ter sido cobrada; confira o console da Deepgram antes de reenviar.'));
    xhr.send(file);
  });
}
$('transcribe-form').addEventListener('submit', async event => {
  event.preventDefault(); if (busy || !selectedFile || !config?.configured) return;
  const submitted = { filename: selectedFile.name, options: options() };
  clearResult(); error(''); busy = true; $('audio').pause();
  $('input-fields').disabled = true; $('result-section').setAttribute('aria-busy', 'true');
  $('submit').textContent = 'Transcrevendo…'; $('empty').hidden = true; $('progress-area').hidden = false;
  $('progress').value = 0; $('progress-label').textContent = 'Enviando áudio…'; $('progress-hint').textContent = 'Mantenha esta página aberta até concluir.';
  updateSubmit();
  try {
    result = await send(selectedFile, submitted.options); run = submitted;
    const seconds = result.metadata?.duration;
    $('result-meta').textContent = `${run.filename} · ${run.options.model}${Number.isFinite(seconds) ? ' · ' + timestamp(seconds) : ''}`;
    $('result-meta').hidden = false;
    $('result-status').textContent = hasSpeech(result) ? 'Transcrição concluída. Revise nomes, números e termos específicos.' : 'Nenhuma fala foi reconhecida. O JSON completo está disponível para inspeção.';
    showResult();
  } catch (failure) { error(failure.message); $('empty').hidden = false; }
  finally {
    busy = false; clearInterval(timer); timer = null; $('input-fields').disabled = false;
    $('result-section').setAttribute('aria-busy', 'false'); $('progress-area').hidden = true;
    $('submit').innerHTML = `${result ? 'Transcrever novamente' : 'Transcrever áudio'} <span aria-hidden="true">→</span>`;
    updateCompatibility(); updateSubmit(); loadBalance();
  }
});
window.addEventListener('beforeunload', event => { if (busy) { event.preventDefault(); event.returnValue = ''; } });
window.addEventListener('pagehide', () => { if (!busy) { clearResult(); selectedFile = null; $('file').value = ''; releaseAudio(); } });
window.addEventListener('pageshow', event => { if (event.persisted) window.location.reload(); });
loadConfig();
