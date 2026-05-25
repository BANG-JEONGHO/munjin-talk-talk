import { useEffect, useState } from 'react'
import ScreenHeader from '../tablet/ScreenHeader.jsx'

// 직원 도움 호출 후 표시되는 안내 화면
// 모든 문진 화면에서 "직원 도움" 버튼 클릭 시 이 화면으로 전환
//
// 이전 화면 복귀를 위해 onReturn(이전 step) 처리

export default function StaffCallScreen({ patient, onReturn, returnLabel = '문진으로 돌아가기' }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setElapsed(s => s + 1), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <>
      <ScreenHeader
        patientName={patient.name + ' 어르신'}
        subtitle="직원에게 알림 전송됨"
        showVisitTag={false}
      />

      <main className="screen-main staff-call-main">
        <div className="staff-call-icon-wrap">
          <div className="staff-call-icon">
            <svg viewBox="0 0 64 64" fill="none">
              <circle cx="32" cy="32" r="30" fill="#2563EB"/>
              {/* 종 본체 — Lucide bell 스타일 */}
              <path
                d="M32 18a9 9 0 0 0-9 9c0 9-4 12-4 12h26s-4-3-4-12a9 9 0 0 0-9-9z"
                stroke="white"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
              {/* 종 추 (clapper) */}
              <path
                d="M28 43a4 4 0 0 0 8 0"
                stroke="white"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
          </div>
          <div className="staff-call-pulse"></div>
        </div>

        <h2 className="staff-call-title">직원에게 알림이 갔어요!</h2>
        <p className="staff-call-message">
          곧 직원이 도와드리러 옵니다.<br/>
          잠시만 자리에서 기다려 주세요.
        </p>

        <div className="staff-call-status">
          <div className="staff-call-dot"></div>
          <span>알림 전송됨 · 응답 1분 이내</span>
        </div>

        <div className="staff-call-elapsed">
          호출 후 경과: {Math.floor(elapsed / 60)}분 {elapsed % 60}초
        </div>
      </main>

      <footer className="screen-footer">
        <button
          type="button"
          className="btn-primary staff-call-return"
          onClick={onReturn}
        >
          {returnLabel}
        </button>
      </footer>
    </>
  )
}
