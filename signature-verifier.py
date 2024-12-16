import requests
import os
import concurrent.futures

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]

unsigned_repo = set()


def get_all_public_repo():
    ret = {}
    i = 1
    while True:
        res = requests.get(
            f"  https://api.github.com/user/repos",
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


def get_commits(repo):
    commit_map = {}
    print(f"::debug::Checking {repo}...")
    i = 1
    cnt = {"unverified": 0, "all": 0}
    while True:
        res = requests.get(
            f"https://api.github.com/repos/{repo}/commits",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {TOKEN}",
            },
            params={
                "type": "all",
                "per_page": 100,
                "page": i,
                "committer": USER,
            },
        ).json()
        print(f"::debug::Gather committer commits from {repo}/{i}...")
        if not isinstance(res, list):
            raise Exception(f"failed to gather {repo}: {res}")
            break
        elif len(res) == 0:
            break
        for item in res:
            commit_map[item["sha"]] = item.get("commit", {}).get("verification", {}).get("verified", True)
        i += 1
    i = 1
    while True:
        res = requests.get(
            f"https://api.github.com/repos/{repo}/commits",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {TOKEN}",
            },
            params={
                "type": "all",
                "per_page": 100,
                "page": i,
                "author": USER,
            },
        ).json()
        print(f"::debug::Gather author commits from {repo}/{i}...")
        if not isinstance(res, list):
            raise Exception(f"failed to gather {repo}: {res}")
            break
        elif len(res) == 0:
            break
        for item in res:
            commit_map[item["sha"]] = item.get("commit", {}).get("verification", {}).get("verified", True)
        i += 1
    cnt["unverified"] = sum(1 for value in commit_map.values() if value is False)
    cnt["all"] = len(commit_map)
    if cnt["unverified"] != 0:
        print(f"::warning::{repo} has unsigned commits!")
        unsigned_repo.add(repo)
    return cnt


def main():
    repos = get_all_public_repo()
    commit_check_result = {}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_repo1 = {
            executor.submit(get_commits, repo): repo for repo in repos.keys()
        }
        for future in concurrent.futures.as_completed(future_to_repo1):
            repo = future_to_repo1[future]
            try:
                result = future.result()
                commit_check_result[repo] = result
            except Exception as e:
                print(f"::error::Error fetching commits for {repo}: {e}")

    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
        print(f"# Verification Report on the Signatures of Commits\r\n", file=fh)
        if len(unsigned_repo) == 0:
            print(
                ":tada: All commits have been properly signed and are in compliance with the signature verification requirements. :tada:\r\n"
            )
            return

        low_risk = []
        dangerous = []

        for repo in unsigned_repo:
            if (
                repos[repo]["owner"]["login"] == USER
                or commit_check_result[repo]["unverified"]
                < commit_check_result[repo]["all"]
            ):
                low_risk.append(repo)
            else:
                dangerous.append(repo)

        print(
            "The following repositories contain unsigned or unverified signatures. :question:\r\n",
            file=fh,
        )
        print("\r\n## Low Risk :white_check_mark:\r\n", file=fh)
        print(
            "The repository is either owned by me or contains commits that have been signed previously.\r\n",
            file=fh,
        )
        if len(low_risk) > 0:
            print(
                "\r\n".join(
                    map(
                        lambda repo: f"* **{repo}**: Total of `{commit_check_result[repo]['all']}` commits, including `{commit_check_result[repo]['unverified']}` commits that are unsigned/unverified.",
                        low_risk,
                    )
                ),
                file=fh,
            )
        else:
            print("> Nothing here. :spiral_notepad:", file=fh)
        print("\r\n## Dangerous :radioactive:\r\n", file=fh)
        print(
            "The repository is not under my control, and all commits are either unsigned or unverified.\r\n",
            file=fh,
        )
        if len(dangerous) > 0:
            print(
                "\r\n".join(
                    map(
                        lambda repo: f"* **{repo}**: Total of `{commit_check_result[repo]['all']}` commits, including `{commit_check_result[repo]['unverified']}` commits that are unsigned/unverified.",
                        dangerous,
                    )
                ),
                file=fh,
            )
        else:
            print("> Nothing here. :spiral_notepad:", file=fh)
        print("\r\n---\r\n", file=fh)
        print("End of Report", file=fh)


if __name__ == "__main__":
    main()
