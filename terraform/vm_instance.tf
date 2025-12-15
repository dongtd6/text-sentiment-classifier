
# -------------------------------VM INSTANCE
resource "google_compute_instance" "vm_instance"{
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
    network = google_compute_network.vpc_tr_network.self_link    //"default"                           //"default"
    access_config {
      //Ephemeral public IP
    }
  }
  metadata = {
    ssh-keys = var.ssh_keys
  }

  metadata_startup_script = "${file("./install.docker.sh")}"
  tags = ["allow-ssh", "allow-icmp"] # add tag to add firewall rules
  depends_on = [google_compute_network.vpc_tr_network]
}