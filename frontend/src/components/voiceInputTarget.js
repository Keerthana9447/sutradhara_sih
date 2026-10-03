let focusedVoiceInput = null

export function rememberVoiceInput(element, onTranscribed) {
  focusedVoiceInput = { element, onTranscribed }
}

export function deliverVoiceTranscript(text, fallback) {
  if (focusedVoiceInput?.element.isConnected) {
    focusedVoiceInput.onTranscribed(text)
    return
  }

  fallback(text)
}
