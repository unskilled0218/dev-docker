# goal

- [command](#command)
- [goal](#goal-1)

## command

- release with latest tag
- connect packages to repo
- I wanna see packages in dev/dev-docker page
- my-base -> base, npm-non-root -> npm, android-dev -> android
- remove tauri and switchboard from release phase. leave Dockerfile
- also remove android from release phase
- remove Android, Tauri, and Switchboard from the build phase too; retain their Dockerfiles

## goal

Update the image release workflow to build and publish only `base` and `npm` with the `latest` tag and associate their Gitea packages with `dev/dev-docker` so they appear on that repository's Packages page. Rename image packages from `my-base` to `base`, `npm-non-root` to `npm`, and `android-dev` to `android`, keeping dependent image references consistent. Exclude Android, Tauri, and Switchboard from both automated build and release phases while retaining their Dockerfiles for manual use.
