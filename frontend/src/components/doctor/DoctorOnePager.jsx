import { useState, useEffect, useMemo } from 'react'
import { getOnePager } from '../../services/api.js'
import './DoctorOnePager.css'

// v4 변경:
// - "진단명 추천 없음" / "검증 완료" 자잘한 chips 제거
// - 의료진 확인 항목 체크박스 실제 작동 (클릭 시 체크 + 파란 테두리)
// - 재진의 변화 추적 카드를 "오늘 말한 불편함" 디자인으로 변경
//   (EMR 연동 안 되므로 이전 진료 추적 불가, 환자가 새로 말한 증상 그대로 표시)
// - 좌우 패널 길이 차이로 무너지지 않도록 균형 조정
// - "위험 — 우선 평가 필요" amber 배지는 유지 (재진 객혈 시연용)

const CopyIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <rect x="8" y="8" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="2"/>
    <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" stroke="currentColor" strokeWidth="2"/>
  </svg>
)

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <path d="M5 12l5 5L20 7" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

// Mock — 초진
const MOCK_INITIAL = {
  patient: {
    name: '김*자', age: 74, gender: '여성', department: '이비인후과',
    visit_type: 'initial', receivedAt: '10:30', audioDuration: 58
  },
  agenda: [
    { type: 'drug_drug_interaction', type_label: '복약 상호작용',
      summary: '혈압약-감기약 병용 가능 여부 문의',
      original_quote: '혈압약이랑 감기약을 같이 먹어도 되는지 궁금해요' },
    { type: 'food_drug_interaction', type_label: '음식-약 상호작용',
      summary: '양파즙 병용 가능 여부 문의',
      original_quote: '양파즙도 같이 먹어도 되나요' }
  ],
  full_q4_transcript: '혈압약이랑 감기약을 같이 먹어도 되는지 궁금해요. 양파즙도 같이 먹어도 되나요?',
  symptomSlots: [
    { name: '목 불편감', sub: '인후 자극', sourceQuote: '목이 칼칼하고', score: 0.91 },
    { name: '코막힘', sub: '비폐색', sourceQuote: '코가 맥혀요 (사투리 자동 매칭)', score: 0.88 },
    { name: '기침', sub: 'cough', sourceQuote: '기침도 조금 나요', score: 0.84 }
  ],
  reviewItems: [
    '발열 여부와 실제 체온 확인',
    '가래 동반 여부와 색깔',
    '혈압약 ↔ 일반 감기약 병용 가능 여부 안내',
    '양파즙 병용 가능 여부 답변',
    '흡연력 및 알레르기 이력 (음성에서 미수집)'
  ],
  transferText: '74세 여성 환자. 어제부터 목 불편감과 코막힘 호소. 발열은 없다고 말함. 혈압약 복용 중 감기약 병용 가능 여부 문의.',
  safety_flag: null
}

// Mock — 재진 (위험 분기 시연용)
// v4: 변화 추적 카드 대신 "오늘 말한 불편함"으로 통일 (EMR 미연동)
const MOCK_FOLLOWUP = {
  patient: {
    name: '김*자', age: 74, gender: '여성', department: '이비인후과',
    visit_type: 'followup', receivedAt: '11:15', audioDuration: 42
  },
  agenda: [
    { type: 'treatment_duration', type_label: '복약 기간',
      summary: '복약 기간 문의',
      original_quote: '이 약을 언제까지 먹어야 되나요' }
  ],
  full_q4_transcript: '이 약을 언제까지 먹어야 되나요?',
  uncategorized_remnant: '',
  symptomSlots: [
    { name: '기침', sub: 'cough · 악화', sourceQuote: '기침이 더 심해졌고', score: 0.89 },
    { name: '객혈', sub: 'hemoptysis · 신규 ⚠', sourceQuote: '어제는 피가 살짝 묻어 나왔어요', score: 0.93, alert: true },
  ],
  reviewItems: [
    '[우선] 객혈 평가 (X-ray·객담 검사 고려)',
    '[우선] 객혈량과 시작 시점 확인',
    '기침 악화 패턴 평가',
    '복약 순응도 (저녁 누락) 영향 평가',
    '흡연력 재확인'
  ],
  transferText: '재진 환자. 환자 호소: 기침 악화 + 객혈 신규 발생 ("피가 살짝 묻어 나왔다"). 환자 미해결 질문: 복약 기간 문의.',
  safety_flag: {
    category: 'hemoptysis', label: '객혈 의증',
    severity: 'high', matched_pattern: '피가 살짝'
  }
}


export default function DoctorOnePager({ sessionId, sessionData, sidePanel, renderAgenda = true }) {
  const [apiData, setApiData] = useState(null)
  const [copied, setCopied] = useState(false)
  const [mockOverride, setMockOverride] = useState(null)
  const [checked, setChecked] = useState({})  // {0: true, 2: true} 형태

  useEffect(() => {
    if (sessionData || !sessionId) return
    getOnePager(sessionId).then(setApiData)
  }, [sessionId, sessionData])

  const data = useMemo(() => {
    if (sessionData) return _normalize(sessionData)
    if (apiData) return _normalize(apiData)
    return mockOverride === 'followup' ? MOCK_FOLLOWUP : MOCK_INITIAL
  }, [sessionData, apiData, mockOverride])

  // mock 변경 시 체크 초기화
  useEffect(() => {
    setChecked({})
  }, [mockOverride])

  const isFollowup = data.patient.visit_type === 'followup'
  const themeClass = isFollowup ? 'theme-followup' : 'theme-initial'

  const handleCopy = () => {
    navigator.clipboard?.writeText(data.transferText)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const toggleCheck = (idx) => {
    setChecked(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  return (
    <div className={`onepaper-v4 ${themeClass}`}>

      {/* 데모용 토글 (실시연 시 제거) */}
      {!sessionData && !apiData && (
        <div className="onepaper-demo-toggle">
          <button
            className={!mockOverride || mockOverride === 'initial' ? 'active' : ''}
            onClick={() => setMockOverride('initial')}
          >Mock: 초진</button>
          <button
            className={mockOverride === 'followup' ? 'active' : ''}
            onClick={() => setMockOverride('followup')}
          >Mock: 재진 (위험 분기)</button>
        </div>
      )}

      {/* 위험 플래그 */}
      {data.safety_flag && data.safety_flag.severity === 'high' && (
        <div className="op-safety-alert">
          <span className="osa-icon">⚠</span>
          <div>
            <b>{data.safety_flag.label} — 우선 평가 필요</b>
            <p>감지: "{data.safety_flag.matched_pattern}" ({data.safety_flag.category})</p>
          </div>
        </div>
      )}

      {/* 환자 정보 바 — "진단명 추천 없음" / "검증 완료" 제거 */}
      <div className="op-patient-bar">
        <div className="op-patient-info">
          <h4>
            {data.patient.name} · {data.patient.age}세 {data.patient.gender} · {data.patient.department}
          </h4>
          <p>
            <span className={`op-visit-badge ${data.patient.visit_type}`}>
              {isFollowup ? '재진' : '초진'}
            </span>
            <span>접수 {data.patient.receivedAt}</span>
            <span className="op-dot" />
            <span>음성 {data.patient.audioDuration}초</span>
          </p>
        </div>
        {/* "진단명 추천 없음" / "검증 완료" chips 제거됨 */}
      </div>

      {/* 좌우 분할 */}
      <div className="op-split">

        {/* 좌측 3카드 */}
        <div className="op-left">

          {/* 카드 1: 환자가 말한 불편함 — 초진/재진 동일 디자인 */}
          <section className="op-card symptom-card">
            <div className="op-card-title">
              <h4>{isFollowup ? '오늘 말한 불편함' : '오늘 말한 불편함'}</h4>
              <span className={`op-chip ${isFollowup ? 'teal' : 'blue'}`}>
                {isFollowup ? '재진' : '초진'}
              </span>
            </div>
            <div className="slot-rows">
              {data.symptomSlots?.map((slot, i) => (
                <div key={i} className={`slot-row ${slot.alert ? 'slot-row-alert' : ''}`}>
                  <div className="slot-name">
                    {slot.name} <small>({slot.sub})</small>
                  </div>
                  <div className={`slot-score ${slot.alert ? 'slot-score-alert' : ''}`}>
                    {slot.score.toFixed(2)}
                  </div>
                  <div className="slot-quote">"{slot.sourceQuote}"</div>
                </div>
              ))}
            </div>
          </section>

          {/* 카드 2: 의료진 확인 항목 — 체크박스 실제 작동 */}
          <section className="op-card review-card">
            <div className="op-card-title">
              <h4>{isFollowup ? '재진 확인 항목' : '의료진 확인 항목'}</h4>
              <span className="op-chip gray">체크용</span>
            </div>
            <ul className="check-list-v4">
              {data.reviewItems.map((item, i) => {
                const isPriority = item.startsWith('[우선]')
                const isChecked = !!checked[i]
                return (
                  <li
                    key={i}
                    className={[
                      'check-item-v4',
                      isPriority && 'check-priority',
                      isChecked && 'check-checked'
                    ].filter(Boolean).join(' ')}
                    onClick={() => toggleCheck(i)}
                  >
                    <span className={`check-box-v4 ${isChecked ? 'checked' : ''}`}>
                      {isChecked && <CheckIcon />}
                    </span>
                    <span className="check-text-v4">{item}</span>
                  </li>
                )
              })}
            </ul>
          </section>

          {/* 카드 3: 기록용 문장 */}
          <section className="op-card transfer-card">
            <div className="op-card-title">
              <h4>기록용 문장</h4>
              <span className="op-chip teal">EMR 복사</span>
            </div>
            <p className="transfer-text">{data.transferText}</p>
            <button className="copy-btn" onClick={handleCopy}>
              <CopyIcon />
              {copied ? '복사됨!' : 'EMR로 복사'}
            </button>
          </section>
        </div>

        {/* 우측 패널 */}
        <aside className="op-right">
          {sidePanel}
        </aside>
      </div>
    </div>
  )
}


// API 응답 정규화 (v4: 변화 추적 → 증상 카드로 통일)
function _normalize(raw) {
  if (!raw || raw.patient === undefined) return raw

  const visit_type = raw.visit_type || 'initial'
  const normalized = {
    patient: {
      name: raw.patient.name_masked || raw.patient.name || '환자',
      age: raw.patient.age || 0,
      gender: raw.patient.gender || '-',
      department: raw.patient.department || '이비인후과',
      visit_type,
      receivedAt: raw.patient.received_at || '--:--',
      audioDuration: raw.patient.audio_duration || 0,
    },
    agenda: (raw.agenda || []).map(q => ({
      type: q.category,
      type_label: _categoryToKorean(q.category),
      summary: q.summary,
      original_quote: q.original_quote,
    })),
    full_q4_transcript: raw.full_q4_transcript || '',
    uncategorized_remnant: raw.uncategorized_remnant || '',
    reviewItems: raw.review_items || [],
    transferText: raw.transfer_text || '',
    safety_flag: raw.safety_flag,
    symptomSlots: []
  }

  // v4: symptom_list / progress_tracking 둘 다 symptomSlots로 통일
  if (raw.symptom_card?.type === 'symptom_list') {
    normalized.symptomSlots = (raw.symptom_card.slots || []).map(s => ({
      name: s.name,
      sub: s.slot_id,
      sourceQuote: s.source_quote,
      score: s.score || 0,
    }))
  } else if (raw.symptom_card?.type === 'progress_tracking') {
    // 재진도 환자가 새로 말한 증상으로 표시
    const spans = raw.symptom_card.spans || []
    normalized.symptomSlots = spans.map(span => ({
      name: _slotIdToKorean(span.slot_ref),
      sub: span.slot_ref,
      sourceQuote: span.source_quote,
      score: span.score || 1.0,
      alert: span.type === 'new_symptom' || span.slot_ref === 'hemoptysis'
    }))
  }

  return normalized
}

function _categoryToKorean(cat) {
  const m = {
    drug_drug_interaction: '복약 상호작용',
    food_drug_interaction: '음식-약 상호작용',
    treatment_duration: '복약 기간',
    prognosis: '예후·회복',
    general_health_info: '건강정보',
    prognosis_concern: '심각성 우려',
    other: '기타'
  }
  return m[cat] || '환자 질문'
}

function _slotIdToKorean(id) {
  const m = {
    cough: '기침', throat_irritation: '목 불편감', nasal_obstruction: '코막힘',
    rhinorrhea: '콧물', fever: '열', sputum: '가래', dyspnea: '호흡곤란',
    hemoptysis: '객혈', chest_pain: '흉통', wheezing: '천명음', headache: '두통',
    sneezing: '재채기', voice_change: '음성 변화', sore_throat: '인후통'
  }
  return m[id] || id
}
