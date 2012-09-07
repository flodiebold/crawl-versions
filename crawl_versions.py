#!/usr/bin/env python

import argparse, os, os.path, subprocess, yaml, traceback, sys, shutil, stat
import save_reader
from common import *

source_address = "git://gitorious.org/crawl/crawl.git"

def call_git(command, *args, **kwargs):
    """Simple wrapper function for running git commands."""
    if kwargs.get("output", False):
        return subprocess.check_output(["git", command] + list(args))
    else:
        subprocess.check_call(["git", command] + list(args))

def init_source():
    """Makes sure the crawl source is present, returns the directory."""
    source_dir = os.path.join(base_dir, "src")
    if os.path.isdir(source_dir): return source_dir
    print "Downloading crawl source..."
    call_git("clone", source_address, source_dir)
    return source_dir

def load_config():
    """Loads the version config files."""
    config_dir = os.path.join(base_dir, "crawl-versions.d")
    if not os.path.isdir(config_dir):
        print "Couldn't find the configuration directory!"
        print "(Maybe copy from crawl-versions.d.example?)"
        sys.exit(1)
    versions = []
    for filename in os.listdir(config_dir):
        if not filename.endswith(".yml"): continue
        with open(os.path.join(config_dir, filename)) as f:
            contents = f.read()
        for data in yaml.load_all(contents):
            versions.append(data)
    return versions

def load_base_config():
    """Loads the config.yml file."""
    config_file_name = os.path.join(base_dir, "config.yml")
    with open(config_file_name, "r") as f:
        contents = f.read()
        return yaml.load(contents)

def get_path(key, config, version, **kwargs):
    template = version.get(key, None)
    template = template or config.get("defaults", {}).get(key, None)
    return template and template.format(name=version["name"], **kwargs)

def _find_major_version():
    line_start = "#define TAG_MAJOR_VERSION"
    with open("tag-version.h", "r") as f:
        for l in f.readlines():
            if l.startswith(line_start):
                mv = int(l[len(line_start):].strip())
                return mv
    return None

def compile_revision(version_name, revision):
    """Compiles the given revision for the given version.
    Returns the major version tag."""
    common_dir = os.path.join(get_crawl_dir(), version_name)
    revision_dir = os.path.join(common_dir, revision)
    if os.path.isdir(revision_dir): return None # Already present
    
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
        return _find_major_version()
    finally:
        os.chdir(old_cwd)

def _update_version(version, config):
    old_cwd = os.getcwd()
    try:
        # Check latest revision and compile (if necessary)
        latest = call_git("describe", version["branch"], output=True).strip()
        present = revision_present(version["name"], latest)
        print "Latest", version["name"], "is", latest

        major_version = compile_revision(version["name"], latest)

        # Symlink latest to the newest version
        version_dir = os.path.join(get_crawl_dir(), version["name"])
        os.symlink(latest, os.path.join(version_dir, "latest.new"))
        os.rename(os.path.join(version_dir, "latest.new"),
                  os.path.join(version_dir, "latest"))

        # Symlink latest-{major_version} to this version
        if major_version:
            os.symlink(latest, os.path.join(version_dir, "latest.new"))
            os.rename(os.path.join(version_dir, "latest.new"),
                      os.path.join(version_dir, "latest-{}".format(major_version)))

        # Create runner script
        bin_dir = os.path.join(base_dir, "bin")
        if not os.path.isdir(bin_dir): os.makedirs(bin_dir)
        bin_file = os.path.join(bin_dir, version["name"])
        runner_script = os.path.join(script_dir, "crawl_runner.py")
        if not os.path.isfile(bin_file):
            with open(bin_file, "w") as f:
                f.write("#!/bin/sh\n")
                f.write("exec " + runner_script + ' "' + version["name"] + '" "$@"\n')
            os.chmod(bin_file, 0755)

        # Link logfiles, milestones and rc dirs
        os.chdir(base_dir)
        scoring_link_dir = get_path("scoring-link-dir", config, version)
        if scoring_link_dir:
            def do_link(filename, folder):
                if not os.path.isdir(scoring_link_dir):
                    os.makedirs(scoring_link_dir)
                os.symlink(os.path.abspath(os.path.join(version_dir, folder, filename)),
                           os.path.join(scoring_link_dir, filename + ".new"))
                os.rename(os.path.join(scoring_link_dir, filename + ".new"),
                          os.path.join(scoring_link_dir, filename))
            for (file_type, folder) in [("logfile", "shared"),
                                        ("milestones", "saves")]:
                do_link(file_type, folder)
                for game_mode in version.get("game-modes", []):
                    do_link(file_type + "-" + game_mode, folder)

        rcfile_dir_link = get_path("rcfile-dir-link", config, version)
        rcfile_dir = get_path("rcfile-dir", config, version)
        if rcfile_dir_link and rcfile_dir:
            temp_filename = rcfile_dir_link + ".new"
            os.symlink(os.path.abspath(rcfile_dir), temp_filename)
            os.rename(temp_filename, rcfile_dir_link)

        return True
    except:
        print "Update of", version["name"], "failed!"
        traceback.print_exc()
        return False
    finally:
        os.chdir(old_cwd)

def update(args):
    config = load_base_config()
    versions = load_config()
    source_dir = init_source()
    os.chdir(source_dir)
    call_git("fetch", "--all")
    success = True
    for version in versions:
        success = success and _update_version(version, config)
    return 0 if success else 1

def savefile_revision(save_file):
    """Determines the crawl revision with which the given save file was made."""
    with save_reader.Package(save_file) as p:
        p.read_chr_chunk()
        return p.crawl_version

def savefile_statistics(version):
    """Counts save files for each revision of the version."""
    save_dir = os.path.join(get_crawl_dir(), version["name"], "saves")
    stats = dict()
    for game_mode in [None] + game_modes:
        mode_save_dir = os.path.join(save_dir, game_mode) if game_mode else save_dir
        if not os.path.isdir(mode_save_dir): continue
        for save_file in os.listdir(mode_save_dir):
            if not save_file.endswith(".cs"): continue
            rev = savefile_revision(os.path.join(mode_save_dir, save_file))
            stats[rev] = 1 + stats.get(rev, 0)
    return stats

def installed_revisions(version):
    """Returns a list of all revisions installed for a given version."""
    version_dir = os.path.join(get_crawl_dir(), version["name"])
    revisions = []
    for path in os.listdir(version_dir):
        if path in ["saves", "shared"]: continue
        if path.startswith("latest"): continue
        revisions.append(path)
        
    revisions.sort()
    return revisions

def find_crawl_processes():
    """Searches for running processes of crawl binaries managed by this script."""
    crawl_dir = os.path.realpath(get_crawl_dir())
    for pid in os.listdir("/proc"):
        if not pid.isdigit(): continue
        try:
            exe_file = os.path.realpath(os.path.join("/proc", pid, "exe"))
        except OSError:
            continue

        if exe_file.startswith(crawl_dir):
            rel_path = os.path.relpath(exe_file, crawl_dir)
            (version_name, revision) = rel_path.split(os.path.sep)[0:2]
            yield (pid, version_name, revision)
    
def process_statistics():
    """Counts the processes running for each revision of each version."""
    stats = dict()
    for pid, version_name, rev in find_crawl_processes():
        version_stats = stats.get(version_name, dict())
        stats[version_name] = version_stats
        version_stats[rev] = 1 + version_stats.get(rev, 0)
    return stats

def list_revisions(args):
    config = load_config()
    if args.versions:
        versions = args.versions
    else:
        versions = [v["name"] for v in config]

    process_stats = process_statistics()

    for version in config:
        if version["name"] not in versions: continue

        savefile_stats = savefile_statistics(version)
        v_process_stats = process_stats.get(version["name"], dict())
        revisions = installed_revisions(version)

        print version["name"], "revisions:"

        for rev in revisions:
            # Check if blacklisted
            exec_file = os.path.join(get_crawl_dir(), version["name"], rev, "bin", "crawl")
            blacklisted = not os.access(exec_file, os.X_OK)

            save_count = savefile_stats.get(rev, 0)
            process_count = v_process_stats.get(rev, 0)
            print "{0} ({1} saves, {2} processes{3})".format(rev, save_count, process_count, ", blacklisted" if blacklisted else "")
            if rev in savefile_stats: del savefile_stats[rev]
            if rev in v_process_stats: del v_process_stats[rev]

        other_saves = sum(savefile_stats.values())
        if other_saves:
            print other_saves, "other savegames"

        other_processes = sum(v_process_stats.values())
        if other_processes:
            print other_processes, "other processes"
        
        print

def blacklist(args):
    config = load_config()
    if args.versions:
        versions = args.versions
    else:
        versions = [v["name"] for v in config]

    source_dir = init_source()
    os.chdir(source_dir)
    try:
        rev_range_parsed = call_git("rev-parse", *args.data, output=True)
    except subprocess.CalledProcessError:
        sys.exit(1)
    revs = rev_range_parsed.split()

    if any(rev.startswith("^") for rev in revs):
        ranges = True
    else:
        ranges = args.ranges

    if ranges:
        revs = call_git("rev-list", *revs, output=True).split()

    for version in config:
        if version["name"] not in versions: continue

        revisions = installed_revisions(version)
        latest = os.readlink(os.path.join(get_crawl_dir(), version["name"], "latest"))
        blacklist = []
        for rev in revisions:
            rev_id = call_git("rev-parse", rev, output=True).strip()
            if rev_id not in revs: continue
            if rev == latest:
                print "This would blacklist the latest version of {0} ({1})! Aborting.".format(version["name"], rev)
                sys.exit(1)

            blacklist.append(rev)

        for rev in blacklist:
            print "Blacklisting {0}...".format(rev)
            exec_file = os.path.join(get_crawl_dir(), version["name"], rev, "bin", "crawl")
            # Remove exec bit
            mode = os.stat(exec_file).st_mode
            os.chmod(exec_file, mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
            

def remove_revision(version_name, revision):
    """Deletes a revision."""
    revision_dir = os.path.join(get_crawl_dir(), version_name, revision)
    shutil.rmtree(revision_dir)

def clean(args):
    config = load_config()
    if args.versions:
        versions = args.versions
    else:
        versions = [v["name"] for v in config]

    process_stats = process_statistics()

    for version in config:
        if version["name"] not in versions: continue

        savefile_stats = savefile_statistics(version)
        v_process_stats = process_stats.get(version["name"], dict())
        revisions = installed_revisions(version)

        latest = os.readlink(os.path.join(get_crawl_dir(), version["name"], "latest"))

        print "Cleaning {0}...".format(version["name"])

        for rev in revisions:
            save_count = savefile_stats.get(rev, 0)
            process_count = v_process_stats.get(rev, 0)
            if save_count > 0 or process_count > 0: continue
            if latest == rev: continue
            print "Removing revision {0}...".format(rev)
            remove_revision(version["name"], rev)

        print

def init_user(username):
    config = load_base_config()
    versions = load_config()
    for version in versions:
        def path(key):
            p = get_path(key, config, version, username=username)
            if p and not os.path.isdir(p): os.makedirs(p)
        path("rcfile-dir")
        path("dgl-inprogress-dir")
        path("ttyrec-dir")
        rcfile_dir = get_path("rcfile-dir", config, version, username=username)
        rcfile_path = os.path.join(rcfile_dir, username + ".rc")
        if not os.path.isfile(rcfile_path):
            default_rc = os.path.join(get_crawl_dir(), version["name"],
                                      "latest", "data", "settings", "init.txt")
            shutil.copyfile(default_rc, rcfile_path)
    return 0

if __name__ == "__main__":
    if os.path.basename(sys.argv[0]) == "init-user":
        sys.exit(init_user(sys.argv[1]))

    parser = argparse.ArgumentParser(description="Manage crawl versions.")
    subparsers = parser.add_subparsers()

    parser_update = subparsers.add_parser("update", help="Update all branches.")
    parser_update.set_defaults(func=update)

    parser_list = subparsers.add_parser("list", help="List revisions.")
    parser_list.set_defaults(func=list_revisions)
    parser_list.add_argument("-v", "--version", dest="versions", action="append")

    parser_blacklist = subparsers.add_parser("blacklist", help="Blacklist revisions.")
    parser_blacklist.set_defaults(func=blacklist, ranges=False)
    parser_blacklist.add_argument("data", nargs="+")
    parser_blacklist.add_argument("-v", "--version", dest="versions", action="append")
    parser_blacklist.add_argument("-r", "--ranges", dest="ranges", const=True, action="store_const")
    parser_blacklist.add_argument("--revisions", dest="ranges", const=False, action="store_const")

    parser_clean = subparsers.add_parser("clean", help="Remove unused versions and clear caches.")
    parser_clean.set_defaults(func=clean)
    parser_clean.add_argument("-v", "--version", dest="versions", action="append")

    args = parser.parse_args()
    if args.func:
        sys.exit(args.func(args))
