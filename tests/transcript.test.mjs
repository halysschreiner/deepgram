import test from 'node:test';
import assert from 'node:assert/strict';
import { timestamp, renderTranscript, downloadName, estimateCost, hasSpeech } from '../static/transcript.mjs';

const result = { metadata: { duration: 61 }, results: {
  channels: [{ alternatives: [{ transcript: 'Olá, Deepgram! Como vai?', paragraphs: { paragraphs: [
    { sentences: [{ text: 'Olá, Deepgram!' }] }, { sentences: [{ text: 'Como vai?' }] }
  ] } }] }],
  utterances: [{ start: 0, speaker: 0, transcript: 'Olá, Deepgram!' }, { start: 60.4, speaker: 1, transcript: 'Como vai?' }]
} };

test('TXT includes timestamps and handles speaker zero', () => {
  const text = renderTranscript(result, 'txt', { times: true });
  assert.match(text, /\[00:00:00 · Pessoa 1\] Olá, Deepgram!/);
  assert.match(text, /\[00:01:00 · Pessoa 2\] Como vai\?/);
});
test('plain text preserves paragraph boundaries when labels are disabled', () => {
  assert.equal(renderTranscript(result, 'txt', { speakers: false }), 'Olá, Deepgram!\n\nComo vai?\n');
});
test('Markdown escapes transcript and filename markup', () => {
  const dangerous = { results: { channels: [{ alternatives: [{ transcript: '<script>*texto*</script>' }] }] } };
  const text = renderTranscript(dangerous, 'md', { filename: '[nome](url).mp3' });
  assert.match(text, /&lt;script&gt;/); assert.ok(text.includes('\\*texto\\*'));
  assert.ok(text.startsWith('# \\[nome\\]\\(url\\)'));
});
test('JSON download preserves the entire API response', () => {
  assert.deepEqual(JSON.parse(renderTranscript(result, 'json')), result);
});
test('multi-channel recordings retain both channels', () => {
  const multi = structuredClone(result);
  multi.results.channels.push({ alternatives: [{ transcript: 'Segundo canal' }] });
  assert.match(renderTranscript(multi, 'txt', { speakers: false }), /Canal 2\n\nSegundo canal/);
  multi.results.utterances[1].channel = 1;
  assert.match(renderTranscript(multi, 'txt', { times: true }), /Canal 2 · Pessoa 2/);
});
test('empty results and unsafe names', () => {
  assert.equal(hasSpeech({ results: { channels: [] } }), false);
  assert.equal(hasSpeech(result), true);
  assert.equal(downloadName('../../áudio.mp3', 'txt'), 'áudio.txt');
  assert.equal(downloadName('a:b?.wav', 'md'), 'a_b_.md');
  assert.equal(timestamp(3601.9), '01:00:01');
});
test('estimates include terms and omit unknown price combinations', () => {
  const pricing = { nova3_mono: .0043, nova3_multi: .0052, keyterm: .0013 };
  const options = { model: 'nova-3', language: 'pt-BR', terms: '' };
  assert.equal(estimateCost(pricing, 60, options), .0043);
  assert.equal(estimateCost(pricing, 60, { ...options, terms: 'Deepgram' }), .0056);
  for (const extra of [{ model: 'nova-2' }, { language: 'auto' }, { mip_opt_out: true }, { multichannel: true }]) {
    assert.equal(estimateCost(pricing, 60, { ...options, ...extra }), null);
  }
});
