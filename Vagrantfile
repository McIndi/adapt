# Test VM for Adapt: pytest, Helm unittest, and a live Keycloak IdP.
#
# Keycloak is a Docker service (not Kind). Kind is the right tool for chart
# install tests. A browser SSO check only needs Keycloak on :8080 and Adapt
# on :8000, which a single container does with less RAM and a shorter boot.
#
# After `vagrant up`, open http://192.168.58.30:8000 and use Sign in with
# Keycloak (alice / Alice!Adapt-Test1).

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/noble64"
  config.vm.hostname = "adapt-container-test"
  config.vm.network "private_network", ip: "192.168.58.30"
  config.vm.network "forwarded_port", guest: 8000, host: 8000
  config.vm.network "forwarded_port", guest: 8080, host: 8080
  config.vm.synced_folder ".", "/vagrant"

  config.vm.provider "virtualbox" do |virtualbox|
    virtualbox.name = "adapt-container-test"
    virtualbox.cpus = 2
    virtualbox.memory = 6144
  end

  config.vm.provision "packages", type: "shell", inline: <<-SHELL
    set -eu
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y \
      docker.io docker-compose-v2 docker-buildx qemu-user-static \
      curl ca-certificates git \
      python3 python3-venv python3-pip python3-dev python3-full \
      build-essential ffmpeg
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    systemctl enable --now docker
    usermod -aG docker vagrant
  SHELL

  config.vm.provision "keycloak", type: "shell", inline: <<-SHELL
    set -eu
    cd /vagrant/tools/vagrant
    docker compose pull
    docker compose up -d --force-recreate
    echo "Waiting for Keycloak realm discovery on the host-only IP..."
    for i in $(seq 1 90); do
      if curl -sf http://192.168.58.30:8080/realms/adapt/.well-known/openid-configuration >/dev/null; then
        echo "Keycloak realm adapt is ready."
        exit 0
      fi
      sleep 2
    done
    echo "Keycloak did not become ready in time. Check: docker compose -f /vagrant/tools/vagrant/docker-compose.yml logs" >&2
    docker compose logs --tail 80 || true
    exit 1
  SHELL

  config.vm.provision "dev", type: "shell", privileged: false, inline: <<-SHELL
    set -eu
    if ! helm plugin list 2>/dev/null | grep -q unittest; then
      helm plugin install https://github.com/helm-unittest/helm-unittest --version v0.6.3
    fi
    python3 -m venv "$HOME/venv"
    "$HOME/venv/bin/pip" install --upgrade pip
    "$HOME/venv/bin/pip" install -e "/vagrant[dev]"
    grep -q 'source "$HOME/venv/bin/activate"' "$HOME/.bashrc" || \
      echo 'source "$HOME/venv/bin/activate"' >> "$HOME/.bashrc"

    mkdir -p "$HOME/adapt-docroot"
    if [ ! -f "$HOME/adapt-docroot/products.csv" ]; then
      printf 'name,price\\nWidget,9.99\\nGadget,12.50\\n' > "$HOME/adapt-docroot/products.csv"
    fi
    "$HOME/venv/bin/adapt" admin create-permissions "$HOME/adapt-docroot" __all__

    sudo cp /vagrant/tools/vagrant/adapt.service /etc/systemd/system/adapt.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now adapt.service

    sudo tee /etc/motd >/dev/null <<'EOF'
Adapt test VM (Docker Keycloak, not Kind)

  Open:            http://192.168.58.30:8000
  Sign in:         Sign in with Keycloak
  User:            alice / Alice!Adapt-Test1
  Superuser:       adapt-admin / Admin!Adapt-Test1

  Keycloak admin:  http://192.168.58.30:8080   admin / admin
  Issuer:          http://192.168.58.30:8080/realms/adapt
  Client:          adapt-web / adapt-web-secret

  Pytest:          pytest /vagrant/tests -q
  Helm unittest:   helm unittest /vagrant/charts/adapt
  Adapt logs:      sudo journalctl -u adapt -f
  Keycloak logs:   docker compose -f /vagrant/tools/vagrant/docker-compose.yml logs -f
EOF
  SHELL
end
