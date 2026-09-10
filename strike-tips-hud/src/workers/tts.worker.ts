import { pipeline, type TextToAudioPipeline } from '@huggingface/transformers';

// Supertonic: modern single-precision TTS built for transformers.js v4.
// (SpeechT5 was dropped: its q8/int8 graphs rename decoder inputs so the
// pipeline can't feed speaker embeddings, and fp16 fails ORT graph fusion.)
const MODEL_ID = 'onnx-community/Supertonic-TTS-ONNX';
// Long verdicts take too long to synthesize on phones; cap the input.
const MAX_CHARS = 600;

let synth: TextToAudioPipeline | null = null;
let loadPromise: Promise<void> | null = null;

function loadSynth(onProgress: (p: number, text: string) => void): Promise<void> {
  if (synth) return Promise.resolve();
  if (!loadPromise) {
    loadPromise = (async () => {
      const pipe = await pipeline('text-to-audio', MODEL_ID, {
        progress_callback: (p: any) => {
          onProgress(
            typeof p?.progress === 'number' ? p.progress / 100 : 0,
            String(p?.status ?? p?.text ?? 'loading')
          );
        },
      });
      synth = pipe as TextToAudioPipeline;
    })().catch((err) => {
      loadPromise = null;
      throw err;
    });
  }
  return loadPromise;
}

function flatten(audio: Float32Array | Float32Array[]): Float32Array {
  if (!Array.isArray(audio)) return audio;
  const total = audio.reduce((n, c) => n + c.length, 0);
  const out = new Float32Array(total);
  let offset = 0;
  for (const chunk of audio) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

self.onmessage = async (e: MessageEvent) => {
  const { type, text, voiceData, id } = e.data ?? {};
  const progress = (p: number, t: string) =>
    self.postMessage({ type: 'PROGRESS', id, progress: p, text: t });

  try {
    if (type === 'LOAD') {
      await loadSynth(progress);
      self.postMessage({ type: 'READY', id });
      return;
    }
    if (type === 'SPEAK') {
      const input = String(text ?? '').slice(0, MAX_CHARS).trim();
      if (!input) {
        self.postMessage({ type: 'RESULT', id, audio: null, samplingRate: 16000 });
        return;
      }
      if (!(voiceData instanceof ArrayBuffer) || voiceData.byteLength === 0) {
        throw new Error('Missing speaker voice data');
      }
      await loadSynth(progress);
      // Pass raw samples: the pipeline wraps Float32Array itself and reshapes
      // to the model's style dim. (Do NOT pre-wrap in a Tensor — dims differ
      // per model and a wrong guess throws a batch-size error.)
      const speaker_embeddings = new Float32Array(voiceData);
      const out = await synth!(input, { speaker_embeddings });
      const samples = flatten(out.audio);
      if (!samples.length) throw new Error('Synthesizer returned no audio');
      const copy = samples.slice().buffer as ArrayBuffer;
      self.postMessage(
        { type: 'RESULT', id, audio: copy, samplingRate: out.sampling_rate ?? 16000 },
        { transfer: [copy] }
      );
      return;
    }
    if (type === 'UNLOAD') {
      synth = null;
      loadPromise = null;
      self.postMessage({ type: 'UNLOADED', id });
    }
  } catch (err: any) {
    self.postMessage({ type: 'ERROR', id, error: String(err?.message ?? err) });
  }
};
