terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  name = var.project_name
  common_tags = {
    Project   = var.project_name
    ManagedBy = "terraform"
    Stage     = "draft"
  }
}

resource "aws_ecr_repository" "app" {
  name                 = local.name
  image_tag_mutability = "MUTABLE"
  force_delete         = false
  tags                 = local.common_tags
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(local.common_tags, { Name = "${local.name}-vpc" })
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = local.common_tags
}

resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  availability_zone       = var.availability_zones[count.index]
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  map_public_ip_on_launch = true
  tags                    = merge(local.common_tags, { Name = "${local.name}-public-${count.index + 1}" })
}

resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  availability_zone = var.availability_zones[count.index]
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 8)
  tags              = merge(local.common_tags, { Name = "${local.name}-private-${count.index + 1}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = local.common_tags
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = local.common_tags
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  depends_on    = [aws_internet_gateway.main]
  tags          = local.common_tags
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }
  tags = local.common_tags
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "alb" {
  name   = "${local.name}-alb"
  vpc_id = aws_vpc.main.id
  # Draft is public; before production, restrict this to VPN/management IPs or the VPC CIDR.
  ingress { from_port = 80; to_port = 80; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  egress  { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = local.common_tags
}

resource "aws_security_group" "app" {
  name   = "${local.name}-app"
  vpc_id = aws_vpc.main.id
  ingress { from_port = 8000; to_port = 8000; protocol = "tcp"; security_groups = [aws_security_group.alb.id] }
  egress  { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  tags = local.common_tags
}

resource "aws_security_group" "db" {
  name   = "${local.name}-db"
  vpc_id = aws_vpc.main.id
  ingress { from_port = 5432; to_port = 5432; protocol = "tcp"; security_groups = [aws_security_group.app.id] }
  tags = local.common_tags
}

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
  tags       = local.common_tags
}

resource "aws_db_instance" "main" {
  identifier             = local.name
  engine                 = "postgres"
  engine_version         = "15.2"
  instance_class         = "db.t4g.micro"
  allocated_storage      = 20
  storage_type           = "gp3"
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  port                   = 5432
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  skip_final_snapshot    = true
  apply_immediately      = false
  tags                   = local.common_tags
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.name}/app"
  recovery_window_in_days = 7
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    ACOP_OPENAI_API_KEY = var.acop_openai_api_key
    ACOP_SECRET_KEY     = var.acop_secret_key
    ACOP_DATABASE_URL   = "postgresql+psycopg://${var.db_username}:${var.db_password}@${aws_db_instance.main.address}:5432/${var.db_name}"
  })
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name}"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_iam_role" "execution" {
  name = "${local.name}-ecs-execution"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "secrets" {
  role = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = aws_secretsmanager_secret.app.arn }] })
}

resource "aws_ecs_cluster" "main" {
  name = local.name
  tags = local.common_tags
}

resource "aws_ecs_task_definition" "app" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.container_cpu
  memory                   = var.container_memory
  execution_role_arn       = aws_iam_role.execution.arn
  container_definitions = jsonencode([{
    name      = local.name
    image     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "ACOP_LLM_PROVIDER", value = "openai" }, { name = "ACOP_LLM_MODEL", value = "gpt-4o-mini" },
      { name = "ACOP_EMBEDDING_MODEL", value = "text-embedding-3-small" }, { name = "ACOP_LLM_TEMPERATURE", value = "0.0" },
      { name = "ACOP_LLM_SEED", value = "7" }, { name = "ACOP_ENV", value = "prod" }, { name = "ACOP_TENANT_ID", value = "default" },
      { name = "ACOP_GUARDRAILS_PATH", value = "config/guardrails.yaml" }
    ]
    secrets = [
      { name = "ACOP_OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.app.arn}:ACOP_OPENAI_API_KEY::" },
      { name = "ACOP_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.app.arn}:ACOP_SECRET_KEY::" },
      { name = "ACOP_DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.app.arn}:ACOP_DATABASE_URL::" }
    ]
    logConfiguration = { logDriver = "awslogs", options = { awslogs-group = aws_cloudwatch_log_group.app.name, awslogs-region = var.aws_region, awslogs-stream-prefix = "ecs" } }
  }])
  tags = local.common_tags
}

resource "aws_lb" "app" {
  name               = local.name
  load_balancer_type = "application"
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]
  tags               = local.common_tags
}

resource "aws_lb_target_group" "app" {
  name        = local.name
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check { path = "/"; matcher = "200-399" }
  tags = local.common_tags
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"
  default_action { type = "forward"; target_group_arn = aws_lb_target_group.app.arn }
}

resource "aws_ecs_service" "app" {
  name            = local.name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  # _WRITE_LOCK is process-local; use a distributed lock/DB CAS before scaling above 1.
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration { subnets = aws_subnet.private[*].id; security_groups = [aws_security_group.app.id]; assign_public_ip = false }
  load_balancer { target_group_arn = aws_lb_target_group.app.arn; container_name = local.name; container_port = 8000 }
  depends_on = [aws_lb_listener.http]
  tags = local.common_tags
}
