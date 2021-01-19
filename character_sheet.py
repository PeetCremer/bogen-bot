import requests
import os
import io
from dotenv import load_dotenv

from numpy import random

import csv


class CharacterSheet:
  def __init__(self, sheet_url):
    self.sheet_url = sheet_url
    self.sheet = None
  
  def update_sheet(self):
    # Get sheet content from url
    req = requests.get(self.sheet_url)
    req.raise_for_status()
    csv_bytes = req.content
    # create csv reader
    csv_io = io.StringIO(csv_bytes.decode())
    reader = csv.reader(csv_io)
    # decode first row and build value dict
    first_row = reader.__next__()
    if first_row is None:
      return None
    # Extract idx of value column
    value_idx = 0
    for idx, key in enumerate(first_row):
      if key == "Wert":
        value_idx = idx
        break
    if value_idx == 0:
      return None

    result_dict = {}
    for row in reader:
      if len(row) > value_idx:
        key = row[0]
        val = row[value_idx]
        if val:
          result_dict[key] = int(val)
    self.sheet = result_dict
    return self.sheet

if __name__ == "__main__":
  load_dotenv()
  CHARACTER_SHEET_URL = os.getenv('CHARACTER_SHEET_URL', None)
  if CHARACTER_SHEET_URL is None:
    raise ValueError("Environnment variable 'CHARACTER_SHEET_URL' has to be set!")

  cs = CharacterSheet(CHARACTER_SHEET_URL)
  cs.update_sheet()


