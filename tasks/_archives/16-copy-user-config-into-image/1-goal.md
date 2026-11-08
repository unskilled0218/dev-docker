- [command](#command)
- [goal](#goal)

## command

copy `~/.ssh`, `~/.gitconfig`, `~/.config/token` like crt files

## goal

Include the build user's `~/.ssh`, `~/.gitconfig`, and `~/.config/token` in the image build context, like the certificate files. Copy them into the corresponding paths under `/home/container`, with suitable ownership and permissions, so containers use the baked-in files instead of the three Compose bind mounts. These private images will contain extractable SSH keys and tokens; keep those files out of Git and build logs. No interactive build prompt is requested.
