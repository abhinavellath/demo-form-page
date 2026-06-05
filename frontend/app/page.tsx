'use client'

import { useEffect, useRef, useState } from 'react'

type DemoMode = 'call' | 'chat'

type ChatLine = { role: 'user' | 'assistant'; text: string }

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, '') ||
  'https://demo-form-page.onrender.com'

export default function Home() {
  const [mode, setMode] = useState<DemoMode>('chat')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const [form, setForm] = useState({
    name: '',
    phone: '',
    role: '',
    experience: ''
  })

  const [chatId, setChatId] = useState<string | null>(null)
  const [sessionSecret, setSessionSecret] = useState<string | null>(null)
  const [lines, setLines] = useState<ChatLine[]>([])
  const [input, setInput] = useState('')
  const [chatBusy, setChatBusy] = useState(false)
  const [ended, setEnded] = useState(false)
  const [endResult, setEndResult] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, chatBusy])

  const resetChat = () => {
    setChatId(null)
    setSessionSecret(null)
    setLines([])
    setInput('')
    setEnded(false)
    setEndResult(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage('')
    resetChat()

    try {
      if (mode === 'call') {
        const response = await fetch(`${API_BASE}/lead`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form)
        })
        const data = await response.json()
        setMessage(data.message ?? (response.ok ? 'OK' : 'Request failed'))
      } else {
        const response = await fetch(`${API_BASE}/lead-chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form)
        })
        const data = await response.json()
        if (!response.ok) {
          setMessage(
            typeof data.detail === 'string'
              ? data.detail
              : 'Could not start chat session'
          )
          setLoading(false)
          return
        }
        setChatId(data.chat_id)
        setSessionSecret(data.session_secret)
        setLines([{ role: 'assistant', text: data.opening_message }])
        setMessage('Chat session started — type below to talk to the recruiter.')
        setForm({ name: '', phone: '', role: '', experience: '' })
      }

      if (mode === 'call') {
        setForm({ name: '', phone: '', role: '', experience: '' })
      }
    } catch {
      setMessage('Something went wrong (network or server).')
    }

    setLoading(false)
  }

  const sendChat = async () => {
    const text = input.trim()
    if (!text || !chatId || !sessionSecret || ended || chatBusy) return

    setChatBusy(true)
    setInput('')
    setLines((prev) => [...prev, { role: 'user', text }])

    try {
      const response = await fetch(`${API_BASE}/chat/${chatId}/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-chat-session': sessionSecret
        },
        body: JSON.stringify({ text })
      })
      const data = await response.json()
      if (!response.ok) {
        const err =
          typeof data.detail === 'string' ? data.detail : 'Message failed'
        setLines((prev) => [
          ...prev,
          { role: 'assistant', text: `Error: ${err}` }
        ])
        return
      }
      setLines((prev) => [...prev, { role: 'assistant', text: data.reply }])
    } catch {
      setLines((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: 'Error: could not reach the server.'
        }
      ])
    } finally {
      setChatBusy(false)
    }
  }

  const endChat = async () => {
    if (!chatId || !sessionSecret || ended) return
    setChatBusy(true)
    setEndResult('Running post-conversation agents…')

    try {
      const response = await fetch(`${API_BASE}/chat/${chatId}/end`, {
        method: 'POST',
        headers: { 'x-chat-session': sessionSecret }
      })
      const data = await response.json()
      if (!response.ok) {
        setEndResult(
          typeof data.detail === 'string' ? data.detail : 'End session failed'
        )
        return
      }
      setEnded(true)
      setEndResult(JSON.stringify(data.result, null, 2))
    } catch {
      setEndResult('Could not reach the server.')
    } finally {
      setChatBusy(false)
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-100 p-6">
      <div className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-lg space-y-6">
        <h1 className="text-3xl font-bold text-center">AI Recruiter Demo</h1>

        <div className="flex rounded-lg border border-gray-200 p-1 bg-gray-50">
          <button
            type="button"
            className={`flex-1 py-2 rounded-md text-sm font-medium transition ${
              mode === 'chat'
                ? 'bg-white shadow text-black'
                : 'text-gray-600'
            }`}
            onClick={() => {
              setMode('chat')
              setMessage('')
            }}
          >
            Chat demo
          </button>
          <button
            type="button"
            className={`flex-1 py-2 rounded-md text-sm font-medium transition ${
              mode === 'call'
                ? 'bg-white shadow text-black'
                : 'text-gray-600'
            }`}
            onClick={() => {
              setMode('call')
              resetChat()
              setMessage('')
            }}
          >
            Phone call (Vapi)
          </button>
        </div>

        {!chatId && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="text"
              placeholder="Candidate Name"
              className="w-full border p-3 rounded-lg"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />

            <input
              type="text"
              placeholder="Phone Number"
              className="w-full border p-3 rounded-lg"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              required
            />

            <select
              className="w-full border p-3 rounded-lg bg-white"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              required
            >
              <option value="" disabled>
                Role applied (required for screening bank)
              </option>
              <option value="DevOps Engineer">DevOps Engineer</option>
              <option value="AI Engineer">AI Engineer</option>
            </select>

            <input
              type="text"
              placeholder="Years of Experience"
              className="w-full border p-3 rounded-lg"
              value={form.experience}
              onChange={(e) =>
                setForm({ ...form, experience: e.target.value })
              }
              required
            />

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-black text-white p-3 rounded-lg disabled:opacity-60"
            >
              {loading
                ? mode === 'call'
                  ? 'Starting call…'
                  : 'Starting chat…'
                : mode === 'call'
                  ? 'Apply now (call)'
                  : 'Start chat session'}
            </button>
          </form>
        )}

        {mode === 'chat' && chatId && (
          <div className="space-y-3 border-t pt-4">
            <div className="h-64 overflow-y-auto border rounded-lg p-3 bg-gray-50 text-sm space-y-3">
              {lines.map((line, i) => (
                <div
                  key={i}
                  className={
                    line.role === 'user' ? 'text-right' : 'text-left'
                  }
                >
                  <span
                    className={`inline-block max-w-[90%] rounded-lg px-3 py-2 ${
                      line.role === 'user'
                        ? 'bg-black text-white'
                        : 'bg-white border border-gray-200'
                    }`}
                  >
                    {line.text}
                  </span>
                </div>
              ))}
              {chatBusy && (
                <p className="text-gray-500 text-xs">Thinking…</p>
              )}
              <div ref={bottomRef} />
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                className="flex-1 border rounded-lg px-3 py-2 text-sm"
                placeholder="Your message…"
                value={input}
                disabled={ended}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void sendChat()
                  }
                }}
              />
              <button
                type="button"
                disabled={ended || chatBusy || !input.trim()}
                onClick={() => void sendChat()}
                className="px-4 py-2 rounded-lg bg-black text-white text-sm disabled:opacity-50"
              >
                Send
              </button>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void endChat()}
                disabled={ended || chatBusy}
                className="flex-1 py-2 rounded-lg border border-red-200 bg-red-50 text-red-800 text-sm font-medium disabled:opacity-50"
              >
                End conversation
              </button>
              <button
                type="button"
                onClick={() => {
                  resetChat()
                  setMessage('')
                }}
                className="px-3 py-2 rounded-lg border text-sm text-gray-600"
              >
                New session
              </button>
            </div>

            {endResult && (
              <div>
                <p className="text-xs font-semibold text-gray-600 mb-1">
                  Post-call pipeline result
                </p>
                <pre className="text-xs bg-gray-900 text-green-100 p-3 rounded-lg overflow-x-auto max-h-48">
                  {endResult}
                </pre>
              </div>
            )}
          </div>
        )}

        {message && (
          <p className="text-center text-sm text-gray-700">{message}</p>
        )}
      </div>
    </main>
  )
}
