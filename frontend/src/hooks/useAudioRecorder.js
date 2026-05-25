import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * 브라우저 MediaRecorder API 래퍼 훅
 * - 녹음 시작/중지
 * - 녹음된 Blob 반환
 * - 경과 시간 추적
 *
 * 실제 STT 호출은 services/api.js에서 처리.
 */
export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false)
  const [audioBlob, setAudioBlob] = useState(null)
  const [elapsed, setElapsed] = useState(0)  // 초

  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const streamRef = useRef(null)
  const startTimeRef = useRef(0)
  const intervalRef = useRef(null)

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const recorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm'  // 대부분 브라우저 지원. 백엔드에서 변환 필요할 수 있음
      })
      mediaRecorderRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setAudioBlob(blob)
        // 스트림 해제
        streamRef.current?.getTracks().forEach(t => t.stop())
        streamRef.current = null
      }

      recorder.start()
      startTimeRef.current = Date.now()
      setIsRecording(true)
      setAudioBlob(null)
      setElapsed(0)

      // 경과 시간 업데이트
      intervalRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000))
      }, 200)
    } catch (err) {
      console.error('녹음 시작 실패:', err)
      alert('마이크 권한을 허용해주세요.')
    }
  }, [])

  const stop = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsRecording(false)
  }, [])

  const reset = useCallback(() => {
    setAudioBlob(null)
    setElapsed(0)
  }, [])

  // 언마운트 시 정리
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop())
      }
    }
  }, [])

  return { isRecording, audioBlob, elapsed, start, stop, reset }
}
