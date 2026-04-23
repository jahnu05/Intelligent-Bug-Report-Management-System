import requests
import json
import time

# =========================
# CONFIG
# =========================
OWNER = "mkriti04"
REPO = "BTP-Spring-2025"
TOKEN = "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"

BASE_URL = f"https://api.github.com/repos/{OWNER}/{REPO}"

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json"
}

# =========================
# 1. FETCH CONTRIBUTORS
# =========================
def fetch_contributors():
    contributors = []
    page = 1

    while True:
        url = f"{BASE_URL}/contributors"
        params = {"per_page": 100, "page": page}

        r = requests.get(url, headers=HEADERS, params=params)
        data = r.json()

        if not data:
            break

        contributors.extend(data)
        print(f"Fetched contributors page {page}")

        page += 1

    with open("contributors.json", "w") as f:
        json.dump(contributors, f, indent=4)

    print(f"✅ Total contributors: {len(contributors)}")
    return contributors


# =========================
# 2. FETCH COMMITS PER CONTRIBUTOR
# =========================
def fetch_commits_for_contributor(username):
    commits = []
    page = 1

    while True:
        url = f"{BASE_URL}/commits"
        params = {
            "author": username,
            "per_page": 100,
            "page": page
        }

        r = requests.get(url, headers=HEADERS, params=params)
        data = r.json()

        if not data:
            break

        for c in data:
            sha = c["sha"]

            commits.append({
                "sha": sha,
                "author": username,
                "message": c["commit"]["message"],
                "date": c["commit"]["author"]["date"],
                "patch_url": f"https://github.com/{OWNER}/{REPO}/commit/{sha}.patch",
                "diff_url": f"https://github.com/{OWNER}/{REPO}/commit/{sha}.diff"
            })

        print(f"{username}: page {page}, commits {len(data)}")

        page += 1
        time.sleep(0.2)  # avoid rate limits

    return commits


# =========================
# 3. MAIN PIPELINE
# =========================
def build_commit_dataset():
    contributors = fetch_contributors()

    all_commits = []

    # limit for testing (remove later)
    contributors = contributors[:5]

    for c in contributors:
        username = c["login"]

        print(f"\nFetching commits for: {username}")

        commits = fetch_commits_for_contributor(username)
        all_commits.extend(commits)

    with open("commits.json", "w") as f:
        json.dump(all_commits, f, indent=4)

    print(f"\n✅ Total commits stored: {len(all_commits)}")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    build_commit_dataset()