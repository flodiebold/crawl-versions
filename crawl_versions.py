#!/bin/env python

import argparse, os, os.path, subprocess, yaml, traceback, sys
from common import *

source_address = "git://gitorious.org/crawl/crawl.git"

def call_git(command, *args, **kwargs):
    if kwargs.get("output", False):
        return subprocess.check_output(["git", command] + list(args))
    else:
        subprocess.check_call(["git", command] + list(args))

def init_source():
    source_dir = os.path.join(base_dir, "src")
    if os.path.isdir(source_dir): return source_dir
    print "Downloading crawl source..."
    call_git("clone", source_address, source_dir)
    return source_dir

def load_config():
    config_dir = os.path.join(base_dir, "crawl-versions.conf.d")
    versions = []
    for filename in os.listdir(config_dir):
        if not filename.endswith(".yml"): continue
        with open(os.path.join(config_dir, filename)) as f:
            contents = f.read()
        for data in yaml.load_all(contents):
            versions.append(data)
    return versions

def compile_revision(version, revision):
    common_dir = os.path.join(get_crawl_dir(), version)
    revision_dir = os.path.join(common_dir, revision)
    if os.path.isdir(revision_dir): return
    source_dir = init_source()
    old_cwd = os.getcwd()
    os.chdir(os.path.join(source_dir, "crawl-ref", "source"))
    try:
        call_git("checkout", "-qf", revision)
        command = ["make",
                   "prefix=" + revision_dir,
                   "DATADIR=" + os.path.join(revision_dir, "data/"),
                   "WEBDIR=" + os.path.join(revision_dir, "web/"),
                   "SAVEDIR=" + os.path.join(common_dir, "saves/"),
                   "SHAREDDIR=" + os.path.join(common_dir, "shared/"),
                   "USE_DGAMELAUNCH=Y",
                   "WEBTILES=Y",
                   "clean",
                   "install"]
        subprocess.check_call(command)
    finally:
        os.chdir(old_cwd)

def update_version(version):
    try:
        latest = call_git("describe", version["branch"], output=True).strip()
        present = revision_present(version["name"], latest)
        print "Latest", version["name"], "is", latest
        
        compile_revision(version["name"], latest)
        version_dir = os.path.join(get_crawl_dir(), version["name"])
        os.symlink(latest, os.path.join(version_dir, "latest.new"))
        os.rename(os.path.join(version_dir, "latest.new"),
                  os.path.join(version_dir, "latest"))

        bin_dir = os.path.join(base_dir, "bin")
        if not os.path.isdir(bin_dir): os.makedirs(bin_dir)
        bin_file = os.path.join(bin_dir, version["name"])
        runner_script = os.path.join(script_dir, "crawl_runner.py")
        if not os.path.isfile(bin_file):
            with open(bin_file, "w") as f:
                f.write("#!/bin/sh\n")
                f.write(runner_script + ' "' + version["name"] + '" "$@"\n')
            os.chmod(bin_file, 0755)
        return True
    except:
        print "Update of", version["name"], "failed!"
        traceback.print_exc()
        return False

def update(args):
    config = load_config()
    source_dir = init_source()
    os.chdir(source_dir)
    call_git("fetch", "--all")
    success = True
    for version in config:
        success = success and update_version(version)
    return 0 if success else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage crawl versions.")
    subparsers = parser.add_subparsers()

    parser_update = subparsers.add_parser("update", help="Update all branches.")
    parser_update.set_defaults(func=update)

    args = parser.parse_args()
    if args.func:
        sys.exit(args.func(args))
