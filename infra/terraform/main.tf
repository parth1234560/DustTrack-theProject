
locals {
  name_prefix = "dusttrack-${var.environment}"
}


module "storage" {
  source            = "./modules/storage"
  name_prefix       = local.name_prefix
  allowed_origins   = var.allowed_origins
  photo_bucket_name = var.photo_bucket_name

  state_machine_arn = module.workflow.state_machine_arn
}
module "database" {
  source = "./modules/database"

  name_prefix = local.name_prefix
}

module "identity" {
  source      = "./modules/identity"
  name_prefix = local.name_prefix
}


module "api" {
  source           = "./modules/api"
  name_prefix      = local.name_prefix
  cognito_issuer   = module.identity.issuer_url
  cognito_audience = module.identity.app_client_id
  allowed_origins  = var.allowed_origins

  inspections_table_name     = module.database.inspections_table_name
  segments_table_name        = module.database.segments_table_name
  cleaning_events_table_name = module.database.cleaning_events_table_name
  photo_bucket_name          = module.storage.photo_bucket_name
}

module "workflow" {
  source                 = "./modules/workflow"
  name_prefix            = local.name_prefix
  inspections_table_name = module.database.inspections_table_name
}
module "monitoring" {
  source = "./modules/monitoring"

  lambda_names = setunion(
    toset([module.api.lambda_function_name]),
    module.workflow.lambda_function_names
  )

  state_machine_arn = module.workflow.state_machine_arn
  api_id            = module.api.api_id
  api_stage_name    = module.api.stage_name
}
