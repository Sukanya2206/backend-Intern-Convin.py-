import os

from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.urls import reverse
from django.views import View
from google.oauth2.credentials import Credentials
from google.auth.transport import requests as google_requests
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build


def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }


class GoogleCalendarInitView(View):
    def get(self, request):
        flow = Flow.from_client_secrets_file(
            os.path.join(settings.BASE_DIR, 'path/to/client_secret.json'),
            scopes=['https://www.googleapis.com/auth/calendar'],
            redirect_uri=request.build_absolute_uri(reverse('google_calendar_redirect')),
        )

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent',
        )

        request.session['oauth2_state'] = state
        return HttpResponseRedirect(authorization_url)


class GoogleCalendarRedirectView(View):
    def get(self, request):
        error = request.GET.get('error')
        if error:
            return HttpResponseBadRequest(error)

        oauth2_state = request.session.pop('oauth2_state', None)
        if oauth2_state != request.GET.get('state'):
            return HttpResponseBadRequest('Invalid state parameter')

        flow = Flow.from_client_secrets_file(
            os.path.join(settings.BASE_DIR, 'path/to/client_secret.json'),
            scopes=['https://www.googleapis.com/auth/calendar'],
            redirect_uri=request.build_absolute_uri(reverse('google_calendar_redirect')),
        )

        try:
            flow.fetch_token(authorization_response=request.build_absolute_uri())
        except Exception as e:
            return HttpResponseBadRequest(f"Error getting access token: {e}")

        credentials = flow.credentials
        request.session['oauth2_credentials'] = credentials_to_dict(credentials)

        try:
            service = build('calendar', 'v3', credentials=credentials)
            events_result = service.events().list(calendarId='primary', maxResults=10, singleEvents=True, orderBy='startTime').execute()
            events = events_result.get('items', [])

            if not events:
                return JsonResponse({'message': 'No events found.'})

            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                event_list.append({'summary': event['summary'], 'start': start})

            return JsonResponse({'events': event_list})
        except HttpError as error:
            return HttpResponseBadRequest(f"An error occurred: {error}")