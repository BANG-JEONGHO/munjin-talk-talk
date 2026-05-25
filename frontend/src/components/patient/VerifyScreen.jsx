import ScreenHeader from '../tablet/ScreenHeader.jsx'

// v4 변경:
// - "최종 전사 문장" → "제가 이렇게 들었어요" 라벨로 (제목과 통합)
// - 초록 박스 (문장 구조 확인 / 원문 보존 / 위험 표현 없음) 전부 제거
// - 글자 크기 키움
// - "확정한 문장만 의사에게 전달돼요" 제거
// - onRetry 시 부모에서 VOICE 화면 복귀 + 자동 녹음 재시작 처리

export default function VerifyScreen({
  patient,
  visitType,
  question,
  transcript,
  stepIndex,
  onConfirm,
  onRetry,
  onStaffCall
}) {
  return (
    <>
      <ScreenHeader
        patientName={`${patient.name} ${patient.honorific}`}
        subtitle={`${question.id} 답변 확인 중`}
        visitType={visitType}
        currentStep={stepIndex}
      />

      <div className="screen-body verify-body verify-body-v4">
        <h2 className="verify-title verify-title-large">제가 이렇게 들었어요</h2>
        <p className="verify-help verify-help-large">
          맞으면 "맞아요"를 눌러주세요.<br/>
          잘못 들었으면 다시 말씀해 주실 수 있어요.
        </p>

        {/* 전사 결과 박스 — "최종 전사 문장" 라벨 제거 */}
        <div className="transcript-box transcript-box-v4">
          <div className="transcript-text transcript-text-large">{transcript}</div>
        </div>

        {/* 초록 chips 박스 v4에서 제거됨 */}

        <div className="verify-actions verify-actions-v4">
          <button className="retry retry-v4" onClick={onRetry}>다시 말할게요</button>
          <button className="confirm confirm-v4" onClick={onConfirm}>맞아요 · 다음</button>
        </div>
      </div>

      <div className="screen-footer">
        <button className="btn-help staff-button-wide" onClick={onStaffCall}>직원 도움</button>
        {/* "확정한 문장만 의사에게 전달돼요" 제거 */}
      </div>
    </>
  )
}
