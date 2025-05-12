import json
import requests
from dotenv import load_dotenv
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.core.serializers.json import DjangoJSONEncoder
from webset.services import websetService, openAIService
from webset.services.websetService import WebsetAsyncService
from webset.utils import convert_string_to_json
from webset.constants.api_constants import (
    EXA_WEBSETS_UPDATE_URL,
    EXA_WEBSETS_LIST_URL
)
from webset.utils import get_exa_api_headers
from webset.utils import get_webset_update_payload
from webset.models import APIRequestResponse
from webset.services.websetService import WebsetItemService

load_dotenv()

"""
# Create a Webset with search and enrichments
"""
class CreateWebsetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            result = websetService.create_webset(request.data,request.user)
            return Response({
                'request_id': result['request_id'],
                'message': 'Webset creation initiated',
                'data': result['data']
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetWebsetView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, webset_id):
        result = websetService.get_webset(webset_id)
        if result:
            response = {
                "success": True,
                "message": "Webset retrieved successfully",
                "data": json.loads(result[0].model_dump_json())
            }
            return JsonResponse(response, status=200)
        else:
            response = {
                "success": False,
                "message": "Webset retrieval failed",
                "data": []
            }
            return JsonResponse(response, status=400)


class UpdateWebsetsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, webset_id):
        try:
            # Get request data
            request_data = convert_string_to_json(request.body)
            if not request_data:
                return JsonResponse({
                    "success": False,
                    "message": "Request body cannot be empty",
                    "data": []
                }, status=400)

            # Prepare the API call
            url = EXA_WEBSETS_UPDATE_URL.format(webset_id=webset_id)
            payload = get_webset_update_payload(request_data.get('metadata'))
            headers = get_exa_api_headers()

            # Make the API call
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                # Get the updated webset data
                if response.text:
                    response_data = {
                        "success": True,
                        "message": "Webset metadata updated successfully",
                        "data": json.loads( response.text)
                    }
                    return JsonResponse(response_data, status=200)
                else:
                    return JsonResponse({
                        "success": False,
                        "message": "Failed to retrieve updated webset",
                        "data": []
                    }, status=400)
            else:
                return JsonResponse({
                    "success": False,
                    "message": f"Failed to update webset metadata: {response.text}",
                    "data": []
                }, status=response.status_code)

        except Exception as e:
            return JsonResponse({
                "success": False,
                "message": f"An error occurred: {str(e)}",
                "data": []
            }, status=500)


class GenerateSearchCriteriaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            request_data = convert_string_to_json(request.body)
            if not request_data:
                raise ValidationError("Empty request body")
            
            query = request_data.get('query')
            if not query:
                return JsonResponse({
                    "success": False,
                    "message": "Query parameter is required",
                    "error": "MISSING_QUERY"
                }, status=400)
            
            result = openAIService.generate_search_criteria(query)
            
            if result.get("success"):
                return JsonResponse({
                    "success": True,
                    "message": result["message"]
                }, status=200)
            else:
                return JsonResponse({
                    "success": False,
                    "message": result.get("message", "Search criteria generation failed"),
                    "error": result.get("error", "UNKNOWN_ERROR")
                }, status=400)
                
        except Exception as e:
            return JsonResponse({
                "success": False,
                "message": "An unexpected error occurred",
                "error": str(e)
            }, status=500)


class ListWebsetsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Get pagination parameters with defaults
            cursor = request.query_params.get('cursor', '1')
            limit = int(request.query_params.get('limit', 25))
            
            # Validate limit range
            if not (1 <= limit <= 100):
                return JsonResponse({
                    "success": False,
                    "message": "Limit must be between 1 and 100",
                    "data": []
                }, status=400)
            
            # Make the API call to list websets with pagination
            response = requests.get(
                EXA_WEBSETS_LIST_URL,
                headers=get_exa_api_headers(),
                params={
                    'cursor': cursor,
                    'limit': limit
                }
            )
            
            if response.status_code == 200:
                response_data = {
                    "success": True,
                    "message": "Websets retrieved successfully",
                    "data": response.json(),
                    "pagination": {
                        "cursor": cursor,
                        "limit": limit
                    }
                }
                return JsonResponse(response_data, status=200)
            else:
                return JsonResponse({
                    "success": False,
                    "message": f"Failed to retrieve websets: {response.text}",
                    "data": []
                }, status=response.status_code)

        except ValueError:
            return JsonResponse({
                "success": False,
                "message": "Invalid limit parameter. Must be a number.",
                "data": []
            }, status=400)
        except Exception as e:
            return JsonResponse({
                "success": False,
                "message": f"An error occurred: {str(e)}",
                "data": []
            }, status=500)


class WebsetRequestStatusView(APIView):
    def get(self, request, request_id):
        try:
            result = WebsetAsyncService.get_creation_status(request_id)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_404_NOT_FOUND)


class GetWebsetItemView(APIView):
    def get(self, request, webset_id, item_id):
        try:
            result = WebsetItemService.get_webset_item(webset_id, item_id,request.user)
            return Response({
                'request_id': result['request_id'],
                'data': result['data']
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ListWebsetItemsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, webset_id):
        try:
            # Get pagination parameters with defaults
            cursor = request.query_params.get('cursor', '1')
            limit = int(request.query_params.get('limit', 25))
            
            result = WebsetItemService.list_webset_items(
                webset_id=webset_id,
                user=request.user,
                cursor=cursor,
                limit=limit
            )
            
            return Response({
                'request_id': result['request_id'],
                'data': result['data'],
                'pagination': result['pagination']
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LatestAPIRequestStatusView(APIView):
    def get(self, request, request_id):
        try:
            # Get the latest record for the given request_id
            latest_request = APIRequestResponse.objects.filter(
                request_id=request_id
            ).order_by('-created_at').first()

            if not latest_request:
                return Response({
                    'error': f'No records found for request_id: {request_id}'
                }, status=status.HTTP_404_NOT_FOUND)

            response_data = {
                'request_id': str(latest_request.request_id),
                'status': latest_request.status,
                'request_body': latest_request.request_body,
                'response_body': latest_request.response_body,
                'error_message': latest_request.error_message,
                'created_at': latest_request.created_at,
                'updated_at': latest_request.updated_at
            }

            return Response(json.loads(
                json.dumps(response_data, cls=DjangoJSONEncoder)
            ), status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Error retrieving request status: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from webset.models import APIRequestResponse
from webset.services.websetService import exa
import json


class ListUserWebsetsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Get the authenticated user
            user = request.user

            # Fetch all APIRequestResponse entries for the user where websets are completed
            user_requests = APIRequestResponse.objects.filter(user=user)

            websets_data = []
            webset_id = None

            # Iterate over each response and fetch data from EXA
            for request_entry in user_requests:
                try:
                    # Extract API response
                    response_body = json.loads(request_entry.response_body)

                    webset_id = response_body['data'][0]['webset_id']

                    # Fetch details of the webset from EXA
                    webset = exa.websets.get(id=webset_id)

                        # Add webset details to the response list
                    websets_data.append(webset.model_dump())
                except Exception as e:
                    # Log and skip webset if fetching fails
                    print(f"Error fetching webset {webset_id}: {str(e)}")
                    continue

            # Return the list of websets
            return Response({
                'success': True,
                'message': 'User websets fetched successfully.',
                'data': websets_data
            }, status=200)

        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=500)
