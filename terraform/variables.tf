variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Application name used for resource naming"
  type        = string
  default     = "system-health-api"
}

variable "environment" {
  description = "Deployment environment (dev / staging / prod)"
  type        = string
}

variable "task_cpu" {
  description = "ECS task CPU units (256 = 0.25 vCPU)"
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 1024
}

variable "desired_count" {
  description = "Number of running ECS tasks"
  type        = number
  default     = 2
}

variable "min_capacity" {
  description = "Auto-scaling minimum task count"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Auto-scaling maximum task count"
  type        = number
  default     = 10
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}
