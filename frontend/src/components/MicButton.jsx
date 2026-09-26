import { useEffect, useRef, useState } from 'react'
import { Mic, Square, Loader2, AlertCircle } from 'lucide-react'
import { api } from '../api'

const LOCALES = {
  en: 'en-IN',
  hi: 'hi-IN',
  te: 'te-IN',
  ta: 'ta-IN',
  ml: 'ml-IN',
  sa: 'hi-IN', // browser support for Sanskrit varies; Hindi is the closest fallback
}

// Backend voice recognition (Sarvam Saaras / Bhashini, app/asr.py) covers
// these languages — see SUPPORTED_ASR_LANGUAGES server-side. Sanskrit isn't
// supported there, so it keeps using the browser's own recognizer mapped
// to the closest available locale (hi-IN), same as English does natively.
const BACKEND_ASR_LANGUAGES = new Set(['en', 'hi', 'te', 'ta', 'ml', 'sa'])

function getRecognition() {
  if (typeof window === 'undefined') return null
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) return null
  return SpeechRecognition
}

function pickRecorderMimeType() {
  if (typeof MediaRecorder === 'undefined') return null
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || null
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => resolve((reader.result || '').toString().split(',')[1] || '')
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

/**
 * Voice input.
 *
 * English (and Sanskrit, which the backend doesn't support — see
 * BACKEND_ASR_LANGUAGES above) keeps using the browser's own live
 * SpeechRecognition, same as before — fast, free, and reliably supported
 * for English in particular.
 *
 * Hindi/Telugu/Tamil/Malayalam now record the microphone with
 * MediaRecorder and send the audio to the backend's Sarvam/Bhashini ASR
 * (app/asr.py's transcribe()) instead of the browser recognizer: browser
 * SpeechRecognition support for Indian-language locales is inconsistent
 * across browsers/OSes (often silently substitutes en-US, or just returns
 * nothing), whereas Sarvam Saaras and the Bhashini fallback are
 * purpose-built for these languages — same reasoning as ReadAloudButton's
 * switch to backend TTS for the same set of languages. If the backend call
 * errors or isn't configured, the failure is surfaced the same way a
 * failed browser recognition already was (copy.micTranscribeFailed),
 * rather than pretending to succeed.
 */
export default function MicButton({ sourceLanguage, onTranscribed, copy }) {
  const [state, setState] = useState('idle') // idle | recording | transcribing | error
  const [errorMsg, setErrorMsg] = useState('')
  const recognitionRef = useRef(null)
  const finalTextRef = useRef('')
  const mediaRecorderRef = useRef(null)
  const mediaChunksRef = useRef([])
  const mediaStreamRef = useRef(null)

  const useBackendAsr = BACKEND_ASR_LANGUAGES.has(sourceLanguage)
  const Recognition = getRecognition()
  const recorderSupported =
    typeof navigator !== 'undefined' && !!navigator.mediaDevices && pickRecorderMimeType() !== null
  const supported = useBackendAsr ? recorderSupported : !!Recognition

  useEffect(
    () => () => {
      recognitionRef.current?.abort()
      mediaRecorderRef.current?.stop()
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
    },
    []
  )

  // ---- Browser SpeechRecognition path (English / Sanskrit) ----
  function startBrowserRecording() {
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
          'service-not-allowed': copy.micNotSupported,
          'audio-capture': copy.micNotSupported,
          network: copy.micTranscribeFailed,
        }
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

  function stopBrowserRecording() {
    recognitionRef.current?.stop()
    setState('transcribing')
  }

  // ---- Backend Sarvam/Bhashini ASR path (Hindi/Telugu/Tamil/Malayalam) ----
  async function startBackendRecording() {
    if (!recorderSupported) {
      setState('error')
      setErrorMsg(copy.micNotSupported)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaStreamRef.current = stream
      const mimeType = pickRecorderMimeType() || ''
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      mediaChunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) mediaChunksRef.current.push(e.data)
      }
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        mediaStreamRef.current = null
        setState('transcribing')
        try {
          const blob = new Blob(mediaChunksRef.current, { type: mimeType || 'audio/webm' })
          const audioBase64 = await blobToBase64(blob)
          const format = mimeType.includes('mp4') ? 'mp4' : mimeType.includes('ogg') ? 'ogg' : 'webm'
          const res = await api.transcribeAudio({
            audio_base64: audioBase64,
            source_language: sourceLanguage,
            audio_format: format,
            sampling_rate: 16000,
          })
          if (res.transcribed_ok && res.text) {
            onTranscribed(res.text)
            setState('idle')
          } else {
            setErrorMsg(copy.micTranscribeFailed)
            setState('error')
          }
        } catch {
          setErrorMsg(copy.micTranscribeFailed)
          setState('error')
        }
      }

      mediaRecorderRef.current = recorder
      recorder.start()
      setState('recording')
    } catch (err) {
      setState('error')
      setErrorMsg(err?.name === 'NotAllowedError' ? copy.micPermissionDenied : copy.micNotSupported)
    }
  }

  function stopBackendRecording() {
    mediaRecorderRef.current?.stop()
  }

  function startRecording() {
    setErrorMsg('')
    if (useBackendAsr) startBackendRecording()
    else startBrowserRecording()
  }

  function stopRecording() {
    if (useBackendAsr) stopBackendRecording()
    else stopBrowserRecording()
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
