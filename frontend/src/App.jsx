import { useState } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import PatientFlow from './components/patient/PatientFlow.jsx'
import DoctorView from './components/doctor/DoctorView.jsx'
import PatientGuideScreen from './components/patient/PatientGuideScreen.jsx'

// v4 변경:
// - 우측 상단에 시연용 Flag 메뉴 (드롭다운)
// - 초진/재진/위험 분기 강제 트리거 시연 가능
// - 환자 화면(/)에서만 표시

export default function App() {
  return (
    <>
      <nav className="mode-switcher">
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
          환자 화면 (태블릿)
        </NavLink>
        <NavLink to="/doctor" className={({ isActive }) => (isActive ? 'active' : '')}>
          의사 원페이퍼 (PC)
        </NavLink>
        <NavLink to="/guide" className={({ isActive }) => (isActive ? 'active' : '')}>
          환자 안내문 (태블릿)
        </NavLink>
      </nav>

      <main className="app-stage">
        <Routes>
          <Route path="/" element={<PatientFlowWithDemoMenu />} />
          <Route path="/doctor" element={<DoctorView />} />
          <Route path="/doctor/:sessionId" element={<DoctorView />} />
          <Route path="/guide" element={<PatientGuideScreen />} />
          <Route path="/guide/:sessionId" element={<PatientGuideScreen />} />
        </Routes>
      </main>
    </>
  )
}


// 환자 화면에 시연 메뉴를 감싸는 래퍼
function PatientFlowWithDemoMenu() {
  const [demoConfig, setDemoConfig] = useState({
    visitType: null,           // null=시작화면부터, 'initial'/'followup'
    forceFlagAtQ: null         // null/'Q1'/'Q2'/'Q3'
  })
  const [key, setKey] = useState(0)  // 시나리오 변경 시 PatientFlow 강제 리마운트

  const handleScenario = (visitType, forceFlagAtQ) => {
    setDemoConfig({ visitType, forceFlagAtQ })
    setKey(k => k + 1)
  }

  return (
    <>
      <DemoMenu onScenario={handleScenario} current={demoConfig} />
      <PatientFlow
        key={key}
        initialVisitType={demoConfig.visitType}
        forceFlagAtQ={demoConfig.forceFlagAtQ}
      />
    </>
  )
}


function DemoMenu({ onScenario, current }) {
  const [open, setOpen] = useState(false)

  const scenarios = [
    { label: '처음부터 시작', visitType: null, force: null },
    { label: '초진 — 정상',   visitType: 'initial', force: null },
    { label: '재진 — 정상',   visitType: 'followup', force: null },
    { label: '재진 — 객혈 분기 (Q3에서 위험 발생)', visitType: 'followup', force: 'Q3' },
  ]

  return (
    <div className="demo-menu">
      <button
        type="button"
        className="demo-menu-trigger"
        onClick={() => setOpen(o => !o)}
      >
        🎬 시연 시나리오 ▾
      </button>
      {open && (
        <div className="demo-menu-dropdown">
          <div className="demo-menu-header">시연 케이스 선택</div>
          {scenarios.map((s, i) => (
            <button
              key={i}
              type="button"
              className="demo-menu-item"
              onClick={() => {
                onScenario(s.visitType, s.force)
                setOpen(false)
              }}
            >
              {s.label}
            </button>
          ))}
          <div className="demo-menu-note">
            ※ 시연용 메뉴. 실 운영에서는 제거됨.
          </div>
        </div>
      )}
    </div>
  )
}
