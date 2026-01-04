import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/contacts.readonly'
]

class CalendarService:
    def __init__(self, credentials_path="credentials.json", token_path="token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None
        self.service = None
        self.people_service = None # For Contacts

    def authenticate(self):
        """Authenticates with Google Calendar API."""
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    self.creds = None
            
            if not self.creds:
                if not os.path.exists(self.credentials_path):
                    return False, "credentials.json 파일이 없습니다. Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 다운로드해서 프로젝트 루트에 넣어주세요."
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES)
                    # Use a fixed port to avoid callback issues if possible, or let it dynamic
                    self.creds = flow.run_local_server(port=0)
                    
                    # Save the credentials for the next run
                    with open(self.token_path, 'w') as token:
                        token.write(self.creds.to_json())
                except Exception as e:
                    return False, f"인증 실패: {e}"

        try:
            self.service = build('calendar', 'v3', credentials=self.creds)
            self.people_service = build('people', 'v1', credentials=self.creds)
            return True, "인증 성공 (Calendar + People)"
        except Exception as e:
            return False, f"서비스 생성 실패: {e}"

    def get_upcoming_events(self, max_results=10):
        """Fetches upcoming events from the user's primary calendar."""
        if not self.service:
            success, msg = self.authenticate()
            if not success:
                return {"error": msg}

        try:
            now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            # 1. Get list of all calendars
            calendar_list_result = self.service.calendarList().list().execute()
            calendars = calendar_list_result.get('items', [])
            
            all_events = []
            now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time

            # 2. Fetch events from each calendar
            for calendar_entry in calendars:
                cal_id = calendar_entry['id']
                cal_summary = calendar_entry.get('summary', 'Unknown')
                
                # Skip some heavy or irrelevant calendars if needed (optional)
                # For now, we try to fetch from all to include KakaoTalk etc.
                try:
                    events_result = self.service.events().list(
                        calendarId=cal_id, timeMin=now,
                        maxResults=max_results, singleEvents=True,
                        orderBy='startTime').execute()
                    
                    items = events_result.get('items', [])
                    for item in items:
                        # Inject calendar name for context
                        item['calendar_name'] = cal_summary 
                        all_events.append(item)
                except Exception as e:
                    print(f"Skipping calendar {cal_summary} ({cal_id}): {e}")
                    continue

            # 3. Sort all events by start time
            # Key: Start time can be dateTime or date
            all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))

            # 4. Slice to max_results
            final_events = all_events[:max_results]

            formatted_events = []
            for event in final_events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                summary = event.get('summary', '제목 없음')
                cal_name = event.get('calendar_name', '')
                
                # Append calendar name to summary if it's not the primary one to help distinguish
                # But user just wanted "included", maybe just list them all.
                # Let's append [CalendarName] if it's not too long, or just let users see the list.
                
                formatted_events.append({
                    "summary": f"[{cal_name}] {summary}" if cal_name else summary,
                    "start": start,
                    "description": event.get('description', ''),
                    "id": event['id'],
                    "attendees": event.get('attendees', [])
                })
            return {"events": formatted_events}
            
            
        except Exception as e:
            return {"error": f"이벤트 조회 실패: {str(e)}"}

    def upload_to_drive(self, filename, content, mimetype="text/markdown"):
        """Uploads content as a file to Google Drive and returns file ID and WebLink."""
        if not self.service:
            self.authenticate()

        try:
            # Build Drive service
            drive_service = build('drive', 'v3', credentials=self.creds)

            file_metadata = {
                'name': filename,
                'mimeType': 'application/vnd.google-apps.document' # Save as Google Doc
            }
            
            # Create media from string content
            import io
            from googleapiclient.http import MediaIoBaseUpload
            
            # Simple text content
            media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype=mimetype, resumable=True)

            print(f"Uploading {filename} to Drive...")
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            print(f"File ID: {file.get('id')}")
            return file.get('id'), file.get('webViewLink')

        except Exception as e:
            print(f"Drive upload failed: {e}")
            return None, None

    def attach_to_calendar_event(self, event_id, file_id, file_link, file_title):
        """Attaches a Drive file to an existing Calendar event."""
        if not self.service:
            self.authenticate()

        try:
            # 1. Fetch existing event to preserve data
            event = self.service.events().get(calendarId='primary', eventId=event_id).execute()
            
            # 2. Prepare attachment
            attachment = {
                'fileUrl': file_link,
                'mimeType': 'application/vnd.google-apps.document',
                'title': file_title,
                'fileId': file_id,
                'iconLink': '' # Optional
            }
            
            # 3. Append to existing attachments or create new list
            attachments = event.get('attachments', [])
            attachments.append(attachment)
            
            event_patch = {
                'attachments': attachments
            }
            
            # 4. Update event
            updated_event = self.service.events().patch(
                calendarId='primary',
                eventId=event_id,
                body=event_patch,
                supportsAttachments=True
            ).execute()
            
            print(f"Event updated with attachment: {updated_event.get('htmlLink')}")
            return True, updated_event.get('htmlLink')

        except Exception as e:
            return False, str(e)

    def search_contacts(self, query):
        """Search google contacts with name query."""
        if not self.people_service:
            try: self.authenticate()
            except: pass
        
        if not self.people_service: return []
        
        try:
            results = self.people_service.people().searchContacts(
                query=query,
                readMask='names,emailAddresses,organizations',
                pageSize=10
            ).execute()
            
            contacts = []
            if 'results' in results:
                for item in results['results']:
                    person = item.get('person', {})
                    
                    names = person.get('names', [])
                    display_name = names[0].get('displayName') if names else "No Name"
                    
                    emails = person.get('emailAddresses', [])
                    email = emails[0].get('value') if emails else ""
                    
                    orgs = person.get('organizations', [])
                    org_info = ""
                    if orgs:
                        org = orgs[0]
                        parts = [p for p in [org.get('name'), org.get('department'), org.get('title')] if p]
                        if parts: org_info = f" ({', '.join(parts)})"
                            
                    full_str = f"{display_name}{org_info}"
                    if email: full_str += f" <{email}>"
                    contacts.append(full_str)
            return contacts
        except Exception as e:
            print(f"Contact search failed: {e}")
            return []

if __name__ == '__main__':
    # Test execution
    cal = CalendarService()
    result = cal.get_upcoming_events()
    print(result)
