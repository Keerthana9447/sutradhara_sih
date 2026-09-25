import { useEffect, useRef, useState } from 'react'
import { Volume2, Square, Loader2 } from 'lucide-react'
import { api } from '../api'

const LOCALES = {
  en: 'en-IN',
  hi: 'hi-IN',
  te: 'te-IN',
  ta: 'ta-IN',
  ml: 'ml-IN',
  sa: 'hi-IN',
}

// Backend voice synthesis (Sarvam Bulbul / Bhashini, app/asr.py) only
// covers these languages — see _LANGUAGE_CODES / SUPPORTED_ASR_LANGUAGES
// server-side. Sanskrit falls straight to the browser voice like before.
const BACKEND_TTS_LANGUAGES = new Set(['en', 'hi', 'te', 'ta', 'ml'])

// TTSRequest caps text at 2500 chars server-side (app/schemas.py) — a
// longer answer skips the backend call entirely rather than sending a
// request that's guaranteed to fail.
const BACKEND_TTS_MAX_CHARS = 2500

/**
 * Read Aloud.
 *
 * For non-English answers this now calls the backend's Sarvam/Bhashini
 * text-to-speech first (app/asr.py's synthesize()) instead of relying
 * solely on the browser's installed voices. Most desktop/mobile browsers
 * ship an English voice but no Telugu/Tamil/Malayalam voice; when
 * window.speechSynthesis can't find a matching voice for the requested
 * lang, it silently substitutes whatever default voice IS installed
 * (usually English) — which can't pronounce non-Latin script at all, but
 * still vocalizes the locale-independent digits it recognizes (e.g.
 * "1970"). That mismatch is what made Read Aloud sound like it was only
 * reading years: everything except the digits was being silently skipped
 * by a voice that was never the right one to begin with.
 *
 * English keeps using the free browser voice directly — it already works
 * reliably and doesn't need a network round trip. If the backend call
 * fails, isn't configured, or the text is too long for it, this falls
 * back to the browser voice anyway, so a person with no network still
 * gets *something* rather than silence — same degrade path as before,
 * just no longer the first choice for Indian languages.
 */
export default function ReadAloudButton({ text, lang, copy }) {
  const [state, setState] = useState('idle') // idle | loading | speaking
  const audioRef = useRef(null)

  useEffect(() => {
    return () => stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text])

  function stop() {
    window.speechSynthesis?.cancel()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setState('idle')
  }

  function speakInBrowser() {
    if (!text || !window.speechSynthesis) {
      setState('idle')
      return
    }
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = LOCALES[lang] || 'en-IN'
    utterance.onstart = () => setState('speaking')
    utterance.onend = () => setState('idle')
    utterance.onerror = () => setState('idle')
    window.speechSynthesis.speak(utterance)
  }

  async function start() {
    if (!text) return
    stop()

    const useBackendVoice =
      lang !== 'en' && BACKEND_TTS_LANGUAGES.has(lang) && text.length <= BACKEND_TTS_MAX_CHARS

    if (useBackendVoice) {
      setState('loading')
      try {
        const res = await api.synthesizeSpeech({ text, language: lang })
        const audio = new Audio(`data:audio/wav;base64,${res.audio_base64}`)
        audio.onplay = () => setState('speaking')
        audio.onended = () => setState('idle')
        audio.onerror = () => setState('idle')
        audioRef.current = audio
        await audio.play()
        return
      } catch {
        // Sarvam/Bhashini unavailable, unconfigured, or errored — fall
        // through to the browser voice below rather than leaving the
        // person with nothing.
      }
    }

    speakInBrowser()
  }

  const speaking = state === 'speaking' || state === 'loading'
  const disabled = !text
  return (
    <button
      type="button"
      onClick={speaking ? stop : start}
      disabled={disabled}
      title={disabled ? copy.readAloudNoAnswer : speaking ? copy.readAloudStop : copy.readAloudStart}
      aria-pressed={speaking}
      className={`inline-flex items-center justify-center w-9 h-9 rounded-md border transition-colors shrink-0 ${
        speaking
          ? 'border-gold bg-gold-light/20 text-gold-dark animate-pulse'
          : 'border-hairline text-green hover:bg-green-pale'
      } disabled:opacity-40 disabled:hover:bg-transparent disabled:cursor-not-allowed`}
    >
      {state === 'loading' ? (
        <Loader2 size={16} className="animate-spin" />
      ) : speaking ? (
        <Square size={14} />
      ) : (
        <Volume2 size={16} />
      )}
    </button>
  )
}
