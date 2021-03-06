# allows specifying explicit variable types
from typing import Any, Dict, Optional, Text

# manipulation of dataframes 
import pandas as pd

# Python client for Synapse
import synapseclient

from synapseclient import File

class SynapseStorage(object):

    """Implementation of Storage interface for datasets/files stored on Synapse.
    Provides utilities to list files in a specific project; update files annotations, create fileviews, etc.
    """

    def __init__(self,
                 storageFileview: str,
                 syn: synapseclient = None,
                 ) -> None:

        """Instantiates a SynapseStorage object

        Args:
            syn: synapse client; if not provided instantiate one
            storageFileview: synapse ID of fileview containing administrative storage metadata; 
            TODO: move away from specific project setup and work with an interface that Synapse specifies (e.g. based on schemas)
        """
        
        if not syn:  
            self.syn = synapseclient.Synapse()
            self.syn.login()
        else:
            self.syn = syn

        self.storageFileview = storageFileview

        # get data in administrative fileview for this pipeline 
        self.setStorageFileviewTable() 


    def setStorageFileviewTable(self) -> None:
        """ 
            Gets all data in an administrative fileview as a pandas dataframe and sets the SynapseStorage storageFileviewTable attribute
            Raises: TODO 
                ValueError: administrative fileview not found.
        """
        # query fileview for all administrative data
        self.storageFileviewTable = self.syn.tableQuery("SELECT * FROM " + self.storageFileview).asDataFrame()

        
    def getStorageProjects(self) -> list: 
    
        """ get all storage projects the current user has access to
        within the scope of the storage fileview parameter specified as SynapseStorage attribute

        Returns: a list of storage projects the current user has access to; the list consists of tuples (projectId, projectName) 
        """

        # get the set of all storage Synapse project accessible for this pipeline
        storageProjects = self.storageFileviewTable["projectId"].unique()

        # get the set of storage Synapse project accessible for this user

        # get current user ID
        currentUser = self.syn.getUserProfile()
        currentUserName = currentUser.userName 
        currentUserId = currentUser.ownerId
        
        # get a set of projects from Synapse (that this user participates in)
        currentUserProjects = self.syn.restGET('/projects/MY_PROJECTS/user/{principalId}?limit=1000'.format(principalId=currentUserId))

        # prune results json filtering project id
        currentUserProjects = [currentUserProject["id"] for currentUserProject in currentUserProjects["results"]]

        # find set of user projects that are also in this pipeline's storage projects set
        storageProjects = list(set(storageProjects) & set(currentUserProjects))

        # prepare a return list of project IDs and names
        projects = []
        for projectId in storageProjects:
            projectName = self.syn.get(projectId, downloadFile = False).name
            projects.append((projectId, projectName))

        return projects


    def getStorageDatasetsInProject(self, projectId:str) -> list:
        
        """ get all datasets in folder under a given storage projects the current user has access to

        Args:
            projectId: synapse ID of a storage project
        Returns: a list of datasets within the given storage project; the list consists of tuples (datasetId, datasetName)
        Raises: TODO
            ValueError: Project ID not found.
        """
        
        # select all folders and their names w/in the storage project
        foldersTable = self.storageFileviewTable[(self.storageFileviewTable["type"] == "folder") & (self.storageFileviewTable["projectId"] == projectId)]

        # return an array of tuples (folderId, folderName)
        folderList = list(foldersTable[["id", "name"]].itertuples(index = False, name = None))

        return folderList


    def getFilesInStorageDataset(self, datasetId:str) -> list:
        """ get all files in a given dataset folder 

        Args:
            datasetId: synapse ID of a storage dataset
        Returns: a list of files; the list consist of tuples (fileId, fileName)
        Raises: TODO
            ValueError: Dataset ID not found.
        """

        # select all files within a given storage dataset (top level folder in a Synapse storage project)
        filesTable = self.storageFileviewTable[(self.storageFileviewTable["type"] == "file") & (self.storageFileviewTable["parentId"] == datasetId)]

        # return an array of tuples (fileId, fileName)
        fileList = list(filesTable[["id", "name"]].itertuples(index = False, name = None))

        return fileList
        

    def associateMetadataWithFiles(self, metadataManifestPath:str, datasetId:str) -> str:
        """Associate metadata with files in a storage dataset already on Synapse. 
        Upload metadataManifest in the storage dataset folder on Synapse as well. Return synapseId of the uploaded manifest file.
        
            Args: metadataManifestPath path to csv containing a validated metadata manifest. The manifest should include a column entityId containing synapse IDs of files/entities to be associated with metadata 
            Returns: synapse Id of the uploaded manifest
            Raises: TODO
                FileNotFoundException: Manifest file does not exist at provided path.

        """

        # read manifest csv
        manifest = pd.read_csv(metadataManifestPath)

        # use file ID (that is a synapse ID) as index of the dataframe
        manifest.set_index("entityId", inplace = True)

        # convert metadata in a form suitable for setting annotations on Synapse
        manifestMetadata = manifest.to_dict("index") 
        print(manifestMetadata)

        # set annotations to files on Synapse
        for fileId, metadata in manifestMetadata.items():
            self.syn.setAnnotations(fileId, metadata)

        # store manifest to Synapse
        manifestSynapseFile = File(metadataManifestPath, description = "Manifest for dataset " + datasetId, parent = datasetId)

        manifestSynapseFileId = self.syn.store(manifestSynapseFile).id

        return manifestSynapseFileId
