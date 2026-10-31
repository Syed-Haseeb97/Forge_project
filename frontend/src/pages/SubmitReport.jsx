import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import axios from 'axios'
import toast from 'react-hot-toast'
import CivicIcon from '../components/CivicIcon'
import { CATEGORIES } from '../components/constants'
import CivicMap from '../components/CivicMap'
import { useAuth } from '../components/AuthContext'

export default function SubmitReport() {
  const navigate = useNavigate()
  const routerLocation = useLocation()
  const { user, isVerified } = useAuth()
  const [form, setForm] = useState(() => ({
    title: routerLocation.state?.title || '',
    description: routerLocation.state?.description || '',
    category: routerLocation.state?.category || 'road_damage',
    location: routerLocation.state?.location || '',
    latitude: routerLocation.state?.latitude || '',
    longitude: routerLocation.state?.longitude || '',
  }))
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [fileType, setFileType] = useState('image')
  const [submitting, setSubmitting] = useState(false)
  const [autofilling, setAutofilling] = useState(false)
  const [locating, setLocating] = useState(false)
  const [mapCenter, setMapCenter] = useState(null)
  const [nearbyReports, setNearbyReports] = useState([])
  const [checkingNearby, setCheckingNearby] = useState(false)

  const cameraInputRef = useRef(null)
  const fileInputRef = useRef(null)
  const audioInputRef = useRef(null)

  // In-browser MediaRecorder voice recording state
  const [isRecording, setIsRecording] = useState(false)
  const [recordDuration, setRecordDuration] = useState(0)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const recordingTimerRef = useRef(null)

  useEffect(() => {
    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current)
    }
  }, [])

  const handleStartRecording = async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      toast('Browser microphone access unavailable; opening audio file picker', { icon: '🎙️' })
      audioInputRef.current?.click()
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioChunksRef.current = []
      const mime = MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : (MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '')
      const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream)
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data)
        }
      }

      recorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop())
        const mimeType = recorder.mimeType || 'audio/webm'
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType })
        const ext = mimeType.includes('mp4') ? 'm4a' : 'webm'
        const audioFile = new File([audioBlob], `voice_complaint_${Date.now()}.${ext}`, { type: mimeType })
        setFile(audioFile)
        setFileType('audio')
        setPreview(URL.createObjectURL(audioBlob))
        setIsRecording(false)
        clearInterval(recordingTimerRef.current)
        setRecordDuration(0)
        toast.success('Voice complaint recorded! Click "Auto-fill from photo/voice" to transcribe.', { icon: '🎙️' })
      }

      recorder.start(250)
      setIsRecording(true)
      setRecordDuration(0)
      recordingTimerRef.current = setInterval(() => {
        setRecordDuration(d => d + 1)
      }, 1000)
    } catch (err) {
      console.warn('Microphone error:', err)
      toast.error('Microphone access denied or blocked. Select an audio file instead.')
      audioInputRef.current?.click()
    }
  }

  const handleStopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
  }

  // Auto-acquire current location if granted by browser to CENTER the map only (does NOT drop pin)
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = Number(pos.coords.latitude.toFixed(6))
          const lng = Number(pos.coords.longitude.toFixed(6))
          setMapCenter([lat, lng])
        },
        () => {
          // Geolocation not granted; remains centered on neutral India-wide view
        },
        { timeout: 5000, enableHighAccuracy: true }
      )
    }
  }, [])

  // Use browser GPS manually (sets coordinates and drops pin)
  const useMyLocation = () => {
    if (!navigator.geolocation) {
      toast.error('Geolocation is not supported by your browser')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(6))
        const lng = Number(pos.coords.longitude.toFixed(6))
        setMapCenter([lat, lng])
        setForm(f => ({ ...f, latitude: String(lat), longitude: String(lng) }))
        setLocating(false)
        toast.success('Current location acquired')
        checkProximityDuplicates(lat, lng)
      },
      (err) => {
        setLocating(false)
        toast.error('Location permission denied or unavailable')
      },
      { timeout: 10000, enableHighAccuracy: true }
    )
  }

  // Duplicate detection query
  const checkProximityDuplicates = async (lat, lng) => {
    if (!lat || !lng) return
    setCheckingNearby(true)
    try {
      const { data } = await axios.get('/api/reports/nearby', {
        params: { latitude: lat, longitude: lng, radius_km: 0.5 }
      })
      setNearbyReports(data)
    } catch {
      // Background non-critical check
    } finally {
      setCheckingNearby(false)
    }
  }

  useEffect(() => {
    const lat = parseFloat(form.latitude)
    const lng = parseFloat(form.longitude)
    if (!isNaN(lat) && !isNaN(lng)) {
      const timer = setTimeout(() => {
        checkProximityDuplicates(lat, lng)
      }, 600)
      return () => clearTimeout(timer)
    }
  }, [form.latitude, form.longitude])

  const handleMapPositionSelect = ({ latitude, longitude }) => {
    setMapCenter([latitude, longitude])
    setForm(f => ({
      ...f,
      latitude: String(latitude),
      longitude: String(longitude),
    }))
  }

  const handleFileChange = (e, type) => {
    const selected = e.target.files?.[0]
    if (!selected) return

    setFile(selected)
    setFileType(type)

    if (type === 'audio') {
      setPreview(URL.createObjectURL(selected))
    } else {
      const reader = new FileReader()
      reader.onload = () => setPreview(reader.result)
      reader.readAsDataURL(selected)
    }
    toast.success(`Attached ${selected.name}`)
    e.target.value = ''
  }

  const handleClearMedia = () => {
    setFile(null)
    setPreview(null)
  }

  // Auto-fill from photo or voice note via Gemini AI
  const handleAutoFill = async () => {
    if (!file) {
      toast.error('Please attach a photo or audio recording first')
      return
    }

    setAutofilling(true)
    const toastId = toast.loading('Multimodal AI is analyzing evidence...')

    try {
      const fd = new FormData()
      fd.append('media', file)
      if (form.description.trim()) {
        fd.append('text', form.description)
      } else if (form.title.trim()) {
        fd.append('text', form.title)
      }

      const { data } = await axios.post('/api/ai/prefill', fd)

      let filledCount = 0
      setForm(prev => {
        const next = { ...prev }
        if (!prev.title.trim() && data.title) {
          next.title = data.title
          filledCount++
        }
        if ((!prev.category || prev.category === 'road_damage' || prev.category === 'other') && data.category) {
          next.category = data.category
          filledCount++
        }
        if (!prev.description.trim() && data.description) {
          next.description = data.description
          filledCount++
        }
        return next
      })

      toast.success(
        `AI auto-filled details (${data.detected_language || 'Multimodal'})`,
        { id: toastId, icon: '✨' }
      )
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Auto-fill failed to interpret evidence', { id: toastId })
    } finally {
      setAutofilling(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.title.trim() || !form.location.trim()) {
      toast.error('Please enter all required incident details')
      return
    }

    const latVal = parseFloat(form.latitude)
    const lngVal = parseFloat(form.longitude)
    if (!form.latitude || !form.longitude || isNaN(latVal) || isNaN(lngVal)) {
      toast.error('Please pin the location on the map or click "Use My Current Location"')
      return
    }

    setSubmitting(true)
    try {
      const fd = new FormData()
      Object.entries(form).forEach(([k, v]) => v && fd.append(k, v))
      if (user?.email) fd.append('citizen_email', user.email)
      if (file) fd.append('media', file)

      const { data } = await axios.post('/api/reports', fd)
      toast.success('Incident logged. Multimodal AI triage complete.')
      navigate(`/reports/${data.id}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Incident submission failed')
      setSubmitting(false)
    }
  }

  const handleUpvoteNearby = async (id) => {
    try {
      await axios.post(`/api/reports/${id}/upvote`)
      toast.success('Endorsed existing incident. Redirecting...')
      navigate(`/reports/${id}`)
    } catch {
      toast.error('Failed to register endorsement')
    }
  }

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const hasCoordinates = Boolean(form.latitude && form.longitude && !isNaN(parseFloat(form.latitude)) && !isNaN(parseFloat(form.longitude)))
  const parsedLat = hasCoordinates ? parseFloat(form.latitude) : null
  const parsedLng = hasCoordinates ? parseFloat(form.longitude) : null
  const mapSelectedPos = hasCoordinates ? [parsedLat, parsedLng] : null

  return (
    <div className="min-h-screen bg-[#f6f4ee] dark:bg-[#06181b] text-[#102a2f] dark:text-[#f6f4ee] transition-colors py-8 sm:py-14">
      <div className="mx-auto max-w-[820px] px-5 lg:px-8">

        {/* Citizen Verification Gate */}
        {!isVerified ? (
          <div className="relative mx-auto max-w-xl">
            <div className="absolute -inset-3 rotate-1 rounded-[30px] bg-[#e8b855]/20 pointer-events-none" />
            <div className="relative overflow-hidden rounded-[26px] border border-white/80 dark:border-[#173e42]/30 bg-white dark:bg-[#0b2529] p-8 sm:p-12 text-center shadow-[0_25px_60px_rgba(26,53,52,.12)]">
              <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-[#0d3035] text-[#e8b855] shadow-md">
                <CivicIcon name="shield" size={30} />
              </div>
              <p className="mt-6 text-[10px] font-bold tracking-[0.18em] uppercase text-[#ba7c29]">
                IDENTITY VERIFICATION REQUIRED
              </p>
              <h2 className="mt-2 font-serif text-3xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                Verify your email first
              </h2>
              <p className="mx-auto mt-3 max-w-md text-xs sm:text-sm leading-relaxed text-[#5f716e] dark:text-[#95a9a6]">
                To maintain public accountability and keep you updated on engineering actions, citizens must verify their email address before registering an incident.
              </p>

              <div className="mt-8 space-y-3">
                <button
                  type="button"
                  onClick={() => navigate('/auth?redirect=/submit')}
                  className="flex w-full items-center justify-center gap-3 rounded-xl bg-[#0d3035] px-6 py-4 text-xs font-bold uppercase tracking-wider text-white shadow-md hover:bg-[#16444a] transition"
                >
                  VERIFY WITH EMAIL & PROCEED
                  <CivicIcon name="arrow" size={16} />
                </button>
                <Link
                  to="/"
                  className="block text-xs font-bold text-[#6a7c79] dark:text-[#95a9a6] hover:text-[#0d3035] dark:hover:text-white pt-2"
                >
                  ← Return to Public Dashboard
                </Link>
              </div>

              <div className="mt-8 flex items-center justify-center gap-2 border-t border-[#173e42]/10 dark:border-[#173e42]/30 pt-5 text-[10px] text-[#718481] dark:text-[#8ea5a2]">
                <CivicIcon name="shield" size={13} className="text-[#347161]" />
                <span>Your contact info remains private and is never shown publicly.</span>
              </div>
            </div>
          </div>
        ) : submitting ? (
          <div className="rounded-[26px] border border-white/70 bg-white dark:bg-[#0b2529] p-8 sm:p-14 text-center shadow-[0_30px_70px_rgba(26,53,52,.16)]">
            <div className="ai-orbit relative mx-auto flex size-20 items-center justify-center rounded-full bg-[#0d3035] text-[#e8b855]">
              <CivicIcon name="brain" size={32} />
              <span className="absolute -right-1 top-0 size-3 rounded-full bg-[#e8b855]" />
            </div>
            <p className="mt-7 text-[11px] font-bold tracking-[0.16em] uppercase text-[#ba7c29]">
              CIVIC AI IS EVALUATING
            </p>
            <h2 className="mt-2 font-serif text-3xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
              Triaging your report
            </h2>
            <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[#5f716e] dark:text-[#95a9a6]">
              Extracting multimodal evidence, diagnosing hazard severity, setting statutory SLA limits, and routing to the municipal engineering authority.
            </p>

            <div className="mx-auto mt-8 max-w-xs space-y-3.5 text-left">
              {[
                'Visual & audio evidence analyzed',
                'Priority hazard level evaluated',
                'Department routing & SLA docket assigned',
              ].map((label, idx) => (
                <div key={label} className="flex items-center gap-3 text-xs font-semibold">
                  <span className={`flex size-6 items-center justify-center rounded-full ${idx === 2 ? 'bg-[#fff3d8] text-[#ba7c29] dark:bg-[#34260f]' : 'bg-[#e3f0ea] text-[#2f7661] dark:bg-[#123830] dark:text-[#70b99e]'}`}>
                    {idx === 2 ? (
                      <span className="size-1.5 animate-pulse rounded-full bg-current" />
                    ) : (
                      <CivicIcon name="check" size={13} />
                    )}
                  </span>
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="relative">
            {/* Background Decorative Glow */}
            <div className="absolute -inset-4 rotate-1 rounded-[32px] bg-[#e8b855]/15 pointer-events-none" />

            {/* Form Container */}
            <div className="relative overflow-hidden rounded-[26px] border border-white/80 dark:border-[#173e42]/30 bg-white dark:bg-[#0b2529] p-6 sm:p-10 shadow-[0_30px_70px_rgba(26,53,52,.12)]">
              {/* Header */}
              <div className="mb-8 flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-[#173e42]/10 dark:border-[#173e42]/30 pb-6">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-[#bd7f23]/25 bg-[#fffaf0] dark:bg-[#0d3035] px-3 py-1.5 text-[10px] font-bold tracking-[0.14em] text-[#956018] dark:text-[#e8b855]">
                    <CivicIcon name="sparkle" size={13} />
                    SECURE CITIZEN GRIEVANCE REGISTRATION
                  </div>
                  <h1 className="mt-3 font-serif text-3xl sm:text-4xl font-bold tracking-tight text-[#0d3035] dark:text-[#f6f4ee]">
                    Tell us what happened
                  </h1>
                  <div className="mt-2.5 flex items-center gap-2 text-xs font-semibold text-[#2f7661] dark:text-[#70b99e] bg-[#e3f0ea] dark:bg-[#123830] px-3 py-1.5 rounded-full w-fit border border-[#347161]/20">
                    <CivicIcon name="check" size={13} />
                    <span>
                      Verified Citizen: {user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user?.email}
                    </span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6]">
                    Provide details or evidence. AI assesses urgency and assigns statutory resolution deadlines.
                  </p>
                </div>
                <span className="self-start sm:self-auto rounded-full bg-[#edf2ef] dark:bg-[#153439] px-3.5 py-1.5 text-[10px] font-bold tracking-wider text-[#436461] dark:text-[#95b0ac]">
                  EST. 2 MIN
                </span>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Department / Category Selection */}
                <div>
                  <label className="mb-2 block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    Municipal Department & Infrastructure Category <span className="text-[#b04b37]">*</span>
                  </label>
                  <div className="relative">
                    <select
                      required
                      value={form.category}
                      onChange={set('category')}
                      className="w-full appearance-none rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-4 py-3.5 text-sm text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29] focus:ring-2 focus:ring-[#ba7c29]/15 transition font-semibold"
                    >
                      {CATEGORIES.map(c => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                    <CivicIcon name="chevron" size={16} className="pointer-events-none absolute right-4 top-4 rotate-90 text-[#6c7c7a]" />
                  </div>
                </div>

                {/* Title */}
                <div>
                  <label className="mb-2 block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    Incident Summary / Title <span className="text-[#b04b37]">*</span>
                  </label>
                  <input
                    required
                    type="text"
                    value={form.title}
                    onChange={set('title')}
                    placeholder="e.g. Hazardous deep pothole on flyover descent"
                    className="w-full rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-4 py-3.5 text-sm text-[#0d3035] dark:text-[#f6f4ee] placeholder:text-[#9aa6a4] outline-none focus:border-[#ba7c29] focus:ring-2 focus:ring-[#ba7c29]/15 transition"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="mb-2 block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    Describe the issue & observations <span className="text-[#b04b37]">*</span>
                  </label>
                  <textarea
                    required
                    rows={3}
                    value={form.description}
                    onChange={set('description')}
                    placeholder="What happened? Please include observable dimensions, risks to traffic or pedestrians, and nearby landmarks..."
                    className="w-full resize-none rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-4 py-3 text-sm leading-6 text-[#0d3035] dark:text-[#f6f4ee] placeholder:text-[#9aa6a4] outline-none focus:border-[#ba7c29] focus:ring-2 focus:ring-[#ba7c29]/15 transition"
                  />
                </div>

                {/* 3 Iconic Evidence Buttons */}
                <div>
                  <div className="mb-2.5 flex items-center justify-between">
                    <label className="block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                      Add evidence (Photo, Audio, or File)
                    </label>
                    <span className="text-[10px] text-[#6d7e7c] dark:text-[#8ea5a2]">
                      AI processes images & audio directly
                    </span>
                  </div>

                  {/* Hidden Inputs */}
                  <input
                    ref={cameraInputRef}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    onChange={(e) => handleFileChange(e, 'image')}
                  />
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*,.pdf"
                    className="hidden"
                    onChange={(e) => handleFileChange(e, 'image')}
                  />
                  <input
                    ref={audioInputRef}
                    type="file"
                    accept="audio/*"
                    capture
                    className="hidden"
                    onChange={(e) => handleFileChange(e, 'audio')}
                  />

                  {/* 3 Buttons Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {/* Take a Photo */}
                    <button
                      type="button"
                      onClick={() => cameraInputRef.current?.click()}
                      className="group flex min-h-[92px] flex-col items-start justify-between rounded-xl border border-[#2d615c]/30 bg-[#0d3035] p-4 text-left text-white transition hover:-translate-y-0.5 hover:bg-[#16444a]"
                    >
                      <span className="flex size-8 items-center justify-center rounded-lg bg-white/10 text-[#e8b855]">
                        <CivicIcon name="camera" size={18} />
                      </span>
                      <span>
                        <span className="block text-xs font-bold">Take a photo</span>
                        <span className="mt-0.5 block text-[10px] text-white/55">Open device camera</span>
                      </span>
                    </button>

                    {/* Upload Evidence */}
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="group flex min-h-[92px] flex-col items-start justify-between rounded-xl border border-[#2d615c]/30 bg-[#0d3035] p-4 text-left text-white transition hover:-translate-y-0.5 hover:bg-[#16444a]"
                    >
                      <span className="flex size-8 items-center justify-center rounded-lg bg-white/10 text-[#e8b855]">
                        <CivicIcon name="upload" size={18} />
                      </span>
                      <span>
                        <span className="block text-xs font-bold">Upload evidence</span>
                        <span className="mt-0.5 block text-[10px] text-white/55">Gallery or document</span>
                      </span>
                    </button>

                    {/* Record Audio via Browser MediaRecorder */}
                    {isRecording ? (
                      <button
                        type="button"
                        onClick={handleStopRecording}
                        className="group flex min-h-[92px] flex-col items-start justify-between rounded-xl border border-red-500/50 bg-[#b04b37] p-4 text-left text-white transition hover:-translate-y-0.5 animate-pulse shadow-md"
                      >
                        <span className="flex size-8 items-center justify-center rounded-lg bg-white/20 text-white">
                          <CivicIcon name="audio" size={18} />
                        </span>
                        <span>
                          <span className="block text-xs font-bold">Stop Recording ({recordDuration}s)</span>
                          <span className="mt-0.5 block text-[10px] text-white/80">Tap to finish speaking</span>
                        </span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={handleStartRecording}
                        className="group flex min-h-[92px] flex-col items-start justify-between rounded-xl border border-[#2d615c]/30 bg-[#0d3035] p-4 text-left text-white transition hover:-translate-y-0.5 hover:bg-[#16444a]"
                      >
                        <span className="flex size-8 items-center justify-center rounded-lg bg-white/10 text-[#e8b855]">
                          <CivicIcon name="audio" size={18} />
                        </span>
                        <span>
                          <span className="block text-xs font-bold">Speak complaint</span>
                          <span className="mt-0.5 block text-[10px] text-white/55">Record voice via mic</span>
                        </span>
                      </button>
                    )}
                  </div>

                  {/* Fallback Audio File Upload Trigger */}
                  <div className="flex justify-end pt-1">
                    <button
                      type="button"
                      onClick={() => audioInputRef.current?.click()}
                      className="text-[11px] font-medium text-[#556b68] dark:text-[#95a9a6] hover:text-[#ba7c29] underline transition"
                    >
                      Or select an existing audio file (.mp3, .m4a, .wav)
                    </button>
                  </div>

                  {/* Attached Media Preview */}
                  {file && preview && (
                    <div className="mt-3.5 rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] p-3.5">
                      <div className="flex items-center justify-between mb-2">
                        <span className="flex items-center gap-2 text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                          <CivicIcon name={fileType === 'audio' ? 'audio' : 'camera'} size={15} className="text-[#347161]" />
                          <span className="truncate max-w-[240px]">{file.name}</span>
                        </span>
                        <button
                          type="button"
                          onClick={handleClearMedia}
                          className="flex size-7 items-center justify-center rounded-full bg-white dark:bg-[#0b2529] text-[#70817e] hover:text-[#b04b37] border border-[#173e42]/15 transition"
                          title="Remove media"
                        >
                          <CivicIcon name="x" size={14} />
                        </button>
                      </div>

                      {fileType === 'audio' ? (
                        <audio controls src={preview} className="w-full mt-2" />
                      ) : (
                        <div className="relative max-h-48 overflow-hidden rounded-lg">
                          <img src={preview} alt="Attached Evidence" className="w-full object-cover" />
                        </div>
                      )}

                      {/* Auto-fill from photo/voice Button */}
                      <div className="mt-3 pt-3 border-t border-[#173e42]/10 dark:border-[#173e42]/20 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <button
                          type="button"
                          onClick={handleAutoFill}
                          disabled={autofilling}
                          className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#ba7c29] hover:bg-[#a66e24] px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-white shadow-sm transition disabled:opacity-50"
                        >
                          <CivicIcon name="sparkle" size={14} />
                          <span>{autofilling ? 'Analyzing Evidence...' : 'Auto-fill from photo/voice'}</span>
                        </button>
                        <span className="text-[10px] text-[#6c7c7a] dark:text-[#95a9a6]">
                          ✨ Extracts title, category & observations to empty fields
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Location Section (Zero Lat/Long numbers shown!) */}
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <label className="block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                      Location & Landmark <span className="text-[#b04b37]">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={useMyLocation}
                      disabled={locating}
                      className="flex items-center gap-1.5 rounded-full border border-[#173e42]/15 bg-[#fffaf0] dark:bg-[#0d3035] px-3 py-1 text-[11px] font-bold text-[#956018] dark:text-[#e8b855] hover:bg-[#ffeed1] transition"
                    >
                      <CivicIcon name="location" size={13} />
                      <span>{locating ? 'Acquiring GPS...' : 'Use My Current Location'}</span>
                    </button>
                  </div>

                  <div className="relative">
                    <CivicIcon name="location" size={17} className="absolute left-4 top-3.5 text-[#617572]" />
                    <input
                      required
                      type="text"
                      value={form.location}
                      onChange={set('location')}
                      placeholder="Street name, landmark, cross junction..."
                      className="w-full rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] py-3 pl-11 pr-4 text-sm text-[#0d3035] dark:text-[#f6f4ee] placeholder:text-[#9aa6a4] outline-none focus:border-[#ba7c29] focus:ring-2 focus:ring-[#ba7c29]/15 transition"
                    />
                  </div>

                  {/* Interactive Map Picker */}
                  <div className="mt-3 overflow-hidden rounded-2xl border border-[#173e42]/15 shadow-sm">
                    <div className="flex items-center justify-between bg-[#f8f8f4] dark:bg-[#06181b] px-3.5 py-2 text-[11px] text-[#6d7e7c] dark:text-[#8ea5a2] border-b border-[#173e42]/10">
                      <span>Click or drag pin to fine-tune map location</span>
                      {checkingNearby && (
                        <span className="font-semibold text-[#ba7c29] animate-pulse">Checking nearby reports...</span>
                      )}
                    </div>
                    <CivicMap
                      interactivePicker={true}
                      center={mapCenter}
                      selectedPosition={mapSelectedPos}
                      onPositionSelect={handleMapPositionSelect}
                      height="200px"
                      zoom={hasCoordinates ? 14 : (mapCenter ? 13 : 5)}
                    />
                  </div>
                  <p className="mt-1.5 text-[11px] text-[#6d7e7c] dark:text-[#8ea5a2] flex items-center gap-1.5">
                    <CivicIcon name="location" size={13} className="text-[#ba7c29]" />
                    <span>Tap the map to drop a pin on the exact spot.</span>
                  </p>

                  {/* Proximity duplicate warnings */}
                  {nearbyReports.length > 0 && (
                    <div className="mt-3 rounded-xl border border-[#bd7f23]/30 bg-[#fffaf0] dark:bg-[#201809] p-3.5">
                      <div className="flex items-center gap-2 text-xs font-bold text-[#956018] dark:text-[#e8b855]">
                        <CivicIcon name="alert" size={15} />
                        <span>Existing issues reported nearby ({nearbyReports.length})</span>
                      </div>
                      <p className="mt-1 text-[11px] text-[#6e7d7a] dark:text-[#8ea5a2]">
                        An active ticket may already cover this problem. You can endorse an existing report instead of creating a duplicate:
                      </p>
                      <div className="mt-2 space-y-2">
                        {nearbyReports.slice(0, 2).map((nr) => (
                          <div
                            key={nr.id}
                            className="flex items-center justify-between gap-3 rounded-lg border border-[#bd7f23]/20 bg-white dark:bg-[#0b2529] p-2.5 text-xs"
                          >
                            <div className="min-w-0 flex-1">
                              <p className="font-bold text-[#0d3035] dark:text-[#f6f4ee] truncate">{nr.title}</p>
                              <p className="text-[10px] text-[#718481]">{Math.round((nr.distance_km || 0) * 1000)}m away · Status: {nr.status}</p>
                            </div>
                            <button
                              type="button"
                              onClick={() => handleUpvoteNearby(nr.id)}
                              className="rounded-full bg-[#e8b855] px-3 py-1 text-[10px] font-bold text-[#0d3035] hover:bg-[#efc56b] transition shrink-0"
                            >
                              ENDORSE THIS
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* AI Assurance Box */}
                <div className="flex items-center gap-3 rounded-xl border border-[#d6b873]/35 bg-[#fffaf0] dark:bg-[#181a17] px-4 py-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[#0d3035] text-[#e8b855]">
                    <CivicIcon name="brain" size={18} />
                  </span>
                  <p className="text-[11px] leading-4 text-[#5c6e6c] dark:text-[#95a9a6]">
                    <strong className="text-[#0d3035] dark:text-[#f6f4ee]">Multimodal AI Assessment</strong>
                    <br />
                    Visual and audio evidence is diagnosed, prioritized, and sent directly to engineering dispatch.
                  </p>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex w-full items-center justify-center gap-3 rounded-xl bg-[#e8b855] px-6 py-4 text-xs font-extrabold tracking-[0.06em] uppercase text-[#153034] shadow-[0_5px_20px_rgba(196,141,36,.2)] transition hover:-translate-y-0.5 hover:bg-[#efc56b] disabled:opacity-60"
                >
                  SUBMIT FOR AI EVALUATION & ROUTING
                  <CivicIcon name="arrow" size={16} />
                </button>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
