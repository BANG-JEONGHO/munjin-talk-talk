// 모든 태블릿 화면 상단의 공통 헤더
// - 로고 + 환자 이름/부제
// - 우측 visit 태그 (선택)
// - 진행 바 (6세그먼트)

const LogoSVG = () => (
  <svg className="screen-logo" viewBox="0 0 112 86" fill="none">
    <path d="M12 18C12 10.268 18.268 4 26 4H58C65.732 4 72 10.268 72 18V44C72 51.732 65.732 58 58 58H35L16 76V58H26C18.268 58 12 51.732 12 44V18Z" fill="white" stroke="#0AA7A5" strokeWidth="6" strokeLinejoin="round"/>
    <path d="M43 23V43" stroke="#2563EB" strokeWidth="8" strokeLinecap="round"/>
    <path d="M33 33H53" stroke="#2563EB" strokeWidth="8" strokeLinecap="round"/>
  </svg>
)

export default function ScreenHeader({
  patientName,
  subtitle,
  visitType,
  currentStep = 0,      // 0~5 (접수, Q1~Q4, 완료)
  totalSteps = 6,
  showVisitTag = true
}) {
  const segments = Array.from({ length: totalSteps }, (_, i) => {
    if (i < currentStep) return 'done'
    if (i === currentStep) return 'active'
    return ''
  })

  return (
    <div className="screen-header">
      <div className="screen-header-top">
        <div className="screen-header-left">
          <LogoSVG />
          <div>
            <div className="screen-title">{patientName}</div>
            <div className="screen-sub">{subtitle}</div>
          </div>
        </div>
        {showVisitTag && visitType && (
          <span className={`visit-tag ${visitType}`}>
            {visitType === 'initial' ? '초진' : '재진'}
          </span>
        )}
      </div>
      <div className="progress">
        {segments.map((state, i) => (
          <span key={i} className={`seg ${state}`} />
        ))}
      </div>
    </div>
  )
}
