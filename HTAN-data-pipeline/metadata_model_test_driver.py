from MetadataModel import MetadataModel

#inputMModelLocation = "./schemas/exampleSchemaReq.jsonld"
#inputMModelLocation = "./schemas/scRNASeq.jsonld"
inputMModelLocation = "./schemas/HTAPP.jsonld"
#inputMModelLocation = "./data/NFSchemaReq.jsonld"
inputMModelLocationType = "local"
#datasetType = "scRNASeq"
#datasetType = "Thing"
datasetType = "HTAPP"



print("*****************************************************")
print("Testing metamodel-based manifest generation")
print("*****************************************************")
mm = MetadataModel(inputMModelLocation, inputMModelLocationType)

manifest_url = mm.getModelManifest(datasetType, filenames = ["1.txt", "2.txt", "3.txt"])

print(manifest_url)


print("*****************************************************")
print("Testing metamodel-based validation")
print("*****************************************************")
manifest_path = "./manifest.csv"

annotation_errors = mm.validateModelManifest(manifest_path, datasetType)

print(annotation_errors)


print("*****************************************************")
print("Testing metamodel-based manifest population")
print("*****************************************************")

# get a sheet prepopulated with an existing manifest; returns a url to a google sheet
prepopulated_manifest_url = mm.populateModelManifest(manifest_path, datasetType)
print(prepopulated_manifest_url)

