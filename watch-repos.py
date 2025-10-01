import os
import concurrent.futures
import requests

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]

unsigned_repo = set()


def get_all_public_repo():
    ret = {}
    i = 1
    while True:
        res = requests.get(
            f"https://api.github.com/user/repos",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {TOKEN}",
            },
            params={"visibility": "public", "per_page": 100, "page": i},
        ).json()
        if isinstance(res, list) and len(res) > 0:
            ret.update({item["full_name"]: item for item in res})
        else:
            break
        i += 1

    return ret



def get_all_watched_repo():
    ret = {}
    i = 1
    while True:
        res = requests.get(
            f"https://api.github.com/users/{USER}/subscriptions",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28"
            },
            params={"per_page": 100, "page": i},
        ).json()
        if isinstance(res, list) and len(res) > 0:
            ret.update({item["full_name"]: item for item in res})
        else:
            break
        i += 1

    return ret

def get_all_need_watch_repo():
    ret = set()
    public_repos = get_all_public_repo().keys()
    watched_repos = get_all_watched_repo().keys()
    print(watched_repos)
    for repo in public_repos:
        if repo not in watched_repos:
            ret.add(repo)

    return ret

def watch_repo(repo):
    res = requests.put(f"https://api.github.com/repos/{repo}/subscription",
                       headers={
                           "Accept": "application/vnd.github+json",
                           "Authorization": f"Bearer {TOKEN}",
                           "X-GitHub-Api-Version": "2022-11-28",
                       },
                       json={"subscribed": True, "ignored": False})

    return res

def main():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_repo1 = {
            executor.submit(watch_repo, repo): repo for repo in get_all_need_watch_repo()
        }
        for future in concurrent.futures.as_completed(future_to_repo1):
            repo = future_to_repo1[future]
            try:
                result = future.result()
                if not result.ok:
                   print(f"::error::Error watch for {repo}: {result.text}", flush=True)
            except Exception as e:
                print(f"::error::Error watch for {repo}: {e}", flush=True)


if __name__ == "__main__":
    main()
