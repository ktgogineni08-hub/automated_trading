# Terraform Outputs
# Phase 4 Tier 4: Multi-Region & High Availability

# Cluster outputs
output "cluster_endpoints" {
  description = "Kubernetes cluster endpoints"
  value = {
    for region, cluster in module.kubernetes_cluster : 
    region => cluster.cluster_endpoint
  }
}

output "cluster_names" {
  description = "Kubernetes cluster names"
  value = {
    for region, cluster in module.kubernetes_cluster : 
    region => cluster.cluster_name
  }
}

output "cluster_certificates" {
  description = "Kubernetes cluster CA certificates"
  value = {
    for region, cluster in module.kubernetes_cluster : 
    region => cluster.cluster_ca_certificate
  }
  sensitive = true
}

# Load balancer outputs
output "global_load_balancer_ip" {
  description = "Global load balancer IP address"
  value       = var.multi_region_enabled ? module.global_load_balancer[0].ip_address : null
}

output "global_load_balancer_dns" {
  description = "Global load balancer DNS name"
  value       = var.multi_region_enabled ? module.global_load_balancer[0].dns_name : null
}

# Database outputs
output "database_endpoints" {
  description = "Database endpoints"
  value = {
    for region, db in module.database : 
    region => db.endpoint
  }
  sensitive = true
}

# Monitoring outputs
output "monitoring_dashboards" {
  description = "Monitoring dashboard URLs"
  value = {
    for region, monitor in module.monitoring : 
    region => monitor.dashboard_url
  }
}

# Backup outputs
output "backup_vault_arns" {
  description = "Backup vault ARNs"
  value = {
    for region, backup in module.backup : 
    region => backup.vault_arn
  }
}

# Kubeconfig command
output "kubeconfig_commands" {
  description = "Commands to configure kubectl for each cluster"
  value = {
    for region, cluster in module.kubernetes_cluster : 
    region => cluster.kubeconfig_command
  }
}

# Connection information
output "connection_info" {
  description = "Connection information for accessing the deployed infrastructure"
  value = {
    primary_region    = var.primary_region
    all_regions       = local.regions
    multi_region      = var.multi_region_enabled
    environment       = var.environment
    load_balancer_url = var.multi_region_enabled ? module.global_load_balancer[0].dns_name : "N/A (single region)"
  }
}
