variable "aws_region" {
  description = "AWS region; intentionally required rather than invented."
  type        = string
}

variable "availability_zones" {
  description = "At least two AZs in aws_region."
  type        = list(string)
}

variable "project_name" {
  type    = string
  default = "acop"
}

variable "image_tag" {
  description = "ECR image tag. The draft workflow publishes latest."
  type        = string
  default     = "latest"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "db_name" {
  type    = string
  default = "acop"
}

variable "db_username" {
  type    = string
  default = "acop"
}

variable "db_password" {
  description = "Inject from a secure tfvars/CI mechanism; never commit it."
  type        = string
  sensitive   = true
}

variable "acop_openai_api_key" {
  type      = string
  sensitive = true
}

variable "acop_secret_key" {
  type      = string
  sensitive = true
}

variable "container_cpu" {
  type    = number
  default = 512
}

variable "container_memory" {
  type    = number
  default = 1024
}
