// Variables to use accross the project
// which can be accessed by var.project_id
variable "project_id" {
  description = "The project ID to host the cluster in"
  default     = "dongtd6"
}

variable "zone" {
  description = "Zone for instance"
  default     = "asia-southeast1-a"
}

variable "region" {
  description = "The region the cluster in"
  default     = "asia-southeast1"
}

variable "default_disk_size" {
  description = "default_disk_size_gb"
  default     = "50"
}

variable "node_count" {
  description = "node_count"
  default     = "2"
}

variable "machine_type" {
  description = "Machine type for instance"
  default     = "e2-standard-2"
}

variable "bucket" {
  description = "GCS bucket for MLE course"
  default     = "dongtd6-bucket"
}

variable "instance_name" {
  description = "Name of the instance"
  default     = "jenkins-node"
}

variable "boot_disk_image" {
  description = "Boot disk image for instance"
  default     = "ubuntu-os-cloud/ubuntu-2204-lts"
}

variable "boot_disk_size" {
  description = "Boot disk size for instance"
  default     = 50
}

variable "firewall_jenkins_port" {
  description = "Name of the firewall rule"
  default     = "allow-jenkins-port"
}

variable "ssh_keys" {
  description = "Value of the public ssh key"
  default     = "dongtd6:ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDAgRjELJmQLrMBFF1a50TP9psou4NF6c+gbagh8q+uBQ1NhkdC6gO5ymg3M34cZSQtKDSDZb+05h3NBXd6bZN19X1Eek1Kg5bZmozh3fu58TtLwWMW7rXIn95YqEnZe5Pn6b5v5FgsEW7IpzboYO92kRWIaRraFeJMPMFKP8mYH+ZiJZvefy9w/grgbAcBh0mXL/GciiI3vfRZ3j1IwLtK/cTf893Ik6E+ERDQYSpsqmGNnGaK10hQ8wTsz3omN7z0RdhoO6oauG6igxA5Gphb6V4MKbPGwfXuJCwumoqrVyXBBkvD2xBGUJQy7P/FnKb8+oKb5zlonLgujC8To+pMIFB/Mt0t6Ihp545AhuMnEI839SxJmk5a4hG8wZBSPtJ8DxlPb503o2aCtaOztcbOBl/M6rVLGUsaUt1IADFsDUIxqVGdPE5Y4cjmJ0/DID3tGJeWaV/zjEFhw4sS3CdlNMNKUjzkYZ7xIiLkF93EPzudNnO8/PjT5V2kYw3GSgU= dongtd6@AcerUbuntu"
}
// run command "ssh-keygen" to generate ssh keys
// run command "cat ~/.ssh/id_rsa.pub" to show public ssh key

