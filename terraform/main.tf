# Ref: https://github.com/terraform-google-modules/terraform-google-kubernetes-engine/blob/master/examples/simple_autopilot_public
# To define that we will use GCP
terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = "4.80.0" // Provider version
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
  required_version = "1.5.6" // Terraform version
}

// The library with methods for creating and
// managing the infrastructure in GCP, this will
// apply to all the resources in the project
provider "google" {
  project     = var.project_id
  region      = var.region
}

// Google Kubernetes Engine
resource "google_container_cluster" "gke-cluster" {
  name     = "${var.project_id}-dev-gke"
  location = var.zone
  initial_node_count = 2
  
  //remove_default_node_pool = true
  // Enabling Autopilot for this cluster
  //enable_autopilot = false
    node_config {
    disk_size_gb = var.default_disk_size
  }
}

data "google_client_config" "default" {}

# Kubernetes provider
provider "kubernetes" {
  host                   = "https://${google_container_cluster.gke-cluster.endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(google_container_cluster.gke-cluster.master_auth[0].cluster_ca_certificate)
  
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "gke-gcloud-auth-plugin" # hoặc "gcloud"  gcloud auth application-default login
    args        = ["get-credentials", google_container_cluster.gke-cluster.name, "--zone", google_container_cluster.gke-cluster.location, "--project", var.project_id]
  }
}

resource "kubernetes_namespace" "model_serving_namespace" {
  metadata {
    name = "model-serving"
    labels = {
      environment = "development"
    }
  }
  depends_on = [google_container_cluster.gke-cluster]
}

# Grant admin role for default service account in "model-serving" namespace 
resource "kubernetes_cluster_role_binding" "model_serving_admin_binding" {
  metadata {
    name = "model-serving-admin-binding"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "admin"
  }

  subject {
    kind      = "ServiceAccount"
    name      = "default"
    namespace = "model-serving"
  }
}
# -----------------------------------------------------------------------------
# Create and permission for Jenkins Service Account
resource "kubernetes_namespace" "jenkins_namespace" {
  metadata {
    name = "jenkins" # a namspace only for service account
    labels = {
      environment = "devops-tools"
    }
  }
  depends_on = [google_container_cluster.gke-cluster]
}
# Service Account for Jenkins Master
resource "kubernetes_service_account" "jenkins_master_sa" {
  metadata {
    name      = "jenkins" # serivce account is 'jenkins'
    namespace = kubernetes_namespace.jenkins_namespace.metadata[0].name
  }
  depends_on = [kubernetes_namespace.jenkins_namespace]
}
# Secret Token for Jenkins Master SA
resource "kubernetes_secret" "jenkins_master_sa_token" {
  metadata {
    name      = "jenkins-sa-token" # secret name include token
    namespace = kubernetes_service_account.jenkins_master_sa.metadata[0].namespace
    annotations = {
      "kubernetes.io/service-account.name" = kubernetes_service_account.jenkins_master_sa.metadata[0].name
    }
  }
  type = "kubernetes.io/service-account-token"
  depends_on = [kubernetes_service_account.jenkins_master_sa]
}

# ClusterRole grant for Jenkins SA overal cluster (to managerment Pods on it's namespace
# and deploy on other namespace). This is ClusterRole so don't need namespace.
resource "kubernetes_cluster_role" "jenkins_cluster_role" {
  metadata {
    name = "jenkins-gke-controller-clusterrole" # ClusterRole name
  }
  rule {
    api_groups = [""] # Core API group
    resources  = ["pods", "pods/exec", "pods/log"] # agent Pods managerment
    verbs      = ["create", "delete", "get", "list", "patch", "update", "watch"]
  }
  rule {
    api_groups = [""] # Core API group cho deploy
    resources  = ["services", "configmaps", "secrets", "events"] # Quyền deploy ứng dụng (secrets cho Helm)
    verbs      = ["create", "delete", "get", "list", "patch", "update", "watch"]
  }
  rule {
    api_groups = ["apps"] # API group cho Deployments, StatefulSets
    resources  = ["deployments", "statefulsets", "replicasets"]
    verbs      = ["create", "delete", "get", "list", "patch", "update", "watch"]
  }
  rule {
    api_groups = ["networking.k8s.io"] # API group cho Ingress
    resources  = ["ingresses"]
    verbs      = ["create", "delete", "get", "list", "patch", "update", "watch"]
  }
  rule {
    api_groups = ["helm.sh"]
    resources  = ["releases"]
    verbs      = ["create", "delete", "get", "list", "patch", "update", "watch"]
  }
}

# ClusterRoleBinding to bind the above ClusterRole to Jenkins' Service Account
# ClusterRoleBinding don't need namespace because it is cluster level.
resource "kubernetes_cluster_role_binding" "jenkins_cluster_role_binding" {
  metadata {
    name = "jenkins-gke-controller-clusterrolebinding"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role.jenkins_cluster_role.metadata[0].name
  }
  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.jenkins_master_sa.metadata[0].name
    namespace = kubernetes_service_account.jenkins_master_sa.metadata[0].namespace
  }
  depends_on = [
    kubernetes_service_account.jenkins_master_sa,
    kubernetes_cluster_role.jenkins_cluster_role
  ]
}
# -----------------------------------------------------------------------------

//resource "google_container_node_pool" "node_pool" {
//  name       = "develop-node-pool"
//  cluster    = "${var.project_id}-dev-gke"
//  location   = var.zone
//  node_count = var.node_count
//  node_config {
//    machine_type = var.machine_type
//    disk_size_gb = var.default_disk_size
//    oauth_scopes = [
//      "https://www.googleapis.com/auth/cloud-platform"
//    ]
//  }
//  depends_on = [google_container_cluster.gke-cluster]
//}

resource "google_compute_instance" "new-node"{
  name = var.instance_name
  machine_type = var.machine_type
  zone = var.zone

  boot_disk {
    initialize_params {
      image = var.boot_disk_image
      size = var.boot_disk_size
    }
  }

  network_interface {
    network = "default"
    access_config {
      //Ephemeral public IP
    }
  }
  metadata = {
    ssh-keys = var.ssh_keys
  }
  depends_on = [google_container_cluster.gke-cluster]
}

resource "google_storage_bucket" "new-bucket" {
  name          = var.bucket
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true
  depends_on = [google_container_cluster.gke-cluster]
}

resource "google_compute_firewall" "firewall_jenkins_port"{
  name = var.firewall_jenkins_port
  network = "default"
  allow{
    protocol = "tcp"
    ports = ["8081","50000"]
  }
  source_ranges = ["0.0.0.0/0"] //Allow all traffic
  depends_on = [google_container_cluster.gke-cluster]
}






