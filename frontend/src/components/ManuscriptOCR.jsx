import { useState, useRef } from "react"
import { Upload, ImageIcon, Leaf, AlertTriangle, CheckCircle2, BookOpen } from "lucide-react"
import useTranslatedStrings from '../hooks/useTranslatedStrings'

const API_ORIGIN = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "")

async function ocrDigitise(image_base64, mime_type, filename) {
  const res = await fetch(`${API_ORIGIN}/api/v1/ocr`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_base64, mime_type, filename }),
  })
  if (!res.ok) throw new Error(`OCR failed: ${res.status}`)
  return res.json()
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result
      const b64 = result.split(",")[1]
      resolve(b64)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function ConfidenceBar({ value }) {
  const pct = Math.round((value || 0) * 100)
  const color = pct >= 70 ? "bg-green" : pct >= 40 ? "bg-gold" : "bg-rust"
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-green-pale rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-ink/60 w-8 text-right">{pct}%</span>
    </div>
  )
}

export default function ManuscriptOCR({ copy, language = 'en' }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  function handleFile(f) {
    if (!f) return
    setFile(f)
    setResult(null)
    setError(null)
    const url = URL.createObjectURL(f)
    setPreview(url)
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files?.[0]
    if (f) handleFile(f)
  }

  async function handleDigitise() {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const b64 = await fileToBase64(file)
      const data = await ocrDigitise(b64, file.type || "image/jpeg", file.name)
      setResult(data)
    } catch (e) {
      setError("Digitisation failed. Please try a different image.")
    } finally {
      setLoading(false)
    }
  }

  const extracted = result?.extracted
  const translationSource = {
    heading: 'Manuscript OCR & Digitisation',
    intro: 'Upload a photo of an old manuscript. A vision-language model will extract herbs, symptoms, and formulation steps into structured JSON.',
    dropHere: 'Drop manuscript image here',
    browse: 'or click to browse — JPEG, PNG, PDF supported',
    clickChange: 'click to change',
    digitising: 'Digitising…',
    digitise: 'Digitise Manuscript',
    error: 'Digitisation failed. Please try a different image.',
    results: 'Extraction Results',
    confidence: 'Confidence',
    script: 'Script',
    language: 'Language',
    rawTranscription: 'Transcription',
    herbs: 'Herbs Identified',
    symptoms: 'Symptoms / Conditions',
    steps: 'Formulation Steps',
    translationUnavailable: 'Some extracted text could not be translated and is shown in its original language.',
    ...(extracted ? {
      extractedNotes: extracted.notes || '',
      rawTranscriptionText: extracted.raw_transcription || '',
      ...Object.fromEntries((extracted.herbs || []).flatMap((herb, index) => [
        [`herbName${index}`, herb.name],
        [`herbPart${index}`, herb.part_mentioned || ''],
      ])),
      ...Object.fromEntries((extracted.symptoms_conditions || []).map((item, index) => [`symptom${index}`, item])),
      ...Object.fromEntries((extracted.formulation_steps || []).map((item, index) => [`step${index}`, item])),
      extractedDisclaimer: result.disclaimer || '',
    } : {}),
  }
  const { text: t, available: translationAvailable, pending: translationPending } =
    useTranslatedStrings(language, translationSource)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-earth">
        <div className="flex items-start gap-3">
          <span className="inline-flex items-center justify-center w-10 h-10 rounded-md bg-[#6b4a1e]/10 text-[#6b4a1e] shrink-0">
            <BookOpen size={20} />
          </span>
          <div>
            <h2 className="font-serif text-xl text-green-dark">{t('heading')}</h2>
            <p className="text-sm text-ink/60 mt-1 max-w-[65ch]">
              {t('intro')}
            </p>
          </div>
        </div>
      </div>

      {/* Drop Zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`dossier-panel p-8 sm:p-12 text-center cursor-pointer transition-all ${
          dragging ? "border-green bg-green-pale/30" : "hover:border-green/40 hover:bg-green-pale/10"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*,.pdf"
          className="hidden"
          onChange={e => handleFile(e.target.files?.[0])}
        />
        {preview ? (
          <div className="flex flex-col items-center gap-3">
            <img src={preview} alt="Manuscript preview" className="max-h-48 rounded-md border border-hairline shadow-md object-contain" />
            <p className="text-sm text-ink/60">{file?.name} · {t('clickChange')}</p>
          </div>
        ) : (
          <>
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-green-pale text-green mb-4">
              <Upload size={24} />
            </div>
            <p className="font-semibold text-ink/70">{t('dropHere')}</p>
            <p className="text-sm text-ink/40 mt-1">{t('browse')}</p>
          </>
        )}
      </div>

      {file && (
        <div className="flex justify-end">
          <button onClick={handleDigitise} disabled={loading}
            className="press inline-flex items-center gap-2 px-5 py-2.5 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark disabled:opacity-50 shadow-[0_5px_14px_rgba(31,59,44,0.18)]">
            {loading ? (
              <><svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> {t('digitising')}</>
            ) : (
              <><ImageIcon size={15} /> {t('digitise')}</>
            )}
          </button>
        </div>
      )}

      {error && (
        <div className="dossier-panel p-4 border-rust/40 bg-rust/5 flex items-start gap-2.5">
          <AlertTriangle size={16} className="text-rust shrink-0 mt-0.5" />
          <p className="text-sm text-rust">{error === 'Digitisation failed. Please try a different image.' ? t('error') : error}</p>
        </div>
      )}

      {!translationAvailable && !translationPending && language !== 'en' && <p role="status" className="text-xs text-earth">{t('translationUnavailable')}</p>}

      {extracted && (
        <div className="space-y-4 stagger">
          {/* Metadata */}
          <div className="dossier-panel p-5 border-l-4 border-l-gold">
            <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
              <h3 className="font-serif text-base text-green-dark">{t('results')}</h3>
              <div className="flex items-center gap-2">
                <span className="text-xs text-ink/50">{t('confidence')}</span>
                <div className="w-32"><ConfidenceBar value={extracted.confidence} /></div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-ink/45 mb-0.5">{t('script')}</p>
                <p className="font-medium">{extracted.script_detected || "�"}</p>
              </div>
              <div>
                <p className="text-xs text-ink/45 mb-0.5">{t('language')}</p>
                <p className="font-medium">{extracted.language_detected || "�"}</p>
              </div>
            </div>
            {extracted.notes && (
              <p className="text-xs text-ink/50 italic mt-3 border-t border-hairline pt-3">{t('extractedNotes')}</p>
            )}
          </div>

          {extracted.raw_transcription && (
            <div className="dossier-panel p-5">
              <p className="section-kicker mb-2">{t('rawTranscription')}</p>
              <p className="text-sm font-mono text-ink/75 leading-relaxed whitespace-pre-wrap bg-paper-dim/50 rounded-md p-3 border border-hairline">
                {t('rawTranscriptionText')}
              </p>
            </div>
          )}

          {extracted.herbs?.length > 0 && (
            <div className="dossier-panel p-5">
              <p className="section-kicker mb-3 flex items-center gap-2"><Leaf size={13} className="text-green" /> {t('herbs')}</p>
              <div className="grid gap-2">
                {extracted.herbs.map((h, i) => (
                  <div key={i} className="flex items-center gap-3 p-2.5 border border-hairline rounded-md bg-paper/50">
                    <div className="flex-1">
                      <p className="text-sm font-semibold">{t(`herbName${i}`)}</p>
                      {h.local_name && <p className="text-xs text-ink/50">{h.local_name}</p>}
                    </div>
                    {h.part_mentioned && <span className="text-xs border border-green/20 bg-green-pale text-green px-2 py-0.5 rounded-full">{t(`herbPart${i}`)}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {extracted.symptoms_conditions?.length > 0 && (
            <div className="dossier-panel p-5">
              <p className="section-kicker mb-2">{t('symptoms')}</p>
              <div className="flex gap-2 flex-wrap">
                {extracted.symptoms_conditions.map((s, i) => (
                  <span key={i} className="area-chip">{t(`symptom${i}`)}</span>
                ))}
              </div>
            </div>
          )}

          {extracted.formulation_steps?.length > 0 && (
            <div className="dossier-panel p-5">
              <p className="section-kicker mb-3">{t('steps')}</p>
              <ol className="space-y-2">
                {extracted.formulation_steps.map((step, i) => (
                  <li key={i} className="flex gap-3 text-sm text-ink/80">
                    <span className="citation-marker shrink-0 w-6 h-6 rounded-full bg-green-pale text-green text-[11px] flex items-center justify-center border border-green/15">{i + 1}</span>
                    <span className="pt-0.5">{t(`step${i}`)}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          <div className="dossier-panel p-4 border-rust/20 bg-rust/5">
            <p className="text-xs text-ink/50 italic">{t('extractedDisclaimer')}</p>
          </div>
        </div>
      )}
    </div>
  )
}
