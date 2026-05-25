import ScreenHeader from '../tablet/ScreenHeader.jsx'

// v4 변경:
// - 모든 글자 크기 키움
// - 맨 아래 긴 안내문 축약하여 환자 안심 메시지로

const AlertIcon = () => (
  <svg viewBox="0 0 64 64" fill="none">
    <circle cx="32" cy="32" r="30" fill="#F97316"/>
    <path d="M32 18v18M32 44v3" stroke="white" strokeWidth="4" strokeLinecap="round"/>
  </svg>
)

export default function SafetyAlertScreen({
  patient,
  visitType,
  matchedKeyword,    // "피가 살짝" 같은 환자 발화 인용
  stepIndex
}) {
  return (
    <>
      <ScreenHeader
        patientName={`${patient.name} ${patient.honorific}`}
        subtitle="직원에게 알림 전송됨"
        visitType={visitType}
        currentStep={stepIndex}
      />

      <div className="screen-body safety-body safety-body-v4">
        <div className="safety-icon-wrap">
          <AlertIcon />
        </div>

        <h2 className="safety-title safety-title-large">
          잠시만 기다려주세요
        </h2>

        <p className="safety-message safety-message-large">
          접수 직원이 곧 도와드리러 옵니다.
        </p>

        {matchedKeyword && (
          <div className="safety-quote-box safety-quote-box-v4">
            <div className="safety-quote-label">들은 내용</div>
            <div className="safety-quote-text">"{matchedKeyword}"</div>
          </div>
        )}

        {/* 축약된 안심 메시지 */}
        <div className="safety-reassure safety-reassure-v4">
          걱정 마세요. 자주 있는 일입니다.<br/>
          정확한 확인을 위해 잠시 멈춘 거예요.
        </div>
      </div>

      <div className="screen-footer">
        <div className="safety-status safety-status-v4">
          <div className="safety-status-dot"></div>
          <span>직원 호출 신호 전송됨 · 응답 1분 이내</span>
        </div>
      </div>
    </>
  )
}
