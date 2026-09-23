import { useEffect, useRef, useState } from 'react'
import { Volume2, Square } from 'lucide-react'

const LOCALES = {
  en: 'en-IN',
  hi: 'hi-IN',
  te: 'te-IN',
  ta: 'ta-IN',
  ml: 'ml-IN',
  sa: 'hi-IN',
}

/**
 * Free browser-native Read Aloud. No TTS API key is required.
 * Browser/OS voice availability varies; the selected language locale is used
 * so the browser can choose an appropriate installed voice.
 */
export default function ReadAloudButton({ text, lang, copy }) {
  const [speaking, setSpeaking] = useState(false)
  const utteranceRef = useRef(null)

  useEffect(() => {
    return () => window.speechSynthesis?.cancel()
  }, [text])

  function stop() {
    window.speechSynthesis?.cancel()
    setSpeaking(false)
  }

  function start() {
    if (!text || !window.speechSynthesis) return
    stop()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = LOCALES[lang] || 'en-IN'
    utterance.onstart = () => setSpeaking(true)
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    utteranceRef.current = utterance
    window.speechSynthesis.speak(utterance)
  }

  const disabled = !text || typeof window === 'undefined' || !window.speechSynthesis
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
      {speaking ? <Square size={14} /> : <Volume2 size={16} />}
    </button>
  )
}
