from gtts import gTTS
import os
import time

def create_sample_meeting_audio():
    # 시나리오: 개발팀 주간 회의 (약 40~50초 분량)
    # gTTS는 기본적으로 같은 목소리이므로, 문맥으로 화자를 구분하도록 대본을 구성함.
    script = [
        "지금부터 1월 1주차 개발팀 주간 회의를 시작하겠습니다. 김민수 팀장입니다. 각 파트별 진행 상황 공유 부탁드립니다.",
        "네, 백엔드 파트 박지성입니다. 현재 API 서버 성능 최적화 작업 중이며, 응답 속도가 30% 개선되었습니다. 특히 데이터베이스 쿼리 튜닝 효과가 컸습니다.",
        "프론트엔드 파트 최유리입니다. 새로운 대시보드 UI 디자인 적용이 완료되었고, 사용자 피드백을 반영하여 버튼 위치를 일부 수정했습니다. 다음 주 월요일 정기 배포 예정입니다.",
        "알겠습니다. 박지성 님, 서버 비용 절감 이슈는 어떻게 되었나요?",
        "네, 말씀하신 대로 불필요한 로그 저장을 줄여서 스토리지 비용을 약 15% 절감했습니다.",
        "좋습니다. 최유리 님도 배포 전 크로스 브라우징 테스트 꼼꼼히 부탁드립니다. 이상으로 회의를 마치겠습니다."
    ]

    full_text = " ... ".join(script)
    
    # 한국어 음성 생성
    print("Generating audio via Google TTS...")
    tts = gTTS(text=full_text, lang='ko')
    
    filename = "sample_meeting.mp3"
    save_path = os.path.join(os.getcwd(), filename)
    
    tts.save(save_path)
    print(f"Sample audio created at: {save_path}")

if __name__ == "__main__":
    create_sample_meeting_audio()
