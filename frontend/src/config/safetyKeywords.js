// 위험 키워드 - 클라이언트 측 1차 감지 (백엔드에서 정밀 판별 별도)
// 감지되면 일반 검증 화면 대신 SafetyAlertScreen으로 분기

export const SAFETY_KEYWORDS = [
  // 객혈 관련
  { keyword: '객혈', category: 'hemoptysis', severity: 'high' },
  { keyword: '각혈', category: 'hemoptysis', severity: 'high' },
  { keyword: '피가 섞', category: 'hemoptysis', severity: 'high' },
  { keyword: '피가 나', category: 'hemoptysis', severity: 'high' },
  { keyword: '피를 토', category: 'hemoptysis', severity: 'high' },
  { keyword: '토혈', category: 'hematemesis', severity: 'high' },

  // 심한 호흡곤란
  { keyword: '숨을 못 쉬', category: 'dyspnea', severity: 'high' },
  { keyword: '숨이 막', category: 'dyspnea', severity: 'high' },
  { keyword: '말을 못 하', category: 'dyspnea', severity: 'high' },
  { keyword: '숨이 차서', category: 'dyspnea', severity: 'medium' },

  // 의식 / 신경학적
  { keyword: '쓰러졌', category: 'consciousness', severity: 'high' },
  { keyword: '기절', category: 'consciousness', severity: 'high' },
  { keyword: '의식', category: 'consciousness', severity: 'high' },

  // 흉통 (심혈관)
  { keyword: '가슴이 너무 아', category: 'chest_pain', severity: 'high' },
  { keyword: '심장이 조여', category: 'chest_pain', severity: 'high' }
]

/**
 * 텍스트에서 위험 키워드를 찾아 반환
 * @param {string} text - 전사 텍스트
 * @returns {{keyword, category, severity, position} | null}
 */
export function detectSafetyKeyword(text) {
  if (!text) return null
  for (const item of SAFETY_KEYWORDS) {
    const idx = text.indexOf(item.keyword)
    if (idx >= 0) {
      return { ...item, position: idx }
    }
  }
  return null
}
