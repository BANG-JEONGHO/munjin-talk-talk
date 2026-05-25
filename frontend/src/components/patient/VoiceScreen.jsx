import { useEffect } from 'react'
import ScreenHeader from '../tablet/ScreenHeader.jsx'
import { useAudioRecorder } from '../../hooks/useAudioRecorder.js'

// Q1~Q4 공통 음성 입력 화면
// 같은 컴포넌트에 props만 다르게 들어와서 4번 재사용됨

const MicIcon = () => (
  <svg viewBox="0 0 24 24" fill="none">
    <rect x="9" y="3" width="6" height="14" rx="3" fill="currentColor"/>
    <path d="M5 11a7 7 0 0 0 14 0M12 18v4M9 22h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
  </svg>
)

function formatTime(seconds) {
  const m = String(Math.floor(seconds / 60)).padStart(2, '0')
  const s = String(seconds % 60).padStart(2, '0')
  return `${m}:${s}`
}

export default function VoiceScreen({
  patient,
  visitType,
  question,
  stepIndex,
  partialText,
  onFinish,
  onStaffCall
}) {
  const { isRecording, audioBlob, elapsed, start, stop } = useAudioRecorder()

  // v4: 화면 진입 시 자동 녹음 시작
  useEffect(() => {
    const t = setTimeout(() => start(), 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.id])

  // 녹음 완료되면 부모에게 Blob 전달
  useEffect(() => {
    if (audioBlob && !isRecording) {
      onFinish(audioBlob)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioBlob, isRecording])

  const handleMicClick = () => {
    if (isRecording) stop()
    else start()
  }

  const handleEnd = () => {
    if (isRecording) stop()
  }

  return (
    <>
      <ScreenHeader
        patientName={`${patient.name} ${patient.honorific}`}
        subtitle={`${visitType === 'initial' ? '초진' : '재진'} · ${question.id}번 질문`}
        visitType={visitType}
        currentStep={stepIndex}
      />

      <div className="screen-body voice-body">
        <span className="voice-badge">{question.badge}</span>
        <h2 className="voice-question" style={{ whiteSpace: 'pre-line' }}>
          {question.title}
        </h2>
        <p className="voice-sub" style={{ whiteSpace: 'pre-line' }}>
          {question.sub}
        </p>
        <div className="voice-example">
          <b>예시</b>{question.example}
        </div>

        <div className="voice-mic-wrap">
          <button
            className={`voice-mic ${isRecording ? 'recording' : ''}`}
            onClick={handleMicClick}
            aria-label={isRecording ? '녹음 중지' : '녹음 시작'}
          >
            <MicIcon />
          </button>
          {isRecording && (
            <div className="voice-wave">
              <i /><i /><i /><i /><i /><i /><i /><i /><i />
            </div>
          )}
          <div className="voice-timer">
            {formatTime(elapsed)} <span>/ 01:00</span>
          </div>
        </div>

        {partialText && (
          <div className="voice-partial">
            <div className="voice-partial-label">실시간 자막</div>
            <div className="voice-partial-text">"{partialText}…"</div>
          </div>
        )}
      </div>

      <div className="screen-footer">
        <button className="btn-help staff-button-wide" onClick={onStaffCall}>직원 도움</button>
        <button className="btn-primary" onClick={handleEnd}>
          발화 마치기
        </button>
      </div>
    </>
  )
}
