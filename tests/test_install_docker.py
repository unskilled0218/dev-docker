"""Offline installer contracts; every external installer command is a safe stub."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DockerInstallerTests(unittest.TestCase):
  def test_installer_uses_strict_mode_and_apt_get(self):
    script = (ROOT / "scripts/install-docker.sh").read_text()
    self.assertTrue(script.startswith("#!/bin/bash\nset -euo pipefail\n"))
    self.assertNotRegex(script, r"(?m)^\s*apt\s")
    self.assertEqual(script.count("apt-get update"), 2)
    self.assertIn("apt-get install ca-certificates curl -y", script)
    self.assertIn("apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y", script)

  def test_base_runs_local_installer_before_user_and_cleans_each_install_layer(self):
    content = (ROOT / "Dockerfile/base.Dockerfile").read_text()
    instructions = content.replace("\\\n", " ").splitlines()
    copy = instructions.index("COPY scripts/install-docker.sh /tmp/install-docker.sh")
    run = next(index for index, line in enumerate(instructions) if line.startswith("RUN bash /tmp/install-docker.sh"))
    user = instructions.index("USER ${USER_NAME}")
    self.assertLess(copy, run)
    self.assertLess(run, user)
    self.assertRegex(instructions[run], r"bash /tmp/install-docker\.sh\s+&&\s+rm /tmp/install-docker\.sh\s+&&\s+rm -rf /var/lib/apt/lists/\*")
    package_runs = [line for line in instructions if line.startswith("RUN ") and "apt-get install" in line]
    self.assertEqual(len(package_runs), 1)
    self.assertTrue(package_runs[0].endswith("rm -rf /var/lib/apt/lists/*"))
    self.assertNotRegex(content, r"\bapt\s+(?:update|install)\b")
    self.assertNotRegex(content, r"https?://\S*install-docker\.sh")
    self.assertIn("scripts/setup.sh | bash", content)

  def test_package_failure_stops_installer_before_later_commands(self):
    # An isolated PATH prevents any real package, network, file, or user command.
    stub = '''#!/bin/bash
name=${0##*/}
printf '%s %s\n' "$name" "$*" >> "$CALLS"
case "$name" in
  apt-get)
    count=0
    if [[ -f "$COUNT" ]]; then read -r count < "$COUNT"; fi
    count=$((count + 1))
    printf '%s\n' "$count" > "$COUNT"
    if [[ "$count" == "$FAIL_AT" ]]; then exit 47; fi ;;
  tee) while IFS= read -r line; do :; done ;;
  dpkg) printf 'amd64\n' ;;
  getent) printf 'container:x:1000:1000::/home/container:/bin/bash\n' ;;
  cut) while IFS= read -r line; do printf 'container\n'; done ;;
esac
'''
    for fail_at in (1, 4, 0):
      with self.subTest(failed_package_command=fail_at), tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bin_path = root / "bin"
        bin_path.mkdir()
        for name in ("apt-get", "install", "curl", "chmod", "tee", "dpkg", "getent", "cut", "usermod"):
          command = bin_path / name
          command.write_text(stub)
          command.chmod(0o755)
        env = {"PATH": str(bin_path), "CALLS": str(root / "calls"), "COUNT": str(root / "count"), "FAIL_AT": str(fail_at)}
        result = subprocess.run([shutil.which("bash"), str(ROOT / "scripts/install-docker.sh")],
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 47 if fail_at else 0, result.stderr)
        self.assertEqual(int((root / "count").read_text()), fail_at or 4)
        calls = (root / "calls").read_text().splitlines()
        usermod = [line for line in calls if line.startswith("usermod ")]
        self.assertEqual(usermod, [] if fail_at else ["usermod -aG docker container"])
        if fail_at == 1:
          self.assertEqual(calls, ["apt-get update"])
