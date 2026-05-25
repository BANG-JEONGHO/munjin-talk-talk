// 세로 태블릿 외곽 프레임 (검은 베젤 + 상단 스피커 + 하단 홈 표시)
// children은 .tablet-screen 내부에 들어감

export default function TabletFrame({ children, visitType }) {
  // visitType에 따라 'initial' 또는 'followup' CSS 클래스로 색상 테마 적용
  const themeClass = visitType ? visitType : 'initial'

  return (
    <div className="tablet-frame">
      <div className={`tablet-screen ${themeClass}`}>
        {children}
      </div>
    </div>
  )
}
