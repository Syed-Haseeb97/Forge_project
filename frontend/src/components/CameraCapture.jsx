import { useState, useRef, useEffect } from 'react'
import { Camera, Upload, X, RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react'
import toast from 'react-hot-toast'

export default function CameraCapture({ onCapture, onClear, currentPreview = null, label = 'Photographic Evidence' }) {
  const [stream, setStream] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [facingMode, setFacingMode] = useState('environment') // 'environment' (back) | 'user' (front)
  const [cameraError, setCameraError] = useState(null)
  const [hasMultipleCameras, setHasMultipleCameras] = useState(false)
  const [preview, setPreview] = useState(currentPreview)
  const [selectedFileName, setSelectedFileName] = useState('')

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const nativeCameraInputRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    setPreview(currentPreview)
  }, [currentPreview])

  // Stop camera stream when unmounting or closing modal
  useEffect(() => {
    return () => {
      stopCameraStream()
    }
  }, [])

  const stopCameraStream = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop())
      setStream(null)
    }
  }

  const startCamera = async (mode = facingMode) => {
    setCameraError(null)
    setIsModalOpen(true)

    // Stop existing stream if any
    if (stream) {
      stream.getTracks().forEach(track => track.stop())
    }

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Camera API is not supported in this browser environment.')
      }

      // Check available video devices
      const devices = await navigator.mediaDevices.enumerateDevices()
      const videoInputs = devices.filter(d => d.kind === 'videoinput')
      setHasMultipleCameras(videoInputs.length > 1)

      const constraints = {
        video: {
          facingMode: { ideal: mode },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      }

      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints)
      setStream(mediaStream)

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream
        videoRef.current.play().catch(() => {})
      }
    } catch (err) {
      console.error('Camera access error:', err)
      let msg = 'Could not access device camera.'
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        msg = 'Camera permission was denied. Please allow camera access in your browser settings, or use the file upload option.'
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        msg = 'No camera device detected on this terminal.'
      }
      setCameraError(msg)
    }
  }

  const handleFlipCamera = () => {
    const nextMode = facingMode === 'environment' ? 'user' : 'environment'
    setFacingMode(nextMode)
    startCamera(nextMode)
  }

  const handleCaptureFrame = () => {
    if (!videoRef.current) return

    const video = videoRef.current
    const canvas = canvasRef.current || document.createElement('canvas')
    canvas.width = video.videoWidth || 1280
    canvas.height = video.videoHeight || 720

    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

    canvas.toBlob(blob => {
      if (!blob) {
        toast.error('Failed to capture image snapshot')
        return
      }
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
      const file = new File([blob], `evidence-${timestamp}.jpg`, { type: 'image/jpeg' })
      const dataUrl = canvas.toDataURL('image/jpeg', 0.92)

      setPreview(dataUrl)
      setSelectedFileName(file.name)
      stopCameraStream()
      setIsModalOpen(false)
      onCapture?.(file, dataUrl)
      toast.success('Photo captured successfully')
    }, 'image/jpeg', 0.92)
  }

  const handleNativeCameraChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      processSelectedFile(file)
    }
    e.target.value = ''
  }

  const handleFileInputChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      processSelectedFile(file)
    }
    e.target.value = ''
  }

  const processSelectedFile = (file) => {
    if (file.size > 25 * 1024 * 1024) {
      toast.error('File size exceeds 25MB limit')
      return
    }
    setSelectedFileName(file.name)
    if (file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const url = e.target.result
        setPreview(url)
        onCapture?.(file, url)
      }
      reader.readAsDataURL(file)
    } else {
      setPreview(null)
      onCapture?.(file, null)
    }
  }

  const handleRemove = () => {
    setPreview(null)
    setSelectedFileName('')
    stopCameraStream()
    onClear?.()
  }

  const closeModal = () => {
    stopCameraStream()
    setIsModalOpen(false)
    setCameraError(null)
  }

  return (
    <div className="space-y-3">
      {/* Hidden system inputs */}
      <input
        ref={nativeCameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={handleNativeCameraChange}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,audio/*,.pdf"
        className="hidden"
        onChange={handleFileInputChange}
      />

      {/* Captured / Uploaded Preview */}
      {preview ? (
        <div className="relative rounded-2xl overflow-hidden border border-[#173e42]/20 bg-[#0d3035] group">
          <img
            src={preview}
            alt="Evidence preview"
            className="w-full h-56 sm:h-64 object-cover"
          />
          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/45 to-transparent p-3 sm:p-4 flex items-center justify-between text-white">
            <div className="flex items-center gap-2 truncate text-xs sm:text-sm">
              <CheckCircle2 size={16} className="text-[#e8b855] shrink-0" />
              <span className="truncate font-medium">{selectedFileName || 'Evidence Attached'}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => startCamera()}
                className="bg-white/20 hover:bg-white/30 backdrop-blur-sm px-3 py-1.5 rounded-full text-xs font-bold flex items-center gap-1.5 transition"
                title="Retake Photo"
              >
                <RefreshCw size={12} />
                <span>Retake</span>
              </button>
              <button
                type="button"
                onClick={handleRemove}
                className="bg-[#b04b37] hover:bg-[#8e3827] px-3 py-1.5 rounded-full text-xs font-bold flex items-center gap-1 transition"
                title="Remove Photo"
              >
                <X size={12} />
                <span>Remove</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Action buttons for Camera vs File Upload */
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Direct Camera Option */}
          <button
            type="button"
            onClick={() => {
              if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
                nativeCameraInputRef.current?.click()
              } else {
                startCamera()
              }
            }}
            className="flex items-center gap-3.5 p-4 rounded-xl border border-[#173e42]/15 bg-[#0d3035] text-white hover:bg-[#16444a] transition text-left group"
          >
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-white/10 text-[#e8b855]">
              <Camera size={20} />
            </div>
            <div>
              <span className="block font-bold text-xs">Take Photo Directly</span>
              <span className="text-[10px] text-white/60">Open device camera</span>
            </div>
          </button>

          {/* File Upload Option */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-3.5 p-4 rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#06181b] text-[#0d3035] dark:text-[#f6f4ee] hover:bg-[#fffaf0] dark:hover:bg-[#123035] transition text-left group"
          >
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-[#f0f4f3] dark:bg-[#163035] text-[#347161]">
              <Upload size={20} />
            </div>
            <div>
              <span className="block font-bold text-xs">Upload from Files / Gallery</span>
              <span className="text-[10px] text-[#70817e]">Images or documents</span>
            </div>
          </button>
        </div>
      )}

      {/* In-App Live Camera Viewfinder Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex flex-col justify-between p-4 sm:p-6 animate-fadeIn">
          {/* Header */}
          <div className="flex items-center justify-between text-white max-w-2xl w-full mx-auto">
            <div className="flex items-center gap-2">
              <Camera size={18} className="text-[#e8b855]" />
              <span className="font-semibold text-xs tracking-wider uppercase">Official Camera Capture</span>
            </div>
            <button
              type="button"
              onClick={closeModal}
              className="p-2 text-white/60 hover:text-white hover:bg-white/10 rounded-full transition"
              title="Close Viewfinder"
            >
              <X size={20} />
            </button>
          </div>

          {/* Viewfinder Window */}
          <div className="relative max-w-2xl w-full mx-auto my-auto aspect-[4/3] sm:aspect-[16/9] bg-black rounded-2xl overflow-hidden flex items-center justify-center border border-white/20 shadow-2xl">
            {cameraError ? (
              <div className="p-6 text-center max-w-md">
                <AlertCircle size={36} className="mx-auto text-[#b04b37] mb-3" />
                <p className="text-sm font-bold text-white mb-2">Camera Access Required</p>
                <p className="text-xs text-white/70 leading-relaxed mb-4">{cameraError}</p>
                <div className="flex gap-2 justify-center">
                  <button
                    type="button"
                    onClick={() => startCamera()}
                    className="rounded-full bg-white/20 px-4 py-2 text-xs font-bold text-white hover:bg-white/30"
                  >
                    Try Again
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      closeModal()
                      fileInputRef.current?.click()
                    }}
                    className="rounded-full bg-[#e8b855] px-4 py-2 text-xs font-bold text-[#0d3035] hover:bg-[#efc56b]"
                  >
                    Upload File Instead
                  </button>
                </div>
              </div>
            ) : (
              <>
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-cover"
                />
                {/* Viewfinder Reticle Grid */}
                <div className="absolute inset-8 border border-white/20 rounded-xl pointer-events-none flex flex-col justify-between p-4">
                  <div className="flex justify-between text-[10px] font-mono text-white/50 uppercase">
                    <span>Evidence Verification</span>
                    <span>1080P</span>
                  </div>
                  <div className="self-center size-8 border border-white/40 rounded-full flex items-center justify-center">
                    <div className="size-1.5 bg-[#e8b855] rounded-full animate-ping" />
                  </div>
                  <div className="text-[10px] font-mono text-white/50 text-right">
                    Jan Aawaz (जनAawaz) Public Infrastructure Record
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Controls Footer */}
          <div className="max-w-2xl w-full mx-auto flex items-center justify-around py-3 text-white">
            {hasMultipleCameras ? (
              <button
                type="button"
                onClick={handleFlipCamera}
                className="p-3 bg-white/10 hover:bg-white/20 rounded-full transition"
                title="Switch Camera"
              >
                <RefreshCw size={20} />
              </button>
            ) : (
              <div className="w-11" />
            )}

            {/* Shutter Button */}
            {!cameraError && (
              <button
                type="button"
                onClick={handleCaptureFrame}
                className="size-16 rounded-full border-4 border-white flex items-center justify-center hover:scale-105 active:scale-95 transition bg-white/20"
                title="Capture Photographic Proof"
              >
                <div className="size-12 bg-[#e8b855] rounded-full shadow-lg" />
              </button>
            )}

            <button
              type="button"
              onClick={closeModal}
              className="px-4 py-2 text-xs font-bold text-white/60 hover:text-white"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
