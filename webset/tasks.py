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
import json

from celery import shared_task
from celery.beat import logger
from celery.contrib.migrate import task_id_eq
from django.core.serializers.json import DjangoJSONEncoder

from webset.models import APIRequestResponse, WebhookData


@shared_task()
def create_webset_task(query,request_id=None):
    from exa_py.websets.types import CreateWebsetParameters, CreateEnrichmentParameters

    from webset.services.websetService import exa
    webset = exa.websets.create(
        params=CreateWebsetParameters(
            search={
                "query": "software developer in delhi who knows python django",
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
    print(f"Created webset: {webset}")  # Add this logging
    # Wait until Webset completes processing
    webset = exa.websets.wait_until_idle(webset.id)
    print(f"Completed webset: {webset}")  # Add this logging


    # prepare response data
    response_data = {
        "webset_id": webset.id,
        "status": "webset.create.completed",
        "data": json.loads(json.dumps(webset.model_dump(), cls=DateTimeEncoder))
    }

    #update API request response
    api_request = APIRequestResponse.objects.filter(request_id=request_id).first()


    APIRequestResponse.objects.filter(request_id=request_id).update(
        response_body=response_data,
        status='webset.created.completed'
    )

    # create webhook data for completion
    WebhookData.objects.create(
        request_id=api_request.request_id,
        event="webset.created",
        status="webset.created.completed",
        payload=json.dumps(response_data),
    )


    # Retrieve Webset Items
    items = exa.websets.items.list(webset_id=webset.id)
    for item in items.data:
        print(f"Item: {item.model_dump_json(indent=2)}")
    print(f"Completed items: {items}")  # Add this logging



# First, convert the webset object to a dict with datetime handling
class DateTimeEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super().default(obj)
