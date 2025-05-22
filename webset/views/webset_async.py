import json

from asgiref.sync import async_to_sync
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import APIRequestResponse, WebhookData, WebsetUserMapping
from ..services.websetService import WebsetAsyncService
from ..tasks import create_webset_task


class AsyncWebsetCreateView(APIView):
    def post(self, request):
        try:
            # Extract query from request data
            query = request.data.get('query')

            if not query:
                return Response({
                    'error': 'Query is required'
                     }
                    , status=status.HTTP_400_BAD_REQUEST
                )

            # Store the API request
            api_request_response = APIRequestResponse.objects.create(
                request_method='POST',
                request_path = request.path,
                request_body = json.dumps(request.data),
                status = 'PENDING',
                user = request.user,
            )

            webset = create_webset_task.delay(query, api_request_response.request_id)
            api_request_response.task_id = webset.id
            api_request_response.save()

            #Create initial webhook data
            WebhookData.objects.create(
                request_id = api_request_response.request_id,
                event = 'webset.created',
                status = 'initiated',
                payload =json.dumps({
                    'task_id': webset.id,
                    'status': 'webset.create.initiated',
                    'query': query
                })
            )

            return Response({
                'message': 'Webset creation initiated',
                'request_id': api_request_response.request_id
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class AsyncConcurrentWebsetCreateView(APIView):
    def post(self, request):
        try:
            query = request.data.get('query')
            if not query:
                return Response({
                    'error': 'Query is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            webset_service = WebsetAsyncService()
            result = async_to_sync(webset_service.create_webset_async)(query)

            return Response({
                'message': 'Webset creation initiated',
                'request_id': result['request_id']
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from webset.models import APIRequestResponse

class GetRequestStatusView(APIView):
    """
    Retrieve the status of a request in the `APIRequestResponse` table using `task_id` or `request_id`.
    """

    def get(self, request):
        try:
            # Get query parameters for task_id or request_id
            request_id = request.query_params.get('request_id')
            task_id = request.query_params.get('task_id')

            # Validate input parameters
            if not request_id and not task_id:
                return Response({
                    'success': False,
                    'error': 'Either request_id or task_id must be provided.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Fetch the record based on provided identifier
            query_filter = {'request_id': request_id} if request_id else {'task_id': task_id}
            request_record = APIRequestResponse.objects.filter(**query_filter).first()

            if not request_record:
                return Response({
                    'success': False,
                    'message': 'No record found for the provided identifier.'
                }, status=status.HTTP_404_NOT_FOUND)

            # Prepare response data
            response_data = {
                'request_id': str(request_record.request_id),
                'task_id': request_record.task_id,
                'status': request_record.status,
                'request_body': request_record.request_body,
                'response_body': request_record.response_body,
                'error_message': request_record.error_message,
                'created_at': request_record.created_at,
                'updated_at': request_record.updated_at,
            }

            return Response({
                'success': True,
                'data': response_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'error': f'An error occurred while retrieving the request status: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)