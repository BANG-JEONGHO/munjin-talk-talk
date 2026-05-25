import { useState, useCallback, useEffect } from 'react'
import TabletFrame from '../tablet/TabletFrame.jsx'
import VisitTypeScreen from './VisitTypeScreen.jsx'
import VoiceScreen from './VoiceScreen.jsx'
import VerifyScreen from './VerifyScreen.jsx'
import SafetyAlertScreen from './SafetyAlertScreen.jsx'
import StaffCallScreen from './StaffCallScreen.jsx'
import DoneScreen from './DoneScreen.jsx'
import { QUESTIONS } from '../../config/questions.js'
import { detectSafetyKeyword } from '../../config/safetyKeywords.js'
import { uploadAudio, getTranscript, processTranscript, createSession } from '../../services/api.js'

// v4 변경:
// - STAFF_CALL 단계 추가 (직원 도움 호출 후 안내 화면)
// - "다시 말할게요" 시 voice 화면 복귀 + 자동 녹음 재시작 (VoiceScreen이 useEffect로 자동 시작)
// - forceFlagAtQ prop 추가 — 시연 메뉴에서 특정 Q에서 flag 강제 트리거
// - 직원 도움 핸들러 모든 화면에 전달

const MOCK_PATIENT = {
  name: '김*자',
  honorific: '어르신',
  age: 74,
  gender: '여성',
  receiptId: 'A-0427'
}

const STEPS = {
  VISIT_TYPE: 'visit_type',
  Q_VOICE: 'q_voice',
  Q_VERIFY: 'q_verify',
  SAFETY_ALERT: 'safety_alert',
  STAFF_CALL: 'staff_call',
  DONE: 'done'
}


export default function PatientFlow({ initialVisitType = null, forceFlagAtQ = null }) {
  const [step, setStep] = useState(initialVisitType ? STEPS.Q_VOICE : STEPS.VISIT_TYPE)
  const [visitType, setVisitType] = useState(initialVisitType)
  const [questionIndex, setQuestionIndex] = useState(0)
  const [transcript, setTranscript] = useState('')
  const [safetyKeyword, setSafetyKeyword] = useState(null)
  const [answers, setAnswers] = useState([])
  const [session] = useState(() => createSession())
  const [prevStep, setPrevStep] = useState(null)  // 직원 도움 복귀용

  const questions = visitType ? QUESTIONS[visitType] : []
  const currentQuestion = questions[questionIndex]


  // 직원 도움 호출 — 모든 화면에서 사용
  const handleStaffCall = useCallback(() => {
    setPrevStep(step)
    setStep(STEPS.STAFF_CALL)
  }, [step])

  // 직원 도움 화면에서 복귀
  const handleStaffCallReturn = useCallback(() => {
    setStep(prevStep || STEPS.VISIT_TYPE)
    setPrevStep(null)
  }, [prevStep])


  const handleVisitTypeConfirm = useCallback((path) => {
    setVisitType(path)
    setStep(STEPS.Q_VOICE)
    setQuestionIndex(0)
  }, [])


  const handleVoiceFinish = useCallback(async (audioBlob) => {
    try {
      const { transcribeJobName } = await uploadAudio(
        audioBlob,
        session.sessionId,
        currentQuestion.id,
        visitType
      )

      // forceFlagAtQ가 설정되면 해당 Q에서 위험 발화로 mock 교체 (시연용)
      let mockJobName = `${visitType ? 'mock' : transcribeJobName}-${currentQuestion.id}_${visitType}`
      if (forceFlagAtQ && currentQuestion.id === forceFlagAtQ) {
        mockJobName = `mock-flag-trigger-${currentQuestion.id}`
      }

      const { transcript: stt } = await getTranscript(mockJobName)
      setTranscript(stt)

      // 클라이언트 1차 위험 키워드 검사
      const safety = detectSafetyKeyword(stt)
      if (safety && safety.severity === 'high') {
        setSafetyKeyword(safety)
        setStep(STEPS.SAFETY_ALERT)
        return
      }

      setStep(STEPS.Q_VERIFY)
    } catch (err) {
      console.error('STT 실패:', err)
      setTranscript('네트워크 오류 - 다시 말씀해 주세요')
      setStep(STEPS.Q_VERIFY)
    }
  }, [session.sessionId, currentQuestion, visitType, forceFlagAtQ])


  const handleVerifyConfirm = useCallback(async () => {
    try {
      const result = await processTranscript({
        sessionId: session.sessionId,
        questionId: currentQuestion.id,
        questionType: currentQuestion.question_type,
        visitType,
        transcript
      })

      if (result.safety_flag && result.safety_flag.severity === 'high') {
        setSafetyKeyword(result.safety_flag)
        setStep(STEPS.SAFETY_ALERT)
        return
      }

      setAnswers([...answers, {
        id: currentQuestion.id,
        transcript,
        question_type: currentQuestion.question_type,
        result
      }])
      setTranscript('')

      if (questionIndex >= 3) {
        setStep(STEPS.DONE)
      } else {
        setQuestionIndex(questionIndex + 1)
        setStep(STEPS.Q_VOICE)
      }
    } catch (err) {
      console.error('process 실패:', err)
      setTranscript('')
      if (questionIndex >= 3) {
        setStep(STEPS.DONE)
      } else {
        setQuestionIndex(questionIndex + 1)
        setStep(STEPS.Q_VOICE)
      }
    }
  }, [answers, currentQuestion, transcript, questionIndex, session.sessionId, visitType])


  const handleVerifyRetry = useCallback(() => {
    setTranscript('')
    setStep(STEPS.Q_VOICE)
    // VoiceScreen이 useEffect로 자동 녹음 재시작
  }, [])


  const renderScreen = () => {
    switch (step) {
      case STEPS.VISIT_TYPE:
        return (
          <VisitTypeScreen
            patient={MOCK_PATIENT}
            onConfirm={handleVisitTypeConfirm}
            onStaffCall={handleStaffCall}
          />
        )

      case STEPS.Q_VOICE:
        return (
          <VoiceScreen
            patient={MOCK_PATIENT}
            visitType={visitType}
            question={currentQuestion}
            stepIndex={questionIndex + 1}
            onFinish={handleVoiceFinish}
            onStaffCall={handleStaffCall}
          />
        )

      case STEPS.Q_VERIFY:
        return (
          <VerifyScreen
            patient={MOCK_PATIENT}
            visitType={visitType}
            question={currentQuestion}
            transcript={transcript}
            stepIndex={questionIndex + 1}
            onConfirm={handleVerifyConfirm}
            onRetry={handleVerifyRetry}
            onStaffCall={handleStaffCall}
          />
        )

      case STEPS.SAFETY_ALERT:
        return (
          <SafetyAlertScreen
            patient={MOCK_PATIENT}
            visitType={visitType}
            matchedKeyword={safetyKeyword?.matched_pattern || safetyKeyword?.label || transcript}
            stepIndex={questionIndex + 1}
          />
        )

      case STEPS.STAFF_CALL:
        return (
          <StaffCallScreen
            patient={MOCK_PATIENT}
            onReturn={handleStaffCallReturn}
            returnLabel={prevStep === STEPS.VISIT_TYPE ? '진료 화면으로 돌아가기' : '문진 계속하기'}
          />
        )

      case STEPS.DONE:
        return (
          <DoneScreen
            patient={MOCK_PATIENT}
            visitType={visitType}
          />
        )

      default:
        return null
    }
  }

  return (
    <TabletFrame visitType={visitType}>
      {renderScreen()}
    </TabletFrame>
  )
}
