#!/usr/bin/env python

import os, os.path, sys, subprocess
import save_reader, getch
from common import *

def wait_key():
    getch.getch()

def yes_no():
    answer = getch.getch()
    return ord(answer) not in set([ord("n"), ord("N"), 27])

def send_webtiles_dialog(html):
    import json
    print json.dumps({"msg": "layer", "layer": "crt"})
    print json.dumps({"msg": "show_dialog", "html": html})

def close_webtiles_dialog():
    import json
    print json.dumps({"msg": "hide_dialog"})

def parse_args():
    version_name = sys.argv[1]
    webtiles_compat = "-await-connection" in sys.argv
    name_index = sys.argv.index("-name")
    name = sys.argv[name_index + 1]
    return (version_name, name, webtiles_compat)

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
    version_name, name, webtiles_compat = parse_args()
    latest = os.readlink(os.path.join(get_crawl_dir(), version_name, "latest"))
    save_file = os.path.join(get_crawl_dir(), version_name, "saves", name + ".cs")
    if os.path.isfile(save_file):
        with save_reader.Package(save_file) as p:
            p.read_chr_chunk()
            revision = p.crawl_version
    else:
        revision = latest

    if not revision_present(version_name, revision):
        if not webtiles_compat: print "Revision unavailable! Forcing upgrade."
        revision = latest
    
    if revision != latest:
        changelog = get_changelog(revision, latest)
        if not webtiles_compat:
            print "A new version is available! Changelog:"
            print changelog
        else:
            dialog_html = "<h3>A new version is available!</h3>"
            dialog_html += """
<p>
  Changelog:<br>
  <div style='width:100%;max-height:250px;overflow-y:auto;overflow-x:hidden;'>
    <pre style='width:100%;font-size:smaller;color:lightgray'>{0}</pre>
  </div>
</p>""".format(changelog.replace("<", "&lt;").replace(">", "&gt;"))
        ask = True
        # Check if blacklisted
        exec_path = os.path.join(get_crawl_dir(), version_name, revision, "bin", "crawl")
        if not os.access(exec_path, os.X_OK):
            ask = False

        if ask:
            if not webtiles_compat:
                print "Upgrade? [Y/n]"
            else:
                dialog_html += """
<input type='button' class='button' data-key='N' value="Don't upgrade" style='float:right;'>
<input type='button' class='button' data-key='Y' value='Continue' style='float:right;'>
"""
                send_webtiles_dialog(dialog_html)
            upgrade = yes_no()
        else:
            if not webtiles_compat:
                print "Upgrading. Press a key..."
            else:
                dialog_html += """
<input type='button' class='button' data-key=' ' value='Continue' style='float:right;'>"""
                send_webtiles_dialog(dialog_html)
            wait_key()
            upgrade = True

        if webtiles_compat: close_webtiles_dialog()

        if upgrade:
            revision = latest

    if not webtiles_compat: print "Running version", revision
    exec_path = os.path.join(get_crawl_dir(), version_name, revision, "bin", "crawl")
    parameters = [exec_path] + sys.argv[2:]
    os.execv(exec_path, parameters)
