import requests
import os
import concurrent.futures

USER = os.environ["GH_USER"]

unsigned_repo = set()


def get_all_public_repo():
    ret = {}
    i = 1
    while True:
        res = requests.get(
            f"https://api.github.com/users/{USER}/repos",
            headers={
                "Accept": "application/vnd.github+json",
            },
            params={"type": "all", "per_page": 100, "page": i},
        ).json()
        if isinstance(res, list) and len(res) > 0:
            ret.update({item["full_name"]: item for item in res})
        else:
            break
        i += 1

    return ret


def get_commits(repo, type):
    print(f"::debug::Checking {repo}...")
    i = 1
    cnt = {"unverified": 0, "all": 0}
    while True:
        res = requests.get(
            f"https://api.github.com/repos/{repo}/commits",
            headers={
                "Accept": "application/vnd.github+json",
            },
            params={
                "type": "all",
                "per_page": 100,
                "page": i,
                "author": USER,
                "committer": USER,
            },
        ).json()
        print(f"::debug::Gather commits from {repo}/{i}...")
        if not isinstance(res, list) or len(res) == 0:
            break
        cnt["unverified"] += sum(
            not x.get("commit", {}).get("verification", {}).get("verified", True)
            for x in res
        )
        cnt["all"] += len(res)
        i += 1
    if cnt["unverified"] != 0:
        print(f"::warning::{repo} have unsigned {type} commits!")
        unsigned_repo.add(repo)
    return cnt


def main():

    repos = get_all_public_repo()
    commit_check_result = {}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_repo1 = {
            executor.submit(get_commits, repo, "author"): repo for repo in repos.keys()
        }

        for future in concurrent.futures.as_completed(future_to_repo1):
            repo = future_to_repo1[future]
            try:
                result = future.result()
                commit_check_result[repo] = result
            except Exception as e:
                print(f"Error fetching author commits for {repo}: {e}")

    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
        print(f"# Verification Report on the Signatures of Commits", file=fh)
        if len(unsigned_repo) == 0:
            print(
                ":tada: All commits have been properly signed and are in compliance with the signature verification requirements. :tada:"
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
            "The following repositories contain unsigned or unverified signatures.",
            file=fh,
        )
        print("## Low Risk :white_check_mark:", file=fh)
        print(
            "The repository is either owned by me or contains commits that have been signed previously.",
            file=fh,
        )
        print(
            "\r\n".join(
                map(
                    lambda repo: f"* {repo} (author: {commit_check_result[repo]['unverified']}/{commit_check_result[repo]['all']})",
                    low_risk,
                )
            ),
            file=fh,
        )
        print("---", file=fh)
        print("## Dangerous :radioactive:", file=fh)
        print(
            "The repository is not under my control, and all commits are either unsigned or unverified.",
            file=fh,
        )
        print(
            "\r\n".join(
                map(
                    lambda repo: f"* {repo} (author: {commit_check_result[repo]['unverified']}/{commit_check_result[repo]['all']})",
                    dangerous,
                )
            ),
            file=fh,
        )


if __name__ == "__main__":
    main()
