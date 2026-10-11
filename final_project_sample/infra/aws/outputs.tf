output "ecr_repository_url" { value = aws_ecr_repository.app.repository_url }
output "ecs_cluster_name" { value = aws_ecs_cluster.main.name }
output "ecs_service_name" { value = aws_ecs_service.app.name }
output "load_balancer_dns_name" { value = aws_lb.app.dns_name }
output "rds_endpoint" { value = aws_db_instance.main.address }
output "secret_arn" { value = aws_secretsmanager_secret.app.arn }
