'use client'

import { useState } from 'react'

export default function Home() {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const [form, setForm] = useState({
    name: '',
    phone: '',
    role: '',
    experience: ''
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    setLoading(true)
    setMessage('')

    try {
      const response = await fetch(
        'https://YOUR-BACKEND-URL.onrender.com/lead',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(form)
        }
      )

      const data = await response.json()

      setMessage(data.message)

      setForm({
        name: '',
        phone: '',
        role: '',
        experience: ''
      })

    } catch (error) {
      setMessage('Something went wrong')
    }

    setLoading(false)
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-100 p-6">

      <div className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-md">

        <h1 className="text-3xl font-bold mb-6 text-center">
          AI Recruiter Demo
        </h1>

        <form onSubmit={handleSubmit} className="space-y-4">

          <input
            type="text"
            placeholder="Candidate Name"
            className="w-full border p-3 rounded-lg"
            value={form.name}
            onChange={(e) =>
              setForm({ ...form, name: e.target.value })
            }
            required
          />

          <input
            type="text"
            placeholder="Phone Number"
            className="w-full border p-3 rounded-lg"
            value={form.phone}
            onChange={(e) =>
              setForm({ ...form, phone: e.target.value })
            }
            required
          />

          <input
            type="text"
            placeholder="Role Applied"
            className="w-full border p-3 rounded-lg"
            value={form.role}
            onChange={(e) =>
              setForm({ ...form, role: e.target.value })
            }
            required
          />

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
            className="w-full bg-black text-white p-3 rounded-lg"
          >
            {loading ? 'Starting Call...' : 'Apply Now'}
          </button>

        </form>

        {message && (
          <p className="mt-4 text-center">
            {message}
          </p>
        )}

      </div>

    </main>
  )
}