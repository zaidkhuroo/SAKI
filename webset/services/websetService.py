import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import requests
from asgiref.sync import sync_to_async
from django.core import cache
from django.db import transaction
from dotenv import load_dotenv
from exa_py import Exa
from exa_py.websets.types import CreateWebsetParameters, CreateEnrichmentParameters

from webset.models import APIRequestResponse, WebhookData
import json
from webset.constants.api_constants import  EXA_WEBSETS_ITEMS_URL, EXA_WEBSETS_ITEMS_LIST_URL
from webset.services.enrichmentService import EnrichmentService
from webset.tasks import DateTimeEncoder

load_dotenv()
exa = Exa(os.getenv('EXA_API_KEY'))
import asyncio
import json
from functools import partial
from concurrent.futures import ThreadPoolExecutor

from django.db import transaction
from django.core.cache import cache
from asgiref.sync import sync_to_async


class WebsetAsyncService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.semaphore = asyncio.Semaphore(5)

    async def create_webset_async(self, query):
        request_id = None
        try:
            request_record = await self._create_request_record(query)
            request_id = request_record.request_id

            cache_key = f'webset_creation_{request_id}'
            if cache.get(cache_key):
                return {'request_id': request_id, 'status': 'duplicate_request'}
            cache.set(cache_key, 'processing', timeout=300)

            async with self.semaphore:
                loop = asyncio.get_event_loop()
                webset = await loop.run_in_executor(
                    self.executor,
                    partial(self._create_exa_webset, query)
                )

                request_record = await self._get_request_record_for_update(request_id)
                if not request_record:
                    raise Exception("Request record not found")

                response_data = {
                    "webset_id": webset.id,
                    "status": "completed",
                    "data": json.loads(json.dumps(webset.model_dump(), cls=DateTimeEncoder))
                }

                await self._update_request_record(request_record, response_data)
                await self._create_webhook_data(request_id, webset, response_data)

            cache.delete(cache_key)
            return {'request_id': request_id, 'data': response_data}

        except Exception as e:
            print(f"Error in create_webset_async: {str(e)}")
            if request_id:
                await self._handle_error(request_id, str(e))
                cache.delete(f'webset_creation_{request_id}')
            raise

    async def get_creation_status(self, request_id):
        """Get the status of a webset creation request"""
        try:
            request_record = await APIRequestResponse.objects.aget(request_id=request_id)
            return {
                'request_id': str(request_record.request_id),
                'status': request_record.status,
                'response': request_record.response_body,
                'error': request_record.error_message
            }
        except APIRequestResponse.DoesNotExist:
            raise Exception(f"Request with ID {request_id} not found")

    # ----------------- SYNC WRAPPED METHODS -----------------

    @sync_to_async
    def _create_request_record(self, query):
        with transaction.atomic():
            return APIRequestResponse.objects.create(
                request_method='POST',
                request_path='/api/webset/create',
                request_body=query,
                status='processing'
            )

    @sync_to_async
    def _get_request_record_for_update(self, request_id):
        with transaction.atomic():
            return APIRequestResponse.objects.select_for_update().filter(
                request_id=request_id
            ).first()

    @sync_to_async
    def _update_request_record(self, request_record, response_data):
        with transaction.atomic():
            request_record.response_body = response_data
            request_record.status = 'completed'
            request_record.save()

    @sync_to_async
    def _handle_error(self, request_id, error_message):
        with transaction.atomic():
            record = APIRequestResponse.objects.select_for_update().filter(
                request_id=request_id
            ).first()
            if record:
                record.status = 'failed'
                record.error_message = error_message
                record.save()

    # ----------------- EXA API CALL -----------------

    def _create_exa_webset(self, query):
        webset = exa.websets.create(
            params=CreateWebsetParameters(
                search={
                    "query": query,
                    "count": 5
                },
                enrichments=[
                    CreateEnrichmentParameters(
                        description="LinkedIn profile of VP of Engineering or related role",
                        format="text",
                    ),
                ],
            )
        )
        return exa.websets.wait_until_idle(webset.id)

    # ----------------- ASYNC ORM CREATE -----------------

    @staticmethod
    async def _create_webhook_data(request_id, webset, response_data):
        await WebhookData.objects.acreate(
            request_id=request_id,
            event="webset.created",
            status="completed",
            payload=json.dumps(response_data)
        )


#Response of creating a webset
"""
{
  "id": "<string>",
  "object": "webset",
  "status": "idle",
  "externalId": "<string>",
  "searches": [
    {
      "id": "<string>",
      "object": "webset_search",
      "status": "created",
      "query": "<string>",
      "entity": {
        "type": "company"
      },
      "criteria": [
        {
          "description": "<string>",
          "successRate": 50
        }
      ],
      "count": 2,
      "progress": {
        "found": 123,
        "completion": 50
      },
      "metadata": {},
      "canceledAt": "2023-11-07T05:31:56Z",
      "canceledReason": "webset_deleted",
      "createdAt": "2023-11-07T05:31:56Z",
      "updatedAt": "2023-11-07T05:31:56Z"
    }
  ],
  "enrichments": [
    {
      "id": "<string>",
      "object": "webset_enrichment",
      "status": "pending",
      "websetId": "<string>",
      "title": "<string>",
      "description": "<string>",
      "format": "text",
      "options": [
        {
          "label": "<string>"
        }
      ],
      "instructions": "<string>",
      "metadata": {},
      "createdAt": "2023-11-07T05:31:56Z",
      "updatedAt": "2023-11-07T05:31:56Z"
    }
  ],
  "metadata": {},
  "createdAt": "2023-11-07T05:31:56Z",
  "updatedAt": "2023-11-07T05:31:56Z"
}
"""


# class WebsetAysncService:
#     def __init__(self):
#         self.executor = ThreadPoolExecutor(max_workers=10)  # Adjust based on your needs
#         self.semaphore = asyncio.Semaphore(5)  # Limit concurrent EXA api calls
#
#     async def create_webset_async(self, query):
#         request_id = None
#         try:
#             # Create request record with select_for_update to prevent race conditions
#             with transaction.atomic():
#                 request_record = APIRequestResponse.objects.create(
#                     request_method='POST',
#                     request_path='/api/webset/create',
#                     request_body=query,
#                     status='processing'
#                 )
#                 request_id = request_record.request_id
#
#             # Use cache to prevent duplicate processing
#             cache_key = f'webset_creation_{request_id}'
#             if cache.get(cache_key):
#                 return {'request_id': request_id, 'status': 'duplicate_request'}
#             cache.set(cache_key, 'processing', timeout=300)  # 5 minutes timeout
#
#             async with self.semaphore:  # Limit concurrent API calls
#                 # Execute EXA API call in thread pool
#                 loop = asyncio.get_event_loop()
#                 webset = await loop.run_in_executor(
#                     self.executor,
#                     partial(self._create_exa_webset, query)
#                 )
#
#                 # Update request record atomically
#                 with transaction.atomic():
#                     request_record = await self._get_request_record_for_update(request_id)
#                     if not request_record:
#                         raise Exception("Request record not found")
#
#                     response_data = {
#                         "webset_id": webset.id,
#                         "status": "completed",
#                         "data": json.loads(json.dumps(webset.model_dump(), cls=DateTimeEncoder))
#                     }
#
#                     # Update with select_for_update to prevent race conditions
#                     request_record.response_body = response_data
#                     request_record.status = 'completed'
#                     request_record.save()
#
#                     # Create webhook data
#                     await self._create_webhook_data(request_id, webset, response_data)
#
#                 cache.delete(cache_key)
#                 return {'request_id': request_id, 'data': response_data}
#
#         except Exception as e:
#             print(f"Error in create_webset_async: {str(e)}")
#             if request_id:
#                 await self._handle_error(request_id, str(e))
#             cache.delete(f'webset_creation_{request_id}')
#             raise
#
#
#     @staticmethod
#     @transaction.atomic
#     @sync_to_async
#     def _get_request_record_for_update(request_id):
#         return  APIRequestResponse.objects.select_for_update().filter(
#             request_id=request_id
#         ).first()
#
#     def _create_exa_webset(self, query):
#         """Execute EXA API call in thread pool"""
#         webset = exa.websets.create(
#             params=CreateWebsetParameters(
#                 search={
#                     "query": query,
#                     "count": 5
#                 },
#                 enrichments=[
#                     CreateEnrichmentParameters(
#                         description="LinkedIn profile of VP of Engineering or related role",
#                         format="text",
#                     ),
#                 ],
#             )
#         )
#         return exa.websets.wait_until_idle(webset.id)
#
#     @staticmethod
#     async def _create_webhook_data(request_id, webset, response_data):
#         await WebhookData.objects.acreate(
#             request_id=request_id,
#             event="webset.created",
#             status="completed",
#             payload=json.dumps(response_data)
#         )
#
#
#     @staticmethod
#     async def _handle_error(request_id, error_message):
#         """Handle errors and update request record"""
#         with transaction.atomic():
#             request_record = await APIRequestResponse.objects.select_for_update().filter(
#                 request_id=request_id
#             ).afirst()
#             if request_record:
#                 request_record.status = 'failed'
#                 request_record.error_message = error_message
#                 await request_record.asave()
#
#     async def get_creation_status(self, request_id):
#         """Get the status of a webset creation request"""
#         try:
#             request_record = await APIRequestResponse.objects.aget(request_id=request_id)
#             return {
#                 'request_id': str(request_record.request_id),
#                 'status': request_record.status,
#                 'response': request_record.response_body,
#                 'error': request_record.error_message
#             }
#         except APIRequestResponse.DoesNotExist:
#             raise Exception(f"Request with ID {request_id} not found")


# sycn implementation
def create_webset(request_data,user):
    try:
        # Create a new request record
        request_record = APIRequestResponse.objects.create(
            request_body=request_data,
            user=user
        )

        # Your existing create_webset logic here
        # For example:
        response_data = {
            # ... your existing response data ...
        }
         # create_webset_task.delay(query)
        from exa_py.websets.types import CreateWebsetParameters, CreateEnrichmentParameters

        from webset.services.websetService import exa
        webset = exa.websets.create(
            params=CreateWebsetParameters(
                search={
                    "query": request_data["query"],
                    "count": 5
                },
                enrichments=[
                    CreateEnrichmentParameters(
                        description="LinkedIn profile of VP of Engineering or related role",
                        format="text",
                    ),
                ],
            )
        )

        print(f"Webset created with ID: {webset.id}")

        # Wait until Webset completes processing
        webset = exa.websets.wait_until_idle(webset.id)

        # Retrieve Webset Items
        items = exa.websets.items.list(webset_id=webset.id)
        for item in items.data:
            print(f"Item: {item.model_dump_json(indent=2)}")

        response_data= json.loads(items.model_dump_json())


        # Update the request record with the response
        request_record.response_body = json.dumps(response_data,default=vars)
        request_record.status = 'completed'
        request_record.save()

        # Return response with request_id
        return {
            'request_id': str(request_record.request_id),
            'data': response_data
        }

    except Exception as e:
        # Update request record with error
        if 'request_record' in locals():
            request_record.status = 'failed'
            request_record.error_message = str(e)
            request_record.save()

        raise Exception(f"Error creating webset: {str(e)}")
    # create_webset_task.delay(query)

def get_webset(webset_id):
    webset = exa.websets.get(webset_id)


    # Wait until Webset completes processing
    #webset = exa.websets.wait_until_idle(webset.id)

    # Retrieve Webset Items
    items = exa.websets.items.list(webset_id=webset_id)
    for item in items.data:
        print(f"Item: {item.model_dump_json(indent=2)}")

    return items.data

def update_webset(webset_id):
    try:
        # Get the existing webset
        webset = exa.websets.get(webset_id)
        if not webset:
            return None

        # Update the webset with new parameters
        # Note: The actual update parameters would depend on what you want to update
        # This is a basic example - you might want to add more parameters
        updated_webset = exa.websets.update(
            id=webset_id,
            params={
                "search": {
                    "query": webset.searches[0].query if webset.searches else "",
                    "count": 5
                },
                "enrichments": [
                    {
                        "description": "LinkedIn profile of VP of Engineering or related role",
                        "format": "text",
                    }
                ]
            }
        )

        # Wait until the update is complete
        updated_webset = exa.websets.wait_until_idle(webset_id)

        # Get the updated items
        items = updated_webset.list(webset_id=webset_id)
        return  json.loads(items.model_dump_json())

    except Exception as e:
        print(f"Error updating webset: {str(e)}")
        return None

class WebsetItemService:
    @staticmethod
    def get_webset_item(webset_id, item_id,user):
        request_record={}
        try:
            # Create a new request record
            request_record = APIRequestResponse.objects.create(
                user=user,
                request_body={
                    "webset_id": webset_id,
                    "item_id": item_id
                }
            )
            
            # Make the API request
            url = EXA_WEBSETS_ITEMS_URL.format(webset_id=webset_id, item_id=item_id)
            headers = {"x-api-key": os.getenv('EXA_API_KEY')}
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            response_data = response.json()
            
            # Update the request record with the response
            request_record.response_body = response_data
            request_record.status = 'completed'
            request_record.save()
            
            return {
                'request_id': str(request_record.request_id),
                'data': response_data
            }
            
        except requests.exceptions.RequestException as e:
            # Update request record with error
            if 'request_record' in locals():
                request_record.status = 'failed'
                request_record.error_message = str(e)
                request_record.save()
            
            raise Exception(f"Error fetching webset item: {str(e)}")
        except Exception as e:
            # Update request record with error
            if 'request_record' in locals():
                request_record.status = 'failed'
                request_record.error_message = str(e)
                request_record.save()
            
            raise Exception(f"Error processing webset item request: {str(e)}")


    @staticmethod
    def list_webset_items(webset_id,user, cursor='1', limit="25"):
        request_record ={}
        try:
            # Create a new request record
            request_record = APIRequestResponse.objects.create(
                user=user,
                request_body={
                    "webset_id": webset_id,
                    "cursor": cursor,
                    "limit": limit
                }
            )
            
            # Validate limit range
            if not (1 <= limit <= 100):
                raise ValueError("Limit must be between 1 and 100")
            
            # Make the API request
            url = EXA_WEBSETS_ITEMS_LIST_URL.format(webset_id=webset_id)
            headers = {"x-api-key": os.getenv('EXA_API_KEY')}
            params = {
                'cursor': cursor,
                'limit': "3"
            }
            
            response = requests.get(url, headers=headers)

            response_data = response.json()

            enrichment_id_title_map ={}
            for item in response_data["data"]:
                for enrichment in item["enrichments"]:
                    print(enrichment)
                    id = enrichment["enrichmentId"]
                    if enrichment_id_title_map.get(id) is not None:
                        enrichment["title"] = enrichment_id_title_map[id];
                    else:
                        response = EnrichmentService.get_enrichment( webset_id,id,user)
                        enrichment["title"] = response["data"]["title"]


            
            # Update the request record with the response
            response_data["webset_id"]=webset_id
            request_record.response_body = response_data
            request_record.status = 'completed'
            request_record.save()
            
            return {
                'request_id': str(request_record.request_id),
                'data': response_data,
                'pagination': {
                    'cursor': cursor,
                    'limit': limit
                }
            }
            
        except requests.exceptions.RequestException as e:
            if 'request_record' in locals():
                request_record.status = 'failed'
                request_record.error_message = str(e)
                request_record.save()
            raise Exception(f"Error fetching webset items: {str(e)}")
        except ValueError as e:
            if 'request_record' in locals():
                request_record.status = 'failed'
                request_record.error_message = str(e)
                request_record.save()
            raise e
        except Exception as e:
            if 'request_record' in locals():
                request_record.status = 'failed'
                request_record.error_message = str(e)
                request_record.save()
            raise Exception(f"Error processing webset items request: {str(e)}")