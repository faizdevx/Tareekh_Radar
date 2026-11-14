// Read-aloud (on-device text-to-speech) and speech-to-text for the diary.
// Note: in Chrome, speech-to-text sends the audio to Google's speech service; the UI says so before use.
export const canSpeak = () => typeof window !== "undefined" && "speechSynthesis" in window;
export const canListen = () => typeof window !== "undefined" && !!(window.SpeechRecognition || window.webkitSpeechRecognition);

let voicesReady = null;
function voices() {
  voicesReady ??= new Promise((res) => {
    const v = speechSynthesis.getVoices();
    if (v.length) return res(v);
    speechSynthesis.addEventListener("voiceschanged", () => res(speechSynthesis.getVoices()), { once: true });
    setTimeout(() => res(speechSynthesis.getVoices()), 1500);
  });
  return voicesReady;
}

/** Speak text in Hindi or English; resolves false if no voice for that language exists on the device. */
export async function speak(text, lang) {
  if (!canSpeak()) return false;
  speechSynthesis.cancel();
  const want = lang === "hi" ? "hi" : "en";
  const list = await voices();
  const voice = list.find((v) => v.lang?.toLowerCase().startsWith(want + "-in")) || list.find((v) => v.lang?.toLowerCase().startsWith(want));
  if (!voice && want === "hi") return false;
  const u = new SpeechSynthesisUtterance(String(text).slice(0, 4000));
  u.lang = want === "hi" ? "hi-IN" : "en-IN";
  if (voice) u.voice = voice;
  u.rate = 0.95;
  speechSynthesis.speak(u);
  return true;
}
export const stopSpeaking = () => canSpeak() && speechSynthesis.cancel();

/** Start dictation; calls onText(finalText) and onEnd(). Returns a stop function, or null if unsupported. */
export function listen(lang, onText, onEnd) {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!R) return null;
  const r = new R();
  r.lang = lang === "hi" ? "hi-IN" : "en-IN";
  r.interimResults = false;
  r.continuous = false;
  r.onresult = (e) => onText([...e.results].map((x) => x[0].transcript).join(" "));
  r.onerror = () => onEnd?.();
  r.onend = () => onEnd?.();
  r.start();
  return () => r.stop();
}
