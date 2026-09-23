import { useEffect, useRef, useState } from 'react'
import { Mic, Square, Loader2, AlertCircle } from 'lucide-react'

/**
 * Browser-native speech recognition. This keeps the default voice path free:
 * no Sarvam/Google API key is required. Chrome/Edge provide the most reliable
 * implementation. The selected Sutradhara language is mapped to its India
 * locale so Telugu/Hindi/Tamil/Malayalam input is recognized appropriately.
 */
const LOCALES = {
  en: 'en-IN',
  hi: 'hi-IN',
  te: 'te-IN',
  ta: 'ta-IN',
  ml: 'ml-IN',
  sa: 'hi-IN', // browser support for Sanskrit varies; Hindi is the closest fallback
}

function getRecognition() {
  if (typeof window === 'undefined') return null
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) return null
  return SpeechRecognition
}

export default function MicButton({ sourceLanguage, onTranscribed, copy }) {
  const [state, setState] = useState('idle') // idle | recording | transcribing | error
  const [errorMsg, setErrorMsg] = useState('')
  const recognitionRef = useRef(null)
  const finalTextRef = useRef('')

  const Recognition = getRecognition()
  const supported = !!Recognition

  useEffect(() => () => recognitionRef.current?.abort(), [])

  function startRecording() {
    setErrorMsg('')
    if (!Recognition) {
      setState('error')
      setErrorMsg(copy.micNotSupported)
      return
    }

    try {
      const recognition = new Recognition()
      recognition.lang = LOCALES[sourceLanguage] || 'en-IN'
      recognition.continuous = false
      recognition.interimResults = false
      recognition.maxAlternatives = 1
      finalTextRef.current = ''

      recognition.onstart = () => setState('recording')
      recognition.onresult = (event) => {
        const text = Array.from(event.results)
          .map((result) => result[0]?.transcript || '')
          .join(' ')
          .trim()
        finalTextRef.current = text
      }
      recognition.onerror = (event) => {
        const messages = {
  notallowed: copy.micPermissionDenied,
  "service-not-allowed": copy.micNotSupported,
  "audio-capture": copy.micNotSupported,
  network: copy.micTranscribeFailed,
};
        setErrorMsg(messages[event.error] || copy.micTranscribeFailed)
        setState('error')
      }
      recognition.onend = () => {
        const text = finalTextRef.current
        if (text) {
          onTranscribed(text)
          setState('idle')
        } else if (state !== 'error') {
          setErrorMsg(copy.micTranscribeFailed)
          setState('error')
        }
        recognitionRef.current = null
      }

      recognitionRef.current = recognition
      recognition.start()
    } catch {
      setState('error')
      setErrorMsg(copy.micTranscribeFailed)
    }
  }

  function stopRecording() {
    recognitionRef.current?.stop()
    setState('transcribing')
  }

  return (
    <div className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={state === 'recording' ? stopRecording : startRecording}
        disabled={!supported || state === 'transcribing'}
        title={state === 'recording' ? copy.micStop : supported ? copy.micStart : copy.micUnavailableTooltip}
        className={`inline-flex items-center justify-center w-9 h-9 rounded-md border transition-colors shrink-0 ${
          state === 'recording'
            ? 'border-rust bg-rust/10 text-rust animate-pulse'
            : 'border-hairline text-green hover:bg-green-pale'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        {state === 'transcribing' ? (
          <Loader2 size={16} className="animate-spin" />
        ) : state === 'recording' ? (
          <Square size={14} />
        ) : (
          <Mic size={16} />
        )}
      </button>
      {state === 'error' && errorMsg && (
        <span className="inline-flex items-center gap-1 text-xs text-rust max-w-[220px]">
          <AlertCircle size={12} className="shrink-0" />
          {errorMsg}
        </span>
      )}
    </div>
  )
}
