[command](#command) | [goal](#goal)

## command

- Run the local script before USER ${USER_NAME}, replacing the remote installer at Dockerfile/base.Dockerfile:20
```Dockerfile
COPY scripts/install-docker.sh /tmp/install-docker.sh
RUN bash /tmp/install-docker.sh && rm /tmp/install-docker.sh
```

- Add set -euo pipefail so installation errors fail the build.
- Use apt-get instead of apt in scripts.
- Clear /var/lib/apt/lists/* after installation, within the same RUN.

## goal

Install Docker using the local scripts/install-docker.sh instead of the remote installer before USER ${USER_NAME} in Dockerfile/base.Dockerfile. Make installation fail on errors with set -euo pipefail, use apt-get for package operations, and remove the temporary installer and /var/lib/apt/lists/* within the installation RUN.
