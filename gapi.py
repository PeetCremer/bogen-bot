import asyncio
#import print # noqa has to be imported after asyncio
import os
from dotenv import load_dotenv
import re
import json

from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import ServiceAccountCreds
from aiogoogle.models import HTTPError as AiogoogleHttpError



class SheetNotFoundError(Exception):
    def __init__(self, sheet_title):
        super().__init__(f"Sheet with title '{sheet_title}' not found!")


async def get_ability_value(doc_id, sheet_title, creds, ability_name):
    aiogoogle = Aiogoogle(service_account_creds=creds)
    # Notice this line. Here, Aiogoogle loads the service account key.
    await aiogoogle.service_account_manager.detect_default_creds_source()
    async with aiogoogle:
        sheets_service = await aiogoogle.discover('sheets', 'v4')
        try:
            ability_value = await _search_ability_by_name(aiogoogle, sheets_service, doc_id, sheet_title, ability_name)
            print("VALUE")
            print(ability_value)
        except SheetNotFoundError as e:
            print(e)


# async def _get_doc(aiogoogle, sheets_service, doc_id):       
#     doc_future = await aiogoogle.as_service_account(
#         sheets_service.spreadsheets.get(spreadsheetId=doc_id)
#     )
#     return doc_future


async def _search_ability_by_name(aiogoogle, sheets_service, doc_id, sheet_title, search_name):
    search_name = search_name.lower()
    req = sheets_service.spreadsheets.values.get(spreadsheetId=doc_id, range=sheet_title)
    req.url = f"https://docs.google.com/spreadsheets/d/1Jo54VXdHyEOF2Br0FmzMC_NopKYqqmXWABumZaspYMc/gviz/tq?tq=select+A+,+F+where+lower(A)+contains+'{search_name.lower()}'+limit+3&sheet=Genna&tqx=out:csv"
    try:
        res = await aiogoogle.as_service_account(
            req,
        )
        return res
    except AiogoogleHttpError as e:
        if e.res.status_code == 400:
            raise SheetNotFoundError(sheet_title)
        else:
            raise e
    


if __name__ == "__main__":
    # Get relevant Environment variables
    load_dotenv()
    _GOOGLE_APPLICATION_CREDENTIALS=os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') # just make sure that they are there
    CHARACTER_SHEET=os.environ.get('CHARACTER_SHEET')
    
    # Setup credentials
    creds = ServiceAccountCreds(
      scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )
    ability_name = "unde"
    asyncio.run(get_ability_value(CHARACTER_SHEET, 'Genna', creds, ability_name))