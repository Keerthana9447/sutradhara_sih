import { ArrowRight, Check, FileText, Landmark, Search, ShieldCheck } from 'lucide-react'
import Logo from './Logo'
import EvidenceThread from './EvidenceThread'
import { LeafSprig, BotanicalCorner } from './Botanical'

const TRACE = [
  { Icon: Search, key: 'product' },
  { Icon: Landmark, key: 'classification' },
  { Icon: FileText, key: 'evidence' },
]

/**
 * The hero is one object, not two: the abstract pipeline (the evidence
 * thread) sits directly above a worked example of that same pipeline running
 * on a real query. Stating the method and then immediately showing it applied
 * is more convincing in a demo than either half on its own.
 */
export default function Hero({ copy, onStart }) {
  return (
    <div className="animate-in">
      <div className="relative text-center max-w-3xl mx-auto pt-10 sm:pt-14 pb-10 px-4">
        <Logo size={360} className="pointer-events-none absolute -top-16 left-1/2 -translate-x-1/2 text-green opacity-[0.045]" />
        <LeafSprig size={112} className="pointer-events-none absolute -left-12 top-16 text-green opacity-[0.09] hidden lg:block" />
        <LeafSprig size={112} flip className="pointer-events-none absolute -right-12 top-24 text-green opacity-[0.09] hidden lg:block" />

        <p className="section-kicker mb-5">{copy.tagline}</p>
        <h1 className="relative font-serif text-5xl sm:text-6xl text-green-dark tracking-tight leading-[0.98] hero-title">{copy.appName}</h1>
        <p className="relative mt-6 text-base sm:text-lg text-ink/65 leading-relaxed max-w-2xl mx-auto hero-lede">{copy.heroLede}</p>
        <div className="relative mt-8 flex flex-col items-center gap-3">
          <button
            onClick={onStart}
            className="press inline-flex items-center gap-2 bg-green text-paper px-6 py-3 rounded-md text-sm font-semibold hover:bg-green-dark hover:-translate-y-0.5 shadow-[0_8px_18px_rgba(31,59,44,0.18)]"
          >
            {copy.heroCta}
            <ArrowRight size={16} />
          </button>
          <p className="text-xs text-ink/40">{copy.builtFor}</p>
        </div>
      </div>

      <div className="hero-stage mb-10">
        <BotanicalCorner size={230} className="pointer-events-none absolute -left-6 -bottom-8 text-gold-light opacity-[0.11]" />

        <EvidenceThread copy={copy} />

        <div className="hero-trace">
          <div className="hero-trace__intro">
            <p className="section-kicker mb-2 text-gold-light">{copy.liveEvidenceTrail}</p>
            <h2 className="font-serif text-2xl sm:text-3xl text-paper leading-tight">{copy.heroTraceTitle}</h2>
            <p className="text-sm text-paper/65 mt-3 max-w-sm leading-relaxed">{copy.heroTraceBody}</p>
            <div className="mt-6 flex items-center gap-2 text-xs text-paper/55">
              <ShieldCheck size={15} className="text-gold-light" /> {copy.citationGrounded}
            </div>
          </div>
          <div className="hero-trace__steps">
            {TRACE.map(({ Icon, key }, index) => (
              <div key={key} className="trace-step" style={{ animationDelay: `${index * 100}ms` }}>
                <span className="trace-step__icon"><Icon size={16} /></span>
                <div>
                  <p className="citation-marker text-[10px] uppercase tracking-[0.12em] text-gold-light/80">{copy.heroTrace[index].label}</p>
                  <p className="text-sm text-paper/90 mt-1 leading-snug">{copy.heroTrace[index].value}</p>
                </div>
                {index < TRACE.length - 1 && <span className="trace-step__line" aria-hidden="true" />}
              </div>
            ))}
            <div className="trace-result"><Check size={16} /><span>{copy.sourceRetained}</span><strong>{copy.confidenceHigh}</strong></div>
          </div>
        </div>
      </div>
    </div>
  )
}
