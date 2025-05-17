import os

from dotenv import load_dotenv
from exa_py import Exa
from exa_py.websets.types import CreateWebsetParameters, CreateEnrichmentParameters


load_dotenv()
exa = Exa(os.getenv('EXA_API_KEY'))

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
def create_webset(query):
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

    print(f"Webset created with ID: {webset.id}")

    # Wait until Webset completes processing
    webset = exa.websets.wait_until_idle(webset.id)

    # Retrieve Webset Items
    items = exa.websets.items.list(webset_id=webset.id)
    for item in items.data:
        print(f"Item: {item.model_dump_json(indent=2)}")

    return items.data


def get_webset(webset_id, requested_page_no=1, limit=1):
    paged_webset_items = get_paged_webset(webset_id, requested_page_no,limit)

    if paged_webset_items:
      for item in paged_webset_items.data:
        print(f"Item: {item.model_dump_json(indent=2)}")
      return paged_webset_items.data
    return None
    # Wait until Webset completes processing
    #webset = exa.websets.wait_until_idle(webset.id)

    # # Retrieve Webset Items
    # items = exa.websets.items.list(webset_id=webset_id)
    # # Get page number
    # # import pdb; pdb.set_trace()
    # for item in items.data:
    #     print(f"Item: {item.model_dump_json(indent=2)}")

    # return items.data

def get_paged_webset(webset_id, requested_page_no=1, limit=1):
    webset = exa.websets.get(webset_id)

    current_page = 1
    cursor=None

    while True:
      items = exa.websets.items.list(
        webset_id=webset_id,
          limit=limit,
          cursor=cursor
      )

      cursor = items.next_cursor

      if current_page == requested_page_no:
        return items
      current_page = current_page + 1
    
      if items.next_cursor == None:
         return None
