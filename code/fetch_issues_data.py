import requests
import time
import json

# =========================
# CONFIG
# =========================
OWNER = "abhigyanpatwari"
REPO = "GitNexus"
TOKEN = "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"

BASE_URL = f"https://api.github.com/repos/{OWNER}/{REPO}"

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json"
}

# =========================
# 1. FETCH LABELS
# =========================
def fetch_labels():
    url = f"{BASE_URL}/labels"
    response = requests.get(url, headers=HEADERS)
    labels = response.json()

    # Save to JSON
    with open("labels.json", "w") as f:
        json.dump(labels, f, indent=4)

    print("✅ Saved labels.json")
    return labels


# =========================
# 2. FETCH ISSUES
# =========================
def fetch_all_issues():
    all_issues = []
    page = 1

    while True:
        url = f"{BASE_URL}/issues"
        params = {
            "state": "all",
            "per_page": 100,
            "page": page
        }

        response = requests.get(url, headers=HEADERS, params=params)
        issues = response.json()

        # Stop when no more data
        if not issues:
            break

        # Remove PRs
        issues = [i for i in issues if "pull_request" not in i]

        print(f"Fetched page {page}, issues: {len(issues)}")

        for issue in issues:
            all_issues.append({
                "id": issue["id"],
                "number": issue["number"],
                "title": issue["title"],
                "body": issue["body"],
                "labels": [l["name"] for l in issue["labels"]],
                "state": issue["state"],
                "created_by": issue["user"]["login"],
                "created_at": issue["created_at"]
            })

        page += 1

    # Save all issues
    with open("issues.json", "w") as f:
        json.dump(all_issues, f, indent=4)

    print(f"\n✅ Total issues fetched: {len(all_issues)}")

    return all_issues


# =========================
# 3. FETCH WHO CLOSED ISSUE
# =========================
def get_closed_by(issue_number):
    url = f"{BASE_URL}/issues/{issue_number}/events"
    response = requests.get(url, headers=HEADERS)
    events = response.json()

    for event in events:
        if event["event"] == "closed":
            return event["actor"]["login"]

    return None


# =========================
# 4. BUILD RESOLVER DATA
# =========================
def build_resolver_data(issues):
    resolver_data = []

    for issue in issues:
        closed_by = None

        if issue["state"] == "closed":
            closed_by = get_closed_by(issue["number"])
            time.sleep(0.5)  # avoid rate limits

        resolver_data.append({
            "issue_number": issue["number"],
            "created_by": issue["created_by"],
            "closed_by": closed_by
        })

    # Save to JSON
    with open("resolvers.json", "w") as f:
        json.dump(resolver_data, f, indent=4)

    print("✅ Saved resolvers.json")


# =========================
# RUN ALL
# =========================
if __name__ == "__main__":
    labels = fetch_labels()
    issues = fetch_all_issues()
    build_resolver_data(issues)