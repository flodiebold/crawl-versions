import os, os.path

base_dir = os.getcwd()

def get_crawl_dir():
    return os.path.join(base_dir, "crawl")

def revision_present(version, revision):
    return os.path.isdir(os.path.join(get_crawl_dir(), version, revision))
