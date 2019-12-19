from __future__ import print_function
import pickle
import os.path
import collections

import pandas as pd

from typing import Any, Dict, Optional, Text

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pygsheets as ps

from schema_explorer import SchemaExplorer
from schema_generator import get_JSONSchema_requirements

class ManifestGenerator(object):

    """TODO:
    Add documentation and style according to style-guide
    """

    def __init__(self,
                 title: str, # manifest sheet title
                 se: SchemaExplorer = None,
                 root: str = None,
                 additional_metadata: Dict = None 
                 ) -> None:
    
        """TODO: read in a config file instead of hardcoding paths to credential files...
        """

        # If modifying these scopes, delete the file token.pickle.
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

        # path to Google API credentials file
        self.credentials_path = "credentials.json"

        # google service for Drive API
        self.drive_service = None

        # google service for Sheet API
        self.sheet_service = None

        # google service credentials object
        self.creds = None

        # schema root
        self.root = root

        # manifest title
        self.title = title

        # schema explorer object
        self.se = se

        # additional metadata to add to manifest
        self.additional_metadata = additional_metadata


    # TODO: replace by pygsheets calls?
    def build_credentials(self):

        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is created automatically when the authorization flow completes for the first time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.scopes)
                creds = flow.run_console() ### don't have to deal with ports
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        # get a Google Sheet API service
        self.sheet_service = build('sheets', 'v4', credentials=creds)
        # get a Google Drive API service
        self.drive_service = build('drive', 'v3', credentials=creds)
        self.creds = creds
        
        return


    def _column_to_letter(self, column):
         character = chr(ord('A') + column % 26)
         remainder = column // 26
         if column >= 26:
            return self._column_to_letter(remainder-1) + character
         else:
            return character


    def _create_empty_manifest_spreadsheet(self, title):

        # create an empty spreadsheet
        spreadsheet = {
            'properties': {
                'title': title
            }
        }   
        
        spreadsheet = self.sheet_service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
        spreadsheet_id = spreadsheet.get('spreadsheetId')

        return spreadsheet_id


    def _set_permissions(self, fileId):

        def callback(request_id, response, exception):
            if exception:
                # Handle error
                print(exception)
            else:
                print ("Permission Id: %s" % response.get('id'))

        batch = self.drive_service.new_batch_http_request(callback = callback)
       
        worldPermission = {
                            'type': 'anyone',
                            'role': 'writer'
        }

        batch.add(self.drive_service.permissions().create(
                                        fileId = fileId,
                                        body = worldPermission,
                                        fields = 'id',
                                        )
        )
        batch.execute()


    def get_manifest(self, json_schema = None): 

        self.build_credentials()

        spreadsheet_id = self._create_empty_manifest_spreadsheet(self.title)

        if not json_schema:
            json_schema = get_JSONSchema_requirements(self.se, self.root, self.title)

        required_metadata_fields = {}

        # gathering dependency requirements and corresponding allowed values constraints for root node
        for req in json_schema["required"]: 
            if req in json_schema["properties"]:
                required_metadata_fields[req] = json_schema["properties"][req]["enum"]
            else:
                required_metadata_fields[req] = []
   

        # gathering dependency requirements and allowed value constraints for conditional dependencies if any
        if "allOf" in json_schema: 
            for conditional_reqs in json_schema["allOf"]: 
                 if "required" in conditional_reqs["if"]:
                     for req in conditional_reqs["if"]["required"]: 
                        if req in conditional_reqs["if"]["properties"]:
                            if not req in required_metadata_fields:
                                if req in json_schema["properties"]:
                                    required_metadata_fields[req] = json_schema["properties"][req]["enum"]
                                else:
                                    required_metadata_fields[req] = conditional_reqs["if"]["properties"][req]["enum"]
                    
                     for req in conditional_reqs["then"]["required"]: 
                         if not req in required_metadata_fields:
                                if req in json_schema["properties"]:
                                    required_metadata_fields[req] = json_schema["properties"][req]["enum"]
                                else:
                                     required_metadata_fields[req] = []    

        # if additional metadata is provided append columns (if those do not exist already
        if self.additional_metadata:
            for column in self.additional_metadata.keys():
                if not column in required_metadata_fields:
                    required_metadata_fields[column] = []
    

        # adding columns to manifest sheet
        end_col = len(required_metadata_fields.keys())
        end_col_letter = self._column_to_letter(end_col) 

        range = "Sheet1!A1:" + str(end_col_letter) + "1"
        ordered_metadata_fields = [list(required_metadata_fields.keys())]

        # order columns header (since they are generated based on a json schema, which is a dict) the order could be somewhat arbitrary;this is not the case from a better user experience perspective; we can add better rules, but for now alphabetical order where column Filename is first and entityId is last, should suffice
        
        ordered_metadata_fields[0] = self.sort_manifest_fields(ordered_metadata_fields[0])

        
        body = {
                "values": ordered_metadata_fields
        }
       
        self.sheet_service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range=range, valueInputOption="RAW", body=body).execute()
        
        # adding additinoal metadata values if needed and adding value-constraints from data model as dropdowns
        for i, req in enumerate(ordered_metadata_fields[0]):
        #for i, (req, values) in enumerate(required_metadata_fields.items()):
            values = required_metadata_fields[req]
            #adding additional metadata if needed
            if self.additional_metadata and req in self.additional_metadata:
                values = self.additional_metadata[req]
                target_col_letter = self._column_to_letter(i) 

                body =  {
                            "majorDimension":"COLUMNS",
                            "values":[values]
                }
                
                response = self.sheet_service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range = target_col_letter + '2:' + target_col_letter + str(len(values) + 1), valueInputOption = "RAW", body = body).execute()

                continue

            # adding value-constraints if any
            req_vals = [{"userEnteredValue":value} for value in values if value]

            if not req_vals:
                continue

            # generating sheet api request to populate the dropdown
            body =  {
                      "requests": [
                        {
                        'setDataValidation':{
                            'range':{
                                'startRowIndex':1,
                                'startColumnIndex':i, 
                                'endColumnIndex':i+1, 
                            },
                            'rule':{
                                'condition':{
                                    'type':'ONE_OF_LIST', 
                                    'values': req_vals
                                },
                                'inputMessage' : 'Choose one from dropdown',
                                'strict':True,
                                'showCustomUi': True
                            }
                        }            
                    }
                ]
            }   

            response = self.sheet_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    
        # setting up spreadsheet permissions (setup so that anyone with the link can edit)
        self._set_permissions(spreadsheet_id)

        # generating spreadsheet URL
        manifest_url = "https://docs.google.com/spreadsheets/d/" + spreadsheet_id
     
        print("==========================")
        print("Manifest successfully generated from schema!")
        print("URL: " + manifest_url)
        print("==========================")
        

        return manifest_url


    def populate_manifest_spreasheet(self, existing_manifest_path, empty_manifest_url):

        manifest = pd.read_csv(existing_manifest_path).fillna("")
        manifest_fields = manifest.columns.tolist()
        manifest_fields = self.sort_manifest_fields(manifest_fields)
        manifest = manifest[manifest_fields]
        
        self.build_credentials()
        gc = ps.authorize(custom_credentials = self.creds)
        sh = gc.open_by_url(empty_manifest_url)
        wb = sh[0]
        wb.set_dataframe(manifest, (1,1))
        
        # set permissions so that anyone with the link can edit
        sh.share("", role = "writer", type = "anyone")

        return sh.url 


    def sort_manifest_fields(self, manifest_fields):
        """ sort a set of metadata fields (e.g. to organize manifest column headers in a more user-friendly and consistent pattern, (e.g. alphabetical))  
        """
        print(manifest_fields)
        manifest_fields.sort()

        if "Filename" in manifest_fields:
            pos = manifest_fields.index("Filename")
            manifest_fields[pos] = manifest_fields[0]
            manifest_fields[0] = "Filename"

        if "entityId" in manifest_fields:
            manifest_fields.remove("entityId")
            manifest_fields.append("entityId")

        print(manifest_fields)
        return manifest_fields
