// 초진과 재진의 4문항 정의. 흐름 단계의 진실의 원천(single source of truth).
//
// 각 질문의 question_type은 백엔드 extract Lambda에 전달되어
// LLM 프롬프트 분기에 사용됨 (옵션 C 하이브리드 전략):
//   - chief_complaint / progress       → Claude Span Extract
//   - onset / adherence                → 규칙 기반 (LLM 호출 없음)
//   - current_medications / new_symptoms → Claude Entity Extract
//   - patient_questions / unresolved_questions → Claude Categorizer

export const QUESTIONS = {
  initial: [
    {
      id: 'Q1',
      badge: 'Q1 · 주호소',
      title: '어디가 불편하셔서\n오셨어요?',
      sub: '증상을 한두 문장으로 짧게\n말씀해 주시면 됩니다',
      example: '"어제부터 목이 칼칼하고 코가 막혀요."',
      question_type: 'chief_complaint',
      processing: 'llm_with_match'  // Claude + Titan
    },
    {
      id: 'Q2',
      badge: 'Q2 · 시작 시점',
      title: '그 증상은 언제부터\n그러셨어요?',
      sub: '날짜가 명확하지 않으셔도\n"며칠 전부터" 정도로 괜찮아요',
      example: '"그저께 저녁부터요."',
      question_type: 'onset',
      processing: 'rule_based'  // LLM 호출 없음
    },
    {
      id: 'Q3',
      badge: 'Q3 · 기저 복약',
      title: '지금 드시는 약이\n있으세요?',
      sub: '매일 드시는 약, 영양제, 한약 등\n전부 말씀해 주시면 좋아요',
      example: '"혈압약을 매일 아침에 먹어요."',
      question_type: 'current_medications',
      processing: 'llm_only'  // Claude만 (벡터 매칭 없음)
    },
    {
      id: 'Q4',
      badge: 'Q4 · 환자 질문',
      title: '의사선생님께\n묻고 싶은 점이 있으세요?',
      sub: '복약 · 음식 · 검사 · 생활 무엇이든\n편하게 말씀해 주세요',
      example: '"양파즙도 같이 먹어도 되나요?"',
      question_type: 'patient_questions',
      processing: 'llm_only'  // Claude Categorizer만
    }
  ],
  followup: [
    {
      id: 'Q1',
      badge: 'Q1 · 경과',
      title: '지난번 진료 이후\n어떻게 지내셨어요?',
      sub: '좋아졌는지, 그대로인지, 더 심해졌는지\n편하게 말씀해 주세요',
      example: '"약 먹고 목은 좀 나아졌어요."',
      question_type: 'progress',
      processing: 'llm_with_match'
    },
    {
      id: 'Q2',
      badge: 'Q2 · 복약 순응도',
      title: '처방받은 약은\n잘 드시고 계세요?',
      sub: '빠뜨리고 못 드신 날, 부작용, 효과 등을\n편하게 말씀해 주세요',
      example: '"잘 먹었는데 한 번씩 깜빡했어요."',
      question_type: 'adherence',
      processing: 'rule_based'
    },
    {
      id: 'Q3',
      badge: 'Q3 · 새 증상',
      title: '그동안 새로 생긴\n증상은 없으세요?',
      sub: '사소해 보이는 변화도 말씀해 주세요\n없으시면 "없어요"라고만 하셔도 돼요',
      example: '"기침이 더 심해졌어요."',
      question_type: 'new_symptoms',
      processing: 'llm_with_match'
    },
    {
      id: 'Q4',
      badge: 'Q4 · 추가 질문',
      title: '지난번에 못 여쭤본\n점이 있으신가요?',
      sub: '"없어요"라고 하셔도 돼요\n생각나는 게 있으면 짧게 말씀해 주세요',
      example: '"이 약을 언제까지 먹어야 되나요?"',
      question_type: 'unresolved_questions',
      processing: 'llm_only'
    }
  ]
}

export const FLOW_STEPS = [
  'visit_type',  // 0: 초진/재진 선택
  'q1',          // 1: Q1 음성
  'q1_verify',   // 2: Q1 검증
  'q2',          // 3
  'q2_verify',   // 4
  'q3',          // 5
  'q3_verify',   // 6
  'q4',          // 7
  'q4_verify',   // 8
  'done'         // 9
]

// 진행 바에 표시할 그룹 (6세그먼트: 접수 + Q1~Q4 + 완료)
export const PROGRESS_SEGMENTS = 6
