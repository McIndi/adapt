Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"
  config.vm.hostname = "adapt-container-test"

  config.vm.provider "virtualbox" do |virtualbox|
    virtualbox.name = "adapt-container-test"
    virtualbox.cpus = 2
    virtualbox.memory = 4096
  end

  config.vm.provision "shell", inline: <<-SHELL
    set -eu
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y docker.io docker-buildx qemu-user-static curl
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    systemctl enable --now docker
    usermod -aG docker vagrant
  SHELL
end
