import { useEffect, useRef, useState } from 'react'
import { Volume2, Square, Loader2, AlertCircle } from 'lucide-react'
import { api } from '../api'

const LOCALES = {
  en: 'en-IN',
  hi: 'hi-IN',
  te: 'te-IN',
  ta: 'ta-IN',
  ml: 'ml-IN',
  sa: 'hi-IN',
}

// English uses the browser's reliable native voice. The five Indian-language
// paths use backend TTS in bounded sentence chunks; falling back to an
// unrelated browser voice often produced audio containing only numerals.
const BACKEND_TTS_LANGUAGES = new Set(['hi', 'te', 'ta', 'ml', 'sa'])
const BACKEND_TTS_CHUNK_CHARS = 1800

// speechSynthesis.getVoices() can return an empty array on the very first
// call after page load — Chrome in particular loads voices asynchronously
// and fires 'voiceschanged' once they're ready. Calling speak() before that
// fires, or with no matching voice found, doesn't error — it just produces
// no audio at all. The browser voice path is now English-only and reports
// an explicit error if it cannot find a suitable voice.
function getVoicesAsync() {
  return new Promise((resolve) => {
    if (!window.speechSynthesis) {
      resolve([])
      return
    }
    const existing = window.speechSynthesis.getVoices()
    if (existing.length > 0) {
      resolve(existing)
      return
    }
    const onVoicesChanged = () => {
      window.speechSynthesis.removeEventListener('voiceschanged', onVoicesChanged)
      resolve(window.speechSynthesis.getVoices())
    }
    window.speechSynthesis.addEventListener('voiceschanged', onVoicesChanged)
    // Some browsers never fire voiceschanged if voices were already
    // available synchronously by the time this promise executor ran, or
    // never fire it at all in certain embedded webviews — don't wait
    // forever for an event that may not come.
    setTimeout(() => {
      window.speechSynthesis.removeEventListener('voiceschanged', onVoicesChanged)
      resolve(window.speechSynthesis.getVoices())
    }, 1000)
  })
}

// Picking a voice by exact locale (utterance.lang = 'en-IN') and leaving it
// to the browser to find a match is unreliable: plenty of systems ship
// only 'en-US' or 'en-GB', never 'en-IN', and some browsers silently
// produce no audio rather than substituting a close variant. Matching on
// just the language prefix ('en', 'hi', ...) against every installed
// voice's own lang is far more likely to find something real. Falls back
// to null (browser's own default voice) rather than failing outright if
// nothing matches the prefix either — some sound is better than none.
function resolveVoice(voices, langCode) {
  const prefix = (langCode || 'en').split('-')[0].toLowerCase()
  const exact = voices.find((v) => v.lang?.toLowerCase() === langCode?.toLowerCase())
  if (exact) return exact
  const byPrefix = voices.find((v) => v.lang?.toLowerCase().startsWith(prefix))
  return byPrefix || null
}

/**
 * Read Aloud.
 *
 * Hindi, Telugu, Tamil, Malayalam, and Sanskrit call the backend's
 * Bhashini/Sarvam text-to-speech (app/asr.py's synthesize()) first, instead
 * of relying solely on the browser's installed voices. Most desktop/mobile
 * browsers ship an English voice but no Telugu/Tamil/Malayalam voice; when
 * window.speechSynthesis can't find a matching voice for the requested
 * lang, it may silently substitute an unrelated default voice (usually
 * English), which cannot pronounce the selected language's script.
 *
 * English deliberately stays on the browser's own voice and does not call
 * the backend at all. It was briefly routed through the backend too, on
 * the assumption that since synthesize() has no server-side language
 * restriction, sending English through it would be strictly more
 * consistent than special-casing it. That assumption didn't hold up:
 * Bhashini and Sarvam are both built for Indian-language speech, and
 * neither produced usable English audio in practice, so English calls
 * through them just failed silently. Browsers, meanwhile, have shipped a
 * reliable English voice for decades — the exact opposite of the gap the
 * backend route exists to fix for the other five languages — so English
 * goes straight to speakInBrowser(). Non-English backend failures are
 * shown explicitly instead of silently playing through an unrelated voice.
 */
export default function ReadAloudButton({ text, lang, copy, consentGiven = false }) {
  const [state, setState] = useState('idle') // idle | loading | speaking
  const [error, setError] = useState('')
  const audioRef = useRef(null)
  const cancelRef = useRef(null)

  useEffect(() => {
    return () => stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text])

  function stop() {
    cancelRef.current?.()
    cancelRef.current = null
    window.speechSynthesis?.cancel()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setState('idle')
  }

  async function speakInBrowser() {
    if (!text || !window.speechSynthesis) {
      setState('idle')
      return
    }
    let isCancelled = false
    const browserPlayback = {
      pause: () => {
        isCancelled = true
        window.speechSynthesis.cancel()
      },
    }
    audioRef.current = browserPlayback
    cancelRef.current = () => browserPlayback.pause()
    const targetLocale = LOCALES[lang] || 'en-IN'
    const voices = await getVoicesAsync()
    if (isCancelled) return
    const voice = resolveVoice(voices, targetLocale)
    if (lang !== 'en' && (!voice || !voice.lang?.toLowerCase().startsWith(lang))) {
      setError(copy.readAloudVoiceUnavailable || 'No browser voice is installed for this language.')
      setState('idle')
      audioRef.current = null
      cancelRef.current = null
      return false
    }

    // Chrome fails silently on texts longer than ~200-250 characters.
    // Split into sentences to avoid this.
    const chunks = text.match(/[^.!?]+[.!?]+|\s*[^.!?]+$/g) || [text]
    let chunkIndex = 0

    function speakNextChunk() {
      if (isCancelled || chunkIndex >= chunks.length) {
        setState('idle')
        if (audioRef.current === browserPlayback) {
          audioRef.current = null
          cancelRef.current = null
        }
        return
      }

      const chunk = chunks[chunkIndex].trim()
      if (!chunk) {
        chunkIndex++
        speakNextChunk()
        return
      }

      const utterance = new SpeechSynthesisUtterance(chunk)
      utterance.lang = voice?.lang || targetLocale
      if (voice) utterance.voice = voice

      utterance.onstart = () => setState('speaking')
      utterance.onerror = () => {
        setState('idle')
        if (audioRef.current === browserPlayback) {
          audioRef.current = null
          cancelRef.current = null
        }
      }
      utterance.onend = () => {
        chunkIndex++
        speakNextChunk()
      }

      window.speechSynthesis.speak(utterance)
    }

    speakNextChunk()
    return true
  }

  function splitForSynthesis(value, limit) {
    const sentences = value.match(/[^.!?।؟]+[.!?।؟]+|\s*[^.!?।؟]+$/g) || [value]
    const chunks = []
    let current = ''
    for (const sentence of sentences) {
      const next = current ? `${current} ${sentence.trim()}` : sentence.trim()
      if (next.length <= limit) {
        current = next
        continue
      }
      if (current) chunks.push(current)
      if (sentence.length <= limit) {
        current = sentence.trim()
      } else {
        for (let i = 0; i < sentence.length; i += limit) chunks.push(sentence.slice(i, i + limit))
        current = ''
      }
    }
    if (current) chunks.push(current)
    return chunks
  }

  function playAudioChunk(audioBase64, isCancelled) {
    return new Promise((resolve, reject) => {
      if (isCancelled()) {
        resolve()
        return
      }
      const audio = new Audio(`data:audio/wav;base64,${audioBase64}`)
      audio.onplay = () => setState('speaking')
      audio.onended = () => {
        if (audioRef.current === audio) audioRef.current = null
        resolve()
      }
      audio.onpause = () => {
        if (isCancelled()) resolve()
      }
      audio.onerror = () => reject(new Error('The audio response could not be played.'))
      audioRef.current = audio
      audio.play().catch(reject)
    })
  }

  async function start() {
    if (!text) return
    stop()
    setError('')

    if (BACKEND_TTS_LANGUAGES.has(lang)) {
      setState('loading')
      const playback = { cancelled: false }
      cancelRef.current = () => {
        playback.cancelled = true
        audioRef.current?.pause()
      }
      try {
        for (const chunk of splitForSynthesis(text, BACKEND_TTS_CHUNK_CHARS)) {
          if (playback.cancelled) return
          const res = await api.synthesizeSpeech({ text: chunk, language: lang, external_processing_consent: true })
          await playAudioChunk(res.audio_base64, () => playback.cancelled)
        }
        if (!playback.cancelled) setState('idle')
        return
      } catch (failure) {
        if (!playback.cancelled) {
          setError(failure?.message || copy.readAloudFailed || 'Speech synthesis failed for this language.')
          setState('idle')
        }
        return
      }
    }

    setState('loading')
    await speakInBrowser()
  }

  const speaking = state === 'speaking' || state === 'loading'
  const disabled = !text || !consentGiven
  return (
    <button
      type="button"
      onClick={speaking ? stop : start}
      disabled={disabled}
      title={disabled ? (!consentGiven ? copy.externalProcessingConsent : copy.readAloudNoAnswer) : speaking ? copy.readAloudStop : error || copy.readAloudStart}
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
      ) : error ? (
        <AlertCircle size={16} aria-label={error} />
      ) : (
        <Volume2 size={16} />
      )}
      {error && <span role="status" className="sr-only">{error}</span>}
    </button>
  )
}
