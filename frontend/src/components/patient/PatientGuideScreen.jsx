import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getPatientGuide } from '../../services/api.js'
import TabletFrame from '../tablet/TabletFrame.jsx'
import './PatientGuideScreen.css'

// 환자 안내 화면 (Phase B - 진료 후 태블릿).
// 의사 답변을 LLM이 어르신 친화적 문장으로 변환한 결과를 큰 글씨로 표시.
// TTS 음성 안내, 보호자 공유(SMS), 종이 출력 옵션 제공.

const MOCK_GUIDE = {
  patient_name_masked: '김*자',
  patient_guide: {
    generated_at: new Date().toISOString(),
    items: [
      {
        question: '혈압약이랑 감기약 같이 먹어도 되는지',
        answer_simple: [
          '혈압약은 평소처럼 계속 드세요.',
          '일반 감기약은 5일까지 같이 드셔도 괜찮아요.',
          '약 사실 때 약사님께 "혈압약 먹는데 같이 먹을 수 있는 거 주세요"라고 꼭 말씀하세요.'
        ],
        tts_emphasis_words: ['혈압약', '5일', '약사님']
      },
      {
        question: '양파즙도 같이 먹어도 되는지',
        answer_simple: [
          '양파즙은 약이랑 같이 드셔도 됩니다.',
          '다만 하루에 한 잔 정도만 드시는 게 좋아요.'
        ],
        tts_emphasis_words: ['하루 한 잔']
      }
    ]
  },
  doctor_additional_notes: '5일 후 다시 한 번 들러주세요. 호전 없으면 X-ray 검토.'
}

export default function PatientGuideScreen() {
  const { sessionId } = useParams()
  const [guide, setGuide] = useState(MOCK_GUIDE)
  const [playingIdx, setPlayingIdx] = useState(null)  // 현재 재생 중 인덱스

  useEffect(() => {
    if (!sessionId) return
    getPatientGuide(sessionId).then(data => {
      if (data) setGuide(data)
    })
  }, [sessionId])

  // 컴포넌트 언마운트 시 정지
  useEffect(() => {
    return () => {
      if ('speechSynthesis' in window) speechSynthesis.cancel()
    }
  }, [])

  // v4: 토글 동작 — 같은 항목 다시 누르면 멈춤
  const handlePlayToggle = (idx) => {
    if (!('speechSynthesis' in window)) {
      alert('이 브라우저는 음성 안내를 지원하지 않습니다.')
      return
    }

    // 이미 재생 중 → 정지
    if (playingIdx === idx) {
      speechSynthesis.cancel()
      setPlayingIdx(null)
      return
    }

    // 다른 항목 재생 중이면 먼저 정지
    speechSynthesis.cancel()

    const item = guide.patient_guide.items[idx]
    const fullText = item.answer_simple.join('. ')
    const utter = new SpeechSynthesisUtterance(fullText)
    utter.lang = 'ko-KR'
    utter.rate = 0.85
    utter.pitch = 1.0

    // 재생 종료 시 상태 초기화
    utter.onend = () => setPlayingIdx(null)
    utter.onerror = () => setPlayingIdx(null)

    setPlayingIdx(idx)
    speechSynthesis.speak(utter)
  }

  const handleShareSMS = () => {
    // 실제 구현 시 보호자 전화번호 입력 모달 → AWS SNS 호출
    alert('보호자 휴대폰으로 안내문이 전송되었습니다. (시연 mock)')
  }

  const handlePrint = () => {
    window.print()
  }

  const items = guide?.patient_guide?.items || []

  return (
    <TabletFrame visitType="guide">
      <div className="patient-guide-screen">
        <header className="pg-header">
          <h1>{guide.patient_name_masked || '환자'} 어르신,</h1>
          <h1>진료가 끝났습니다</h1>
          <p className="pg-sub">선생님께서 이렇게 말씀하셨어요</p>
        </header>

        <div className="pg-items">
          {items.length === 0 && (
            <div className="pg-empty">
              안내문이 아직 준비되지 않았습니다.<br />
              잠시만 기다려 주세요.
            </div>
          )}

          {items.map((item, idx) => (
            <article
              key={idx}
              className={`pg-card ${playingIdx === idx ? 'pg-card-active' : ''}`}
            >
              <div className="pg-question-tag">{item.question}</div>

              <div className="pg-sentences">
                {item.answer_simple.map((sentence, sidx) => (
                  <p key={sidx} className="pg-sentence">
                    {sentence}
                  </p>
                ))}
              </div>

              <button
                className={`pg-tts-btn ${playingIdx === idx ? 'playing' : ''}`}
                onClick={() => handlePlayToggle(idx)}
              >
                <span className="pg-tts-icon">{playingIdx === idx ? '⏸' : '🔊'}</span>
                {playingIdx === idx ? '재생 멈추기' : '말로 재생하기'}
              </button>
            </article>
          ))}
        </div>

        {guide.doctor_additional_notes && (
          <div className="pg-notes-box">
            <span className="pg-notes-label">진료 안내</span>
            <p>{guide.doctor_additional_notes}</p>
          </div>
        )}

        <div className="pg-action-bar">
          <button className="pg-action-btn pg-action-share" onClick={handleShareSMS}>
            <span>💬</span> 가족에게 보내기
          </button>
          <button className="pg-action-btn pg-action-print" onClick={handlePrint}>
            <span>📄</span> 종이로 출력
          </button>
        </div>

        <footer className="pg-footer">
          궁금한 점이 더 있으시면 접수처 직원에게 말씀해 주세요.
        </footer>
      </div>
    </TabletFrame>
  )
}
