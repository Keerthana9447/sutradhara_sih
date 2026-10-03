import { useEffect, useState } from 'react'
import { Scale, Copyright, FileText, ChevronDown, ChevronUp } from 'lucide-react'
import useTranslatedStrings from '../hooks/useTranslatedStrings'

const API_ORIGIN = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

async function fetchLegal(page) {
  const res = await fetch(`${API_ORIGIN}/api/v1/legal/${page}`)
  if (!res.ok) throw new Error(`Could not load ${page} information (${res.status}).`)
  return res.json()
}

const LABELS = {
  heading: 'Legal & Compliance',
  lede: 'RTI Act compliance · Terms of Service · Copyright & IP notice',
  rtiTab: 'RTI Act',
  termsTab: 'Terms of Service',
  copyrightTab: 'Copyright',
  loading: 'Loading legal information…',
  updated: 'Last updated:',
  publicAuthority: 'Public Authority',
  pioContact: 'PIO Contact',
  disclosure: 'Disclosure',
  proactive: 'Proactive Disclosures',
  version: 'Version',
  effective: 'Effective',
  corpusSources: 'Corpus Sources',
  softwareLicense: 'Software License',
  tkdlAttribution: 'TKDL Attribution',
  aiOutputs: 'AI-Generated Outputs',
  contact: 'Contact',
  translationUnavailable: 'Some legal text could not be translated and is shown in English.',
}

function Accordion({ heading, children }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-b border-hairline last:border-0">
      <button onClick={() => setOpen((value) => !value)}
        className="press w-full flex items-center justify-between py-4 text-left hover:text-green">
        <span className="text-sm font-semibold text-ink/80">{heading}</span>
        {open ? <ChevronUp size={14} className="text-ink/40 shrink-0" /> : <ChevronDown size={14} className="text-ink/40 shrink-0" />}
      </button>
      {open && <p className="text-sm text-ink/65 pb-4 leading-relaxed max-w-[72ch]">{children}</p>}
    </div>
  )
}

export default function LegalPages({ language = 'en' }) {
  const [tab, setTab] = useState('rti')
  const [data, setData] = useState({})
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    Promise.all(['rti', 'terms', 'copyright'].map((page) =>
      fetchLegal(page).then((value) => [page, value])
    ))
      .then((pages) => {
        if (!cancelled) setData(Object.fromEntries(pages))
      })
      .catch((failure) => {
        if (!cancelled) setError(failure.message || 'Could not load legal information.')
      })
    return () => { cancelled = true }
  }, [])

  const translationSource = { ...LABELS }
  Object.entries(data).forEach(([page, value]) => {
    if (page === 'rti') {
      for (const field of ['title', 'public_authority', 'disclosure', 'disclaimer']) {
        if (value[field]) translationSource[`${page}_${field}`] = value[field]
      }
      ;(value.proactive_disclosures || []).forEach((item, index) => {
        translationSource[`${page}_disclosure_${index}`] = item
      })
    } else if (page === 'terms') {
      if (value.title) translationSource.terms_title = value.title
      ;(value.sections || []).forEach((section, index) => {
        translationSource[`terms_heading_${index}`] = section.heading
        translationSource[`terms_text_${index}`] = section.text
      })
    } else if (page === 'copyright') {
      for (const field of ['title', 'copyright', 'corpus_sources', 'software_license', 'tkdl_attribution', 'ai_outputs']) {
        if (value[field]) translationSource[`copyright_${field}`] = value[field]
      }
    }
  })
  const { text: t, available, pending } = useTranslatedStrings(language, translationSource)

  const rti = data.rti
  const terms = data.terms
  const copyright = data.copyright

  return (
    <div className="space-y-6">
      <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-ink/30">
        <div className="flex items-start gap-3">
          <span className="inline-flex items-center justify-center w-10 h-10 rounded-md bg-ink/5 text-ink/60 shrink-0">
            <Scale size={20} />
          </span>
          <div>
            <h2 className="font-serif text-xl text-green-dark">{t('heading')}</h2>
            <p className="text-sm text-ink/60 mt-1">{t('lede')}</p>
          </div>
        </div>
      </div>

      <div className="flex gap-1 border-b border-hairline overflow-x-auto">
        {[
          ['rti', 'rtiTab', Scale],
          ['terms', 'termsTab', FileText],
          ['copyright', 'copyrightTab', Copyright],
        ].map(([id, label, Icon]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`press inline-flex items-center gap-1.5 px-4 py-2.5 text-sm border-b-2 whitespace-nowrap ${
              tab === id ? 'border-gold text-gold-dark' : 'border-transparent text-ink/50 hover:text-ink'
            }`}>
            <Icon size={14} /> {t(label)}
          </button>
        ))}
      </div>

      {!available && !pending && language !== 'en' && (
        <p role="status" className="text-xs text-earth">{t('translationUnavailable')}</p>
      )}
      {error && <p role="alert" className="text-sm text-rust">{error}</p>}
      {!error && !data.rti && <p className="text-sm text-ink/40 py-6 text-center">{t('loading')}</p>}

      <div key={tab} className="view-enter">
        {tab === 'rti' && rti && (
          <div className="space-y-4">
            <div className="dossier-panel p-5 border-l-4 border-l-green">
              <h3 className="font-serif text-lg text-green-dark">{t('rti_title')}</h3>
              <p className="text-xs text-ink/40 mt-1">{t('updated')} {rti.last_updated}</p>
            </div>
            <div className="dossier-panel p-5 space-y-3">
              <div><p className="section-kicker mb-1">{t('publicAuthority')}</p><p className="text-sm text-ink/75">{t('rti_public_authority')}</p></div>
              <div><p className="section-kicker mb-1">{t('pioContact')}</p><a href={`mailto:${rti.pio_contact}`} className="text-sm text-green hover:underline">{rti.pio_contact}</a></div>
              <div><p className="section-kicker mb-1">{t('disclosure')}</p><p className="text-sm text-ink/75">{t('rti_disclosure')}</p></div>
              <div>
                <p className="section-kicker mb-2">{t('proactive')}</p>
                <ul className="space-y-1.5">
                  {(rti.proactive_disclosures || []).map((_, index) => (
                    <li key={index} className="text-sm text-ink/70 flex gap-2"><span className="text-green shrink-0">•</span>{t(`rti_disclosure_${index}`)}</li>
                  ))}
                </ul>
              </div>
              <p className="text-xs text-ink/45 italic border-t border-hairline pt-3">{t('rti_disclaimer')}</p>
            </div>
          </div>
        )}
        {tab === 'terms' && terms && (
          <div className="space-y-4">
            <div className="dossier-panel p-5 border-l-4 border-l-gold">
              <h3 className="font-serif text-lg text-green-dark">{t('terms_title')}</h3>
              <p className="text-xs text-ink/40 mt-1">{t('version')} {terms.version} · {t('effective')} {terms.effective_date}</p>
            </div>
            <div className="dossier-panel px-5 py-2">
              {(terms.sections || []).map((_, index) => (
                <Accordion key={index} heading={t(`terms_heading_${index}`)}>{t(`terms_text_${index}`)}</Accordion>
              ))}
            </div>
          </div>
        )}
        {tab === 'copyright' && copyright && (
          <div className="space-y-4">
            <div className="dossier-panel p-5 border-l-4 border-l-earth">
              <h3 className="font-serif text-lg text-green-dark">{t('copyright_title')}</h3>
              <p className="text-sm font-semibold mt-1">{t('copyright_copyright')}</p>
            </div>
            <div className="dossier-panel p-5 space-y-4">
              {[
                ['corpusSources', 'corpus_sources'],
                ['softwareLicense', 'software_license'],
                ['tkdlAttribution', 'tkdl_attribution'],
                ['aiOutputs', 'ai_outputs'],
              ].map(([label, field]) => (
                <div key={field}><p className="section-kicker mb-1">{t(label)}</p><p className="text-sm text-ink/70">{t(`copyright_${field}`)}</p></div>
              ))}
              <div><p className="section-kicker mb-1">{t('contact')}</p><a href={`mailto:${copyright.contact}`} className="text-sm text-green hover:underline">{copyright.contact}</a></div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
