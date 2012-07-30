#!/bin/env python

import os, os.path, sys, subprocess
import save_reader, getch
from common import *

def ask_upgrade():
    print "A new version is available! Upgrade? [y/N]"
    answer = getch.getch()
    return ord(answer) not in set([ord("n"), ord("N"), 27])

def parse_args():
    version_name = sys.argv[1]
    name_index = sys.argv.index("-name")
    name = sys.argv[name_index + 1]
    return (version_name, name)

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
        ask = True
        if ask:
            upgrade = ask_upgrade()
        else:
            upgrade = True

        if upgrade:
            revision = latest
        
    print "Running version", revision
    exec_path = os.path.join(get_crawl_dir(), version_name, revision, "bin", "crawl")
    parameters = [exec_path] + sys.argv[2:]
#    os.execv(exec_path, parameters)
