import { useEffect, useState } from 'react'
import { api } from '../api'

function splitText(text, limit = 5500) {
  const pieces = []
  let remaining = text
  while (remaining.length > limit) {
    let boundary = Math.max(remaining.lastIndexOf('\n', limit), remaining.lastIndexOf(' ', limit))
    if (boundary < limit / 2) boundary = limit
    else boundary += 1
    pieces.push(remaining.slice(0, boundary))
    remaining = remaining.slice(boundary)
  }
  if (remaining) pieces.push(remaining)
  return pieces
}

export default function useTranslatedStrings(language, source) {
  const serialized = JSON.stringify(source)
  const [translated, setTranslated] = useState({})
  const [available, setAvailable] = useState(true)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    const sourceEntries = Object.entries(JSON.parse(serialized))
    const entries = sourceEntries.filter(([, value]) => typeof value === 'string' && value.length > 0)
    if (language === 'en' || entries.length === 0) {
      setTranslated(Object.fromEntries(Object.entries(JSON.parse(serialized))))
      setAvailable(true)
      setPending(false)
      return undefined
    }

    let cancelled = false
    const original = Object.fromEntries(Object.entries(JSON.parse(serialized)))
    setTranslated(original)
    setAvailable(false)
    setPending(true)
    const pieces = entries.flatMap(([key, value]) =>
      splitText(value).map((piece, index) => ({ key, piece, index }))
    )
    const batches = []
    for (let i = 0; i < pieces.length; i += 100) batches.push(pieces.slice(i, i + 100))
    Promise.all(batches.map((batch) => api.translateTexts(batch.map(({ piece }) => piece), language)))
      .then((responses) => {
        if (cancelled) return
        const translatedPieces = new Map()
        let allTranslated = true
        responses.forEach((response, batchIndex) => {
          const batch = batches[batchIndex]
          if (response.results.length !== batch.length) allTranslated = false
          batch.forEach(({ key, piece, index }, itemIndex) => {
            const item = response.results[itemIndex]
            if (!item) {
              allTranslated = false
              translatedPieces.set(`${key}:${index}`, { text: piece, success: false })
              return
            }
            translatedPieces.set(`${key}:${index}`, { text: item.translated, success: item.success })
            allTranslated = allTranslated && item.success
          })
        })
        const next = { ...original }
        entries.forEach(([key, value]) => {
          const chunks = splitText(value)
          const translations = chunks.map((_, index) => translatedPieces.get(`${key}:${index}`))
          if (translations.every((item) => item?.success)) {
            next[key] = translations.map((item) => item.text).join('')
          } else {
            allTranslated = false
          }
        })
        setTranslated(next)
        setAvailable(allTranslated)
        setPending(false)
      })
      .catch(() => {
        if (cancelled) return
        setTranslated(original)
        setAvailable(false)
        setPending(false)
      })

    return () => { cancelled = true }
  }, [language, serialized])

  return {
    text: (key) => translated[key] ?? source[key] ?? '',
    available,
    pending,
  }
}
