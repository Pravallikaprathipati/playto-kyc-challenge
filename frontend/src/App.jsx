import { useEffect, useState } from 'react'

const rawApiBase = import.meta.env.VITE_API_BASE
const API_BASE = rawApiBase ? rawApiBase.replace(/\/$/, '') : '/api/v1'
const ROLE_MERCHANT = 'merchant'
const ROLE_REVIEWER = 'reviewer'

function fetchJson(url, options = {}) {
  const token = localStorage.getItem('playto_token')
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }
  if (token) {
    headers.Authorization = `Token ${token}`
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 10000) // 10 second timeout

  return fetch(url, {
    headers,
    ...options,
    signal: controller.signal,
  }).then(async (res) => {
    clearTimeout(timeoutId)
    const text = await res.text()
    let data = {}
    if (text) {
      try {
        data = JSON.parse(text)
      } catch (parseError) {
        data = { status: res.status, statusText: res.statusText, body: text }
      }
    }
    if (!res.ok) throw data
    return data
  }).catch((error) => {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError') {
      throw { detail: 'Request timed out. Check your internet or backend status.' }
    }
    if (error instanceof TypeError) {
      throw { detail: `Network error: ${error.message}` }
    }
    throw error
  })
}

function App() {
  const [user, setUser] = useState({ role: null })
  const [error, setError] = useState(null)
  const [view, setView] = useState('login')
  const [submissions, setSubmissions] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [selectedSubmission, setSelectedSubmission] = useState(null)
  const [form, setForm] = useState({ username: '', password: '' })
  const [registerForm, setRegisterForm] = useState({ username: '', password: '', email: '', role: 'merchant' })
  const [kycForm, setKycForm] = useState({
    personal_name: '',
    personal_email: '',
    personal_phone: '',
    business_name: '',
    business_type: '',
    expected_monthly_volume_usd: '',
  })
  const [documents, setDocuments] = useState({ pan: null, aadhaar: null, bank_statement: null })
  const [reviewAction, setReviewAction] = useState({ action: '', reason: '' })

  useEffect(() => {
    const role = localStorage.getItem('playto_role')
    const username = localStorage.getItem('playto_username')
    if (role) setUser({ role, username })
  }, [])

  useEffect(() => {
    if (user.role === ROLE_MERCHANT) {
      loadMerchantSubmissions()
    } else if (user.role === ROLE_REVIEWER) {
      loadReviewerDashboard()
    }
  }, [user])

  async function loadMerchantSubmissions() {
    try {
      const data = await fetchJson(`${API_BASE}/submissions/`)
      setSubmissions(data)
    } catch (err) {
      setError(err.detail || 'Failed to load submissions.')
    }
  }

  async function loadReviewerDashboard() {
    try {
      const [data, queue] = await Promise.all([
        fetchJson(`${API_BASE}/reviewer/dashboard/`),
        fetchJson(`${API_BASE}/submissions/`),
      ])
      setMetrics(data)
      setSubmissions(queue)
    } catch (err) {
      setError(err.detail || 'Failed to load reviewer data.')
    }
  }

  async function login() {
    setError(null)
    try {
      const data = await fetchJson(`${API_BASE}/auth/token/`, {
        method: 'POST',
        body: JSON.stringify(form),
      })
      localStorage.setItem('playto_token', data.token)
      localStorage.setItem('playto_role', data.role)
      localStorage.setItem('playto_username', form.username)
      setUser({ role: data.role, username: form.username })
      setView('dashboard')
    } catch (err) {
      setError(err.non_field_errors?.[0] || err.detail || JSON.stringify(err) || 'Login failed.')
    }
  }

  async function register() {
    setError(null)
    try {
      await fetchJson(`${API_BASE}/auth/register/`, {
        method: 'POST',
        body: JSON.stringify(registerForm),
      })
      // After registration, automatically log in
      const data = await fetchJson(`${API_BASE}/auth/token/`, {
        method: 'POST',
        body: JSON.stringify({ username: registerForm.username, password: registerForm.password }),
      })
      localStorage.setItem('playto_token', data.token)
      localStorage.setItem('playto_role', data.role)
      localStorage.setItem('playto_username', registerForm.username)
      setUser({ role: data.role, username: registerForm.username })
      setView('dashboard')
    } catch (err) {
      setError(err.detail || err.non_field_errors?.[0] || JSON.stringify(err) || 'Registration failed.')
    }
  }

  function logout() {
    localStorage.removeItem('playto_token')
    localStorage.removeItem('playto_role')
    localStorage.removeItem('playto_username')
    setUser({ role: null })
    setSubmissions([])
    setMetrics(null)
    setView('login')
  }

  async function createSubmission() {
    try {
      const data = await fetchJson(`${API_BASE}/submissions/`, {
        method: 'POST',
        body: JSON.stringify(kycForm),
      })
      setSubmissions([...submissions, data])
      setKycForm({
        personal_name: '',
        personal_email: '',
        personal_phone: '',
        business_name: '',
        business_type: '',
        expected_monthly_volume_usd: '',
      })
      setView('dashboard')
    } catch (err) {
      setError(err.detail || 'Failed to create submission.')
    }
  }

  async function submitSubmission(id) {
    try {
      const data = await fetchJson(`${API_BASE}/submissions/${id}/submit/`, {
        method: 'POST',
      })
      setSubmissions(submissions.map(s => s.id === id ? data : s))
    } catch (err) {
      setError(err.detail || 'Failed to submit.')
    }
  }

  async function uploadDocument(submissionId, docType, file) {
    const formData = new FormData()
    formData.append('doc_type', docType)
    formData.append('file', file)
    try {
      await fetch(`${API_BASE}/submissions/${submissionId}/documents/`, {
        method: 'POST',
        headers: {
          Authorization: `Token ${localStorage.getItem('playto_token')}`,
        },
        body: formData,
      })
      // Reload submission to show new document
      const data = await fetchJson(`${API_BASE}/submissions/${submissionId}/`)
      setSelectedSubmission(data)
    } catch (err) {
      setError(err.detail || 'Failed to upload document.')
    }
  }

  async function performReview(submissionId) {
    try {
      const data = await fetchJson(`${API_BASE}/submissions/${submissionId}/review/`, {
        method: 'POST',
        body: JSON.stringify(reviewAction),
      })
      setSubmissions(submissions.map(s => s.id === submissionId ? data : s))
      setSelectedSubmission(data)
      setReviewAction({ action: '', reason: '' })
    } catch (err) {
      setError(err.detail || 'Failed to perform review action.')
    }
  }

  function renderQueue() {
    return (
      <div className="space-y-4">
        {metrics && (
          <div className="grid gap-4 md:grid-cols-3">
            <div className="p-4 bg-white rounded shadow">
              <div className="text-sm text-slate-500">In queue</div>
              <div className="mt-2 text-2xl font-semibold">{metrics.submissions_in_queue}</div>
            </div>
            <div className="p-4 bg-white rounded shadow">
              <div className="text-sm text-slate-500">Average time in queue</div>
              <div className="mt-2 text-2xl font-semibold">{metrics.average_time_in_queue_minutes} min</div>
            </div>
            <div className="p-4 bg-white rounded shadow">
              <div className="text-sm text-slate-500">Approval rate</div>
              <div className="mt-2 text-2xl font-semibold">{metrics.approval_rate_last_7_days}%</div>
            </div>
          </div>
        )}
        <div className="space-y-3">
          {submissions.map((submission) => (
            <div key={submission.id} className="p-4 bg-white rounded shadow">
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-sm text-slate-500">{submission.business_name || 'Untitled submission'}</div>
                  <div className="mt-1 font-semibold">State: {submission.state}</div>
                  <div className="text-sm text-slate-600">
                    Personal: {submission.personal_name} • Email: {submission.personal_email}
                  </div>
                  {submission.is_at_risk && (
                    <div className="mt-2 text-red-600 text-sm font-semibold">At risk - over 24 hours</div>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => { setSelectedSubmission(submission); setView('detail') }}
                    className="px-3 py-1 bg-blue-500 text-white rounded text-sm"
                  >
                    View
                  </button>
                  {user.role === ROLE_MERCHANT && submission.state === 'draft' && (
                    <button
                      onClick={() => submitSubmission(submission.id)}
                      className="px-3 py-1 bg-green-500 text-white rounded text-sm"
                    >
                      Submit
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  function renderKycForm() {
    return (
      <div className="rounded bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-xl font-semibold">Create KYC Submission</h2>
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Personal Name</span>
              <input
                value={kycForm.personal_name}
                onChange={(e) => setKycForm({ ...kycForm, personal_name: e.target.value })}
                className="mt-1 block w-full rounded border border-slate-300 p-2"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Personal Email</span>
              <input
                type="email"
                value={kycForm.personal_email}
                onChange={(e) => setKycForm({ ...kycForm, personal_email: e.target.value })}
                className="mt-1 block w-full rounded border border-slate-300 p-2"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Personal Phone</span>
              <input
                value={kycForm.personal_phone}
                onChange={(e) => setKycForm({ ...kycForm, personal_phone: e.target.value })}
                className="mt-1 block w-full rounded border border-slate-300 p-2"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Business Name</span>
              <input
                value={kycForm.business_name}
                onChange={(e) => setKycForm({ ...kycForm, business_name: e.target.value })}
                className="mt-1 block w-full rounded border border-slate-300 p-2"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Business Type</span>
              <input
                value={kycForm.business_type}
                onChange={(e) => setKycForm({ ...kycForm, business_type: e.target.value })}
                className="mt-1 block w-full rounded border border-slate-300 p-2"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Expected Monthly Volume (USD)</span>
              <input
                type="number"
                value={kycForm.expected_monthly_volume_usd}
                onChange={(e) => setKycForm({ ...kycForm, expected_monthly_volume_usd: e.target.value })}
                className="mt-1 block w-full rounded border border-slate-300 p-2"
              />
            </label>
          </div>
          <div className="flex gap-2">
            <button onClick={createSubmission} className="px-4 py-2 bg-blue-500 text-white rounded">
              Create Submission
            </button>
            <button onClick={() => setView('dashboard')} className="px-4 py-2 bg-slate-500 text-white rounded">
              Cancel
            </button>
          </div>
        </div>
      </div>
    )
  }

  function renderSubmissionDetail() {
    if (!selectedSubmission) return null
    return (
      <div className="rounded bg-white p-6 shadow-sm">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Submission Details</h2>
          <button onClick={() => { setSelectedSubmission(null); setView('dashboard') }} className="px-3 py-1 bg-slate-500 text-white rounded">
            Back
          </button>
        </div>
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div><strong>State:</strong> {selectedSubmission.state}</div>
            <div><strong>Personal Name:</strong> {selectedSubmission.personal_name}</div>
            <div><strong>Email:</strong> {selectedSubmission.personal_email}</div>
            <div><strong>Phone:</strong> {selectedSubmission.personal_phone}</div>
            <div><strong>Business Name:</strong> {selectedSubmission.business_name}</div>
            <div><strong>Business Type:</strong> {selectedSubmission.business_type}</div>
            <div><strong>Expected Volume:</strong> ${selectedSubmission.expected_monthly_volume_usd}</div>
            {selectedSubmission.review_reason && (
              <div><strong>Review Reason:</strong> {selectedSubmission.review_reason}</div>
            )}
          </div>
          <div>
            <h3 className="font-semibold mb-2">Documents</h3>
            <div className="space-y-2">
              {selectedSubmission.documents.map((doc) => (
                <div key={doc.id} className="flex justify-between items-center p-2 bg-slate-50 rounded">
                  <span>{doc.doc_type}: {doc.file.split('/').pop()}</span>
                  <a href={doc.file} target="_blank" rel="noopener noreferrer" className="text-blue-500">View</a>
                </div>
              ))}
            </div>
            {user.role === ROLE_MERCHANT && (selectedSubmission.state === 'draft' || selectedSubmission.state === 'more_info_requested') && (
              <div className="mt-4 space-y-2">
                <h4 className="font-semibold">Upload Documents</h4>
                {['pan', 'aadhaar', 'bank_statement'].map((type) => (
                  <div key={type} className="flex gap-2">
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png"
                      onChange={(e) => setDocuments({ ...documents, [type]: e.target.files[0] })}
                      className="flex-1"
                    />
                    <button
                      onClick={() => uploadDocument(selectedSubmission.id, type, documents[type])}
                      disabled={!documents[type]}
                      className="px-3 py-1 bg-green-500 text-white rounded disabled:opacity-50"
                    >
                      Upload {type}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          {user.role === ROLE_REVIEWER && selectedSubmission.state === 'submitted' && (
            <div className="mt-4 space-y-2">
              <h4 className="font-semibold">Review Actions</h4>
              <select
                value={reviewAction.action}
                onChange={(e) => setReviewAction({ ...reviewAction, action: e.target.value })}
                className="block w-full rounded border border-slate-300 p-2"
              >
                <option value="">Select action</option>
                <option value="start_review">Start Review</option>
                <option value="approve">Approve</option>
                <option value="reject">Reject</option>
                <option value="request_more_info">Request More Info</option>
              </select>
              {(reviewAction.action === 'reject' || reviewAction.action === 'request_more_info') && (
                <textarea
                  placeholder="Reason"
                  value={reviewAction.reason}
                  onChange={(e) => setReviewAction({ ...reviewAction, reason: e.target.value })}
                  className="block w-full rounded border border-slate-300 p-2"
                />
              )}
              <button
                onClick={() => performReview(selectedSubmission.id)}
                disabled={!reviewAction.action}
                className="px-4 py-2 bg-blue-500 text-white rounded disabled:opacity-50"
              >
                Submit Review
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-4xl">
        <header className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Playto KYC</h1>
            <p className="text-sm text-slate-600">Merchant and reviewer dashboard</p>
          </div>
          {user.role && (
            <div className="flex gap-2">
              {user.role === ROLE_MERCHANT && (
                <button onClick={() => setView('create')} className="rounded bg-green-500 px-4 py-2 text-white">
                  New Submission
                </button>
              )}
              <button onClick={logout} className="rounded bg-slate-800 px-4 py-2 text-white">
                Logout
              </button>
            </div>
          )}
        </header>

        {error && <div className="mb-4 rounded border border-red-300 bg-red-50 p-4 text-red-700">{error}</div>}

        {!user.role ? (
          <div className="rounded bg-white p-6 shadow-sm">
            <div className="mb-4 flex gap-2">
              <button 
                onClick={() => setView('login')} 
                className={`px-4 py-2 rounded ${view === 'login' ? 'bg-slate-800 text-white' : 'bg-slate-200'}`}
              >
                Login
              </button>
              <button 
                onClick={() => setView('register')} 
                className={`px-4 py-2 rounded ${view === 'register' ? 'bg-slate-800 text-white' : 'bg-slate-200'}`}
              >
                Register
              </button>
            </div>
            
            {view === 'login' || view === 'login' ? (
              <>
                <h2 className="mb-4 text-xl font-semibold">Login</h2>
                <div className="space-y-4">
                  <label className="block">
                    <span className="text-sm font-medium text-slate-700">Username</span>
                    <input
                      value={form.username}
                      onChange={(e) => setForm({ ...form, username: e.target.value })}
                      className="mt-1 block w-full rounded border border-slate-300 p-2"
                    />
                  </label>
                  <label className="block">
                    <span className="text-sm font-medium text-slate-700">Password</span>
                    <input
                      type="password"
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      className="mt-1 block w-full rounded border border-slate-300 p-2"
                    />
                  </label>
                  <button onClick={login} className="rounded bg-slate-800 px-4 py-2 text-white">
                    Log in
                  </button>
                </div>
                <p className="mt-4 text-sm text-slate-500">
                  Use seeded accounts: reviewer/password, merchant_draft/password, merchant_under_review/password.
                </p>
              </>
            ) : (
              <>
                <h2 className="mb-4 text-xl font-semibold">Register</h2>
                <div className="space-y-4">
                  <label className="block">
                    <span className="text-sm font-medium text-slate-700">Username</span>
                    <input
                      value={registerForm.username}
                      onChange={(e) => setRegisterForm({ ...registerForm, username: e.target.value })}
                      className="mt-1 block w-full rounded border border-slate-300 p-2"
                    />
                  </label>
                  <label className="block">
                    <span className="text-sm font-medium text-slate-700">Email</span>
                    <input
                      type="email"
                      value={registerForm.email}
                      onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                      className="mt-1 block w-full rounded border border-slate-300 p-2"
                    />
                  </label>
                  <label className="block">
                    <span className="text-sm font-medium text-slate-700">Password</span>
                    <input
                      type="password"
                      value={registerForm.password}
                      onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                      className="mt-1 block w-full rounded border border-slate-300 p-2"
                    />
                  </label>
                  <label className="block">
                    <span className="text-sm font-medium text-slate-700">Role</span>
                    <select
                      value={registerForm.role}
                      onChange={(e) => setRegisterForm({ ...registerForm, role: e.target.value })}
                      className="mt-1 block w-full rounded border border-slate-300 p-2"
                    >
                      <option value="merchant">Merchant</option>
                      <option value="reviewer">Reviewer</option>
                    </select>
                  </label>
                  <button onClick={register} className="rounded bg-slate-800 px-4 py-2 text-white">
                    Register
                  </button>
                </div>
              </>
            )}
          </div>
        ) : view === 'create' ? (
          renderKycForm()
        ) : view === 'detail' ? (
          renderSubmissionDetail()
        ) : (
          <div className="space-y-6">
            <div className="rounded bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold">Welcome, {user.username}</h2>
                  <p className="text-sm text-slate-600">Role: {user.role}</p>
                </div>
              </div>
            </div>
            <div className="rounded bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-xl font-semibold">Dashboard</h2>
              {renderQueue()}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App

