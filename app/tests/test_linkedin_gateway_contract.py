import json
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
APP = WORKSPACE / "app"
DOCKERFILE = WORKSPACE / "hermes-src" / "Dockerfile"
COMPOSE = WORKSPACE / "compose.yaml"
SCRIPTS = APP / "scripts"


def test_hermes_image_contains_linkedin_gateway_dependencies():
    dockerfile = DOCKERFILE.read_text()
    for package in ("xvfb", "x11vnc", "fluxbox", "novnc", "websockify"):
        assert package in dockerfile
    assert "/usr/share/novnc" not in dockerfile or "novnc" in dockerfile


def test_canonical_gateway_scripts_implement_linux_flow():
    start = (SCRIPTS / "start_linkedin_browser_gateway.sh").read_text()
    status = (SCRIPTS / "status_linkedin_browser_gateway.sh").read_text()
    stop = (SCRIPTS / "stop_linkedin_browser_gateway.sh").read_text()
    install = (SCRIPTS / "install_linkedin_browser_gateway_deps.sh").read_text()

    assert "need_cmd x11vnc" in start
    assert "status_one x11vnc" in status
    assert "stop_one novnc" in stop
    assert "sudo apt-get" not in install
    assert "Docker image" in install


def test_compose_publishes_loopback_only_novnc_ports():
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=WORKSPACE,
        check=True,
        capture_output=True,
        text=True,
    )
    compose = json.loads(result.stdout)
    services = compose["services"]

    assert services["vagas_bot_01"]["ports"] == [
        {"mode": "ingress", "host_ip": "127.0.0.1", "target": 6080, "published": "6081", "protocol": "tcp"}
    ]
    assert services["vagas_bot_02"]["ports"] == [
        {"mode": "ingress", "host_ip": "127.0.0.1", "target": 6080, "published": "6082", "protocol": "tcp"}
    ]


def test_linkedin_runbook_uses_current_container_flow():
    runbook = (APP / "LINKEDIN_AUTH_RUNBOOK.md").read_text()

    assert "/opt/agent-projects/candidaturas" in runbook
    assert "/workspace/candidaturas" in runbook
    assert "hermes-vagas-bot-01" in runbook
    assert "6081" in runbook
    assert " 2.sh" not in runbook
    assert "/opt/candidaturas" not in runbook
    assert "RPi5" not in runbook


def test_websockify_binds_container_interface_for_docker_forwarding():
    start = (SCRIPTS / "start_linkedin_browser_gateway.sh").read_text()

    assert 'LINKEDIN_NOVNC_BIND:-0.0.0.0' in start
    assert 'NOVNC_URL=http://127.0.0.1:$PUBLIC_NOVNC_PORT' in start
