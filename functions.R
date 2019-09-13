# detach("package:synapser", unload=TRUE)
# unloadNamespace("synapser")

library(reticulate) 
# py_available()
# conda_python()
use_condaenv('py3.5', required = TRUE ) ### use path to python 3.5 env
py_discover_config() #absolutely cannot use synapser or else the paths gets messed up

reticulate::import("sys")
reticulate::import_from_path("MetadataModel", path = "HTAN-data-pipeline")
### need pygsheets installed, pandas

source_python("synLoginFun.py")
syn_login()

source_python("metadataModelFuns.py")

# source_python("./HTAN-data-pipeline/storage_test_driver.py")

source_python("synStoreFuns.py")

### logs in and gets list of projects they have access to
projects_list <- get_projects_list
projects_namedList <- c()
for (i in seq_along(projects_list)) {
  projects_namedList[projects_list[[i]][[2]]] <- projects_list[[i]][[1]]
}

### makes summary df
df <- data.frame()
for (i in seq_along(projects_namedList)) {
  ### get project
  projectName <- names(projects_namedList[i])
  project_ID <- projects_namedList[[i]]
  print(projectName)
  print(project_ID)
  df[i,1] <- projectName
  
  ### get folders
  folder_list <- get_folder_list(project_ID)
  # print(folder_list)
  folders_namedList <- c()
  for (i in seq_along(folder_list)) {
    folders_namedList[folder_list[[i]][[2]]] <- folder_list[[i]][[1]]
  }
  print(folders_namedList)
  
  folderNames <- names(folders_namedList)
  folder_ID <- folders_namedList[[i]]
  for (f in seq_along(folders_namedList)) {
    print(f)
    folderName <- names(folders_namedList[f])
    folder_ID <- folders_namedList[[f]]
    
    df[i,2] <- folderName
    print(folderName)
    print(folder_ID)
    
    manifest <- get_storage_manifest_path(folder_ID)
    if ( !is.null(manifest)) {
      manifest_df <- read.csv(manifest)
      ### how to cound empty cells vs all cells
      dim_val <- dim(manifest_df)
      total_cells <- dim_val[1] * dim_val[2]
      empty_cells <- table(is.na(manifest_df))
      per_filled <- (empty_cells[1] / total_cells )* 100
      df[i,3] <- total_cells
      df[i,4] <- per_filled
    }
  }
  
}
