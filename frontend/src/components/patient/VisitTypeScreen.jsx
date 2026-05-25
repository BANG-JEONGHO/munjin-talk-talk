import { useState, useEffect } from 'react'
import ScreenHeader from '../tablet/ScreenHeader.jsx'

// v5 변경 (v3 디자인 복구):
// - v3의 vt-* 클래스 그대로 유지 (디자인 망가지지 않게)
// - 실시간 시계만 추가 (useLiveClock)
// - "선택하신 내용에 따라..." 안내문 제거 (vt-help 제거)
// - "오늘 진료가 처음이신가요?" 글자 크기 키움 (CSS override)
// - 직원 도움 버튼 폭 키움 (staff-button-wide)
// - 직원 도움 클릭 시 onStaffCall 호출

const SparkleIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2.5l2.4 7.1L21.5 12l-7.1 2.4L12 21.5l-2.4-7.1L2.5 12l7.1-2.4L12 2.5z"/>
    <path d="M5 3.5v3M3.5 5h3M19 17.5v3M17.5 19h3"/>
  </svg>
)
const HistoryIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
    <path d="M3 3v5h5"/>
    <path d="M12 8v4l3 2"/>
  </svg>
)
const ChevronRight = () => (
  <svg viewBox="0 0 24 24" fill="none">
    <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)


// 실시간 시계 훅
function useLiveClock() {
  const [time, setTime] = useState(() => formatTime(new Date()))
  useEffect(() => {
    const id = setInterval(() => setTime(formatTime(new Date())), 30 * 1000)
    return () => clearInterval(id)
  }, [])
  return time
}

function formatTime(date) {
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}


export default function VisitTypeScreen({ patient, onConfirm, onStaffCall }) {
  const [selected, setSelected] = useState(null)
  const clock = useLiveClock()

  const handleSelect = (path, e) => {
    setSelected(path)

    // 리플 이펙트
    const button = e.currentTarget
    const rect = button.getBoundingClientRect()
    const ripple = document.createElement('span')
    ripple.className = 'ripple'
    ripple.style.left = (e.clientX - rect.left) + 'px'
    ripple.style.top = (e.clientY - rect.top) + 'px'
    button.appendChild(ripple)
    setTimeout(() => ripple.remove(), 700)
  }

  const handleStart = () => {
    if (!selected) return
    onConfirm(selected)
  }

  return (
    <>
      <ScreenHeader
        patientName="문진톡톡 · 접수"
        subtitle={`이비인후과 · 오늘 ${clock}`}
        currentStep={0}
        showVisitTag={false}
      />

      <div className="screen-body">
        <div className="vt-patient">
          <div className="vt-avatar" />
          <div>
            <div className="vt-name">{patient.name}</div>
            <div className="vt-meta">{patient.age}세 {patient.gender} · #{patient.receiptId}</div>
          </div>
        </div>

        {/* v5: 글자 크기 키움 (vt-question-large 클래스) */}
        <h2 className="vt-question vt-question-large">오늘 진료가 처음이신가요?</h2>

        {/* v5: "선택하신 내용에 따라..." 안내문 제거됨 */}

        <div className="vt-btns">
          <button
            className={`vt-btn ${selected === 'initial' ? 'selected' : ''} ${selected === 'followup' ? 'dimmed' : ''}`}
            data-path="initial"
            onClick={(e) => handleSelect('initial', e)}
          >
            <div className="vt-btn-icon"><SparkleIcon /></div>
            <div className="vt-btn-text">
              <div className="vt-btn-title">처음 왔어요</div>
              <div className="vt-btn-sub">오늘이 첫 진료입니다 · 초진</div>
            </div>
            <div className="vt-btn-arrow"><ChevronRight /></div>
          </button>

          <button
            className={`vt-btn ${selected === 'followup' ? 'selected' : ''} ${selected === 'initial' ? 'dimmed' : ''}`}
            data-path="followup"
            onClick={(e) => handleSelect('followup', e)}
          >
            <div className="vt-btn-icon"><HistoryIcon /></div>
            <div className="vt-btn-text">
              <div className="vt-btn-title">전에 왔었어요</div>
              <div className="vt-btn-sub">이전 진료 기록이 있어요 · 재진</div>
            </div>
            <div className="vt-btn-arrow"><ChevronRight /></div>
          </button>
        </div>
      </div>

      <div className="screen-footer">
        {/* v5: 직원 도움 버튼 폭 키움 + onStaffCall 핸들러 */}
        <button className="btn-help staff-button-wide" onClick={onStaffCall}>직원 도움</button>
        <button
          className={`vt-start ${selected ? 'enabled' : ''}`}
          data-path={selected || ''}
          onClick={handleStart}
          disabled={!selected}
        >
          {selected
            ? `${selected === 'initial' ? '초진' : '재진'} 문진 시작하기 →`
            : '먼저 위에서 한 가지 골라주세요'}
        </button>
      </div>
    </>
  )
}
