import { useState, useEffect } from 'react'
import ScreenHeader from '../tablet/ScreenHeader.jsx'

// v4 변경:
// - 모든 글자 크기 키움
// - 대기 순번: 시연용으로 sessionStorage 기반 카운터 사용 (실서비스는 HIS 연동)

const CheckCircleIcon = () => (
  <svg viewBox="0 0 64 64" fill="none">
    <circle cx="32" cy="32" r="30" fill="#2563EB"/>
    <path d="M20 33l8 8 16-18" stroke="white" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)


// 대기 순번 시뮬레이션
// 시연 환경에서는 0~24시간 내 같은 브라우저에서 누적 카운터 사용
function useQueueNumber() {
  const [number, setNumber] = useState(null)

  useEffect(() => {
    try {
      const today = new Date().toISOString().slice(0, 10)  // YYYY-MM-DD
      const stored = JSON.parse(sessionStorage.getItem('munjin_queue') || '{}')

      if (stored.date !== today) {
        // 새 날 → 카운터 초기화. 시연용으로 1~5 사이 랜덤 시작
        const start = Math.floor(Math.random() * 5) + 1
        sessionStorage.setItem('munjin_queue', JSON.stringify({
          date: today,
          counter: start
        }))
        setNumber(start)
      } else {
        // 같은 날 → 카운터 +1
        const next = (stored.counter || 0) + 1
        sessionStorage.setItem('munjin_queue', JSON.stringify({
          date: today,
          counter: next
        }))
        setNumber(next)
      }
    } catch (e) {
      // sessionStorage 사용 불가 시 fallback
      setNumber(Math.floor(Math.random() * 5) + 1)
    }
  }, [])

  return number
}


export default function DoneScreen({ patient, visitType }) {
  const queueNumber = useQueueNumber()

  return (
    <>
      <ScreenHeader
        patientName={`${patient.name} ${patient.honorific}`}
        subtitle={`${visitType === 'initial' ? '초진' : '재진'} 문진 완료`}
        visitType={visitType}
        currentStep={5}
      />

      <div className="screen-body done-body done-body-v4">
        <div className="done-check-icon-large">
          <CheckCircleIcon />
        </div>

        <h2 className="done-title done-title-large">
          문진이<br/>모두 끝났어요
        </h2>

        <p className="done-message done-message-large">
          선생님이 어르신 말씀을 미리 보고 계세요.<br/>
          잠시만 자리에서 기다려 주세요.
        </p>

        <div className="queue-card queue-card-v4">
          <span className="queue-label queue-label-large">대기 순번</span>
          <span className="queue-number queue-number-large">
            {queueNumber !== null ? queueNumber : '—'}
            <small>번</small>
          </span>
        </div>
      </div>
    </>
  )
}
