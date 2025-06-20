#!/bin/env bash
# sync the repository with git and update the local files

update_app="/${1}"

branch_name="master"

repo_dir="/addon_configs/git/appdaemon-scripts"
if [ ! -d "${repo_dir}" ]; then
    echo "Repository directory does not exist: ${repo_dir}"
    exit 1
fi
# Ensure the repository directory is a git repository
if [ ! -d "${repo_dir}/.git" ]; then
    echo "Directory is not a git repository: ${repo_dir}"
    exit 1
fi

apps_dir="/addon_configs/a0d7b954_appdaemon/apps"
if [ ! -d "${apps_dir}" ]; then
    echo "Apps directory does not exist: ${apps_dir}"
    exit 1
fi

repo_apps_dir="${repo_dir}/git-apps"
if [ ! -d "${repo_apps_dir}" ]; then
    echo "Repository apps directory does not exist: ${repo_apps_dir}"
    exit 1
fi


{
    cd "${repo_dir}" || exit 1
    # update the repository
    git fetch origin || sleep 6
    git fetch origin
    git pull
    git fetch origin
    git checkout "${branch_name}"
    # reset if local changes are present
    git reset --hard "origin/${branch_name}" && git clean -f -d
    # copy apps to the apps directory
    echo "Copying apps from ${repo_apps_dir} to ${apps_dir}"
    cp -rv "${repo_apps_dir}${update_app}"/* "${apps_dir}${update_app}/" || {
        echo "Failed to copy apps from ${repo_apps_dir}${update_app} to ${apps_dir}${update_app}"
        exit 1
    }
    echo "Apps updated successfully."
}
