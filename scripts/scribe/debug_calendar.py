
import os
import json
from auth_calendar import CalendarService

def debug_calendar_events():
    cal = CalendarService()
    # 캘린더 서비스 초기화 (토큰 갱신 등)
    if not cal.service:
        cal.authenticate()
        
    print("Fetching calendar events...")
    
    # 1. 모든 캘린더 목록 가져오기
    calendar_list_result = cal.service.calendarList().list().execute()
    calendars = calendar_list_result.get('items', [])
    
    print(f"Found {len(calendars)} calendars.")
    
    target_keywords = ["카카오", "Kakao", "생일", "휴일"] # 제외할 키워드나 식별 키워드
    
    for calendar_entry in calendars:
        cal_summary = calendar_entry.get('summary', 'Unknown')
        cal_id = calendar_entry['id']
        
        print(f"\nScanning Calendar: {cal_summary} ({cal_id})")
        
        try:
            # 최근/미래 일정 5개만 조회
            events_result = cal.service.events().list(
                calendarId=cal_id,
                maxResults=5,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            items = events_result.get('items', [])
            if not items:
                print("  - No upcoming events.")
                continue
                
            for event in items:
                summary = event.get('summary', 'No Title')
                desc = event.get('description', 'No Description')
                attendees = event.get('attendees', [])
                organizer = event.get('organizer', {})
                
                print(f"  [Event] {summary}")
                print(f"    - Description (First 100 chars): {desc[:100]}...")
                print(f"    - Attendees Raw: {attendees}")
                print(f"    - Organizer: {organizer}")
                
                # 전체 필드 덤프 (혹시 다른 곳에 정보가 있는지 확인)
                # print(json.dumps(event, indent=2, ensure_ascii=False))
                
        except Exception as e:
            print(f"  - Error fetching events: {e}")

if __name__ == "__main__":
    debug_calendar_events()
