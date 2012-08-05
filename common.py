import os, os.path

script_dir = os.path.realpath(os.path.dirname(__file__))
base_dir = script_dir

game_modes = ["sprint", "zotdef"]

def get_crawl_dir():
    return os.path.join(base_dir, "crawl")

def revision_present(version, revision):
    return os.path.isdir(os.path.join(get_crawl_dir(), version, revision))
