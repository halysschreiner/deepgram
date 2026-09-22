export function timestamp(seconds = 0) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  return [Math.floor(value / 3600), Math.floor(value / 60) % 60, value % 60].map(n => String(n).padStart(2, '0')).join(':');
}

function escapeMarkdown(value) {
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/[\\`*_{}\[\]()#+.!|~-]/g, '\\$&');
}

export function hasSpeech(result) {
  return (result.results?.channels || []).some(channel => channel.alternatives?.[0]?.transcript?.trim()) ||
    (result.results?.utterances || []).some(item => item.transcript?.trim());
}

export function renderTranscript(result, format, { times = false, speakers = true, filename = 'Transcrição' } = {}) {
  if (format === 'json') return JSON.stringify(result, null, 2) + '\n';
  const markdown = format === 'md';
  const text = value => markdown ? escapeMarkdown(value) : String(value);
  const channels = result.results?.channels || [];
  const utterances = result.results?.utterances || [];
  const useSegments = utterances.length > 0 && (times || (speakers && utterances.some(item => item.speaker != null)));
  let parts = [];
  if (useSegments) {
    parts = utterances.map(item => {
      const labels = [];
      if (times) labels.push(timestamp(item.start));
      if (channels.length > 1) labels.push(`Canal ${Number(item.channel ?? 0) + 1}`);
      if (speakers && item.speaker != null) labels.push(`Pessoa ${Number(item.speaker) + 1}`);
      const prefix = labels.join(' · ');
      return (prefix ? (markdown ? `**${prefix}**\n\n` : `[${prefix}] `) : '') + text(item.transcript || '');
    });
  } else {
    parts = channels.map((channel, index) => {
      const alternative = channel.alternatives?.[0] || {};
      const paragraphs = alternative.paragraphs?.paragraphs;
      const body = paragraphs?.length
        ? paragraphs.map(p => (p.sentences || []).map(s => s.text || '').join(' ')).join('\n\n')
        : alternative.transcript || '';
      const heading = channels.length > 1 ? (markdown ? `## Canal ${index + 1}\n\n` : `Canal ${index + 1}\n\n`) : '';
      return heading + text(body);
    });
  }
  const body = parts.filter(Boolean).join('\n\n');
  return (markdown ? `# ${text(filename.replace(/[\r\n]+/g, ' '))}\n\n` : '') + body + '\n';
}

export function downloadName(filename, format) {
  const basename = filename.split(/[\\/]/).pop().replace(/\.[^.]+$/, '').replace(/[\x00-\x1f<>:"/\\|?*]/g, '_').replace(/[. ]+$/g, '').slice(0, 120);
  return `${basename || 'transcricao'}.${format}`;
}

export function estimateCost(pricing, seconds, options) {
  if (options.model !== 'nova-3' || options.language === 'auto' || options.mip_opt_out || options.multichannel) return null;
  if (!Number.isFinite(seconds) || seconds <= 0) return null;
  const rate = (options.language === 'multi' ? pricing.nova3_multi : pricing.nova3_mono) + (options.terms.trim() ? pricing.keyterm : 0);
  return seconds / 60 * rate;
}
