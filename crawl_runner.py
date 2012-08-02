#!/bin/env python

import os, os.path, sys, subprocess
import save_reader, getch
from common import *

def wait_key():
    print "Upgrading. Press a key..."
    getch.getch()

def ask_upgrade():
    print "Upgrade? [Y/n]"
    answer = getch.getch()
    return ord(answer) not in set([ord("n"), ord("N"), 27])

def parse_args():
    version_name = sys.argv[1]
    name_index = sys.argv.index("-name")
    name = sys.argv[name_index + 1]
    return (version_name, name)

def get_changelog(from_rev, to_rev):
    source_dir = os.path.join(base_dir, "src")
    changelog_cache = os.path.join(base_dir, "changelogs")
    changelog_file = os.path.join(changelog_cache, from_rev + ".." + to_rev + ".txt")
    if not os.path.isdir(changelog_cache): os.makedirs(changelog_cache)
    if not os.path.isfile(changelog_file):
        old_cwd = os.getcwd()
        try:
            os.chdir(source_dir)
            with open(changelog_file, "wb") as f:
                command = ["git", "log", "--reverse", from_rev + ".." + to_rev]
                subprocess.check_call(command, stdout=f)
        finally:
            os.chdir(old_cwd)

    with open(changelog_file, "r") as f:
        changelog = f.read()

    return changelog

if __name__ == "__main__":
    version_name, name = parse_args()
    latest = os.readlink(os.path.join(get_crawl_dir(), version_name, "latest"))
    save_file = os.path.join(get_crawl_dir(), version_name, "saves", name + ".cs")
    if os.path.isfile(save_file):
        with save_reader.Package(save_file) as p:
            p.read_chr_chunk()
            revision = p.crawl_version
    else:
        revision = latest

    if not revision_present(version_name, revision):
        print "Revision unavailable! Forcing upgrade."
        revision = latest
    
    if revision != latest:
        print "A new version is available! Changelog:"
        print get_changelog(revision, latest)
        ask = True
        # Check if blacklisted
        exec_path = os.path.join(get_crawl_dir(), version_name, revision, "bin", "crawl")
        if not os.access(exec_path, os.X_OK):
            ask = False
        if ask:
            upgrade = ask_upgrade()
        else:
            wait_key()
            upgrade = True

        if upgrade:
            revision = latest
        
    print "Running version", revision
    exec_path = os.path.join(get_crawl_dir(), version_name, revision, "bin", "crawl")
    parameters = [exec_path] + sys.argv[2:]
    os.execv(exec_path, parameters)
