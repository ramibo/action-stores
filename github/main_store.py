
import os
import sys

from typing import Optional
from pathlib import Path
from pydantic import BaseModel
import kubiya
import requests

from typing import List, Dict, Any
import kubiya
from github import Github
from os import environ

store = kubiya.ActionStore("github", "0.1.0")
store.uses_secrets(["GITHUB_PERSONAL_ACCESS_TOKEN"])


# orgprefix = orgname + "/"


def get_orgname(store):
    return os.environ.get("GITHUB_ORGANIZATION_NAME",'kubi-org')


def get_token(store):
    return store.secrets.get("GITHUB_PERSONAL_ACCESS_TOKEN", 'token')


def get_orgprefix(store):
    return get_orgname(store) + "/"


def login(store) -> Github:
    return Github(store.secrets["GITHUB_PERSONAL_ACCESS_TOKEN"])

@store.kubiya_action()
def get_org_repos_names(input=None) -> List[str]:
    orgname = get_orgname(store)
    repos = [
        repo.name
        for repo in login(store).get_organization(orgname).get_repos()
    ]
    return sorted(repos, key=lambda x: x.lower())

@store.kubiya_action()
def get_org_repos_names_with_workflows(input=None) -> List[str]:
    orgname = get_orgname(store)

    repos = [
        repo.name
        for repo in login(store).get_organization(orgname).get_repos()
    ]

    repos_with_workflow=[]
    orgprefix = get_orgprefix(store)

    for repo_name in repos:
        repo = login(store).get_repo(orgprefix + repo_name)
        workflows= [action.name+"/"+str(action.id) for action in repo.get_workflows()]
        if workflows:
            repos_with_workflow.append(repo_name)

    if repos_with_workflow:
        return sorted(repos_with_workflow, key=lambda x: x.lower())
    else:
        return False

@store.kubiya_action()
def get_org_repos_names_with_workflows_in_progress(input=None) -> List[str]:
    orgname = get_orgname(store)

    repos = [
        repo.name
        for repo in login(store).get_organization(orgname).get_repos()
    ]

    repos_with_workflow_in_progress=[]
    orgprefix = get_orgprefix(store)

    for repo_name in repos:
        repo = login(store).get_repo(orgprefix + repo_name)
        workflows_ids= [str(action.id) for action in repo.get_workflows()]
        if workflows_ids:
            for id in workflows_ids:
                workflow_runs=repo.get_workflow(int(id)).get_runs()
                for run in workflow_runs:
                    if run.status=="in_progress" and repo_name not in repos_with_workflow_in_progress:
                        repos_with_workflow_in_progress.append(repo_name)

    if repos_with_workflow_in_progress:
        return sorted(repos_with_workflow_in_progress, key=lambda x: x.lower())
    else:
        return False

@store.kubiya_action()
def get_all_org_repos_open_prs(input=None) -> Dict[str, Any]:
    orgname = get_orgname(store)
    repos = [
        repo.name
        for repo in login(store).get_organization(orgname).get_repos()
    ]

    all_prs = []
    for repo_name in repos:
        orgprefix = get_orgprefix(store)
        state = "open"
        repo = login(store).get_repo(orgprefix + repo_name)

        for pr in repo.get_pulls(state='open'):
            all_prs.append({
                "user": pr.user.login,
                "title": pr.title,
                "number": pr.number,
                "created_at": pr.created_at.isoformat(),
                "head_branch": pr.head.ref,
                "target_branch": pr.base.ref,
                "repo_name": repo.full_name})

    return all_prs

@store.kubiya_action()
def get_open_prs(params: Dict) -> List[Dict[str, Any]]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    limit = params.get("limit", 10)
    state = params.get("state", "open")
    repo = login(store).get_repo(orgprefix + repo_name)
    return [
        {
            "user": pr.user.login,
            "title": pr.title,
            "number": pr.number,
            "created_at": pr.created_at.isoformat(),
            "head_branch": pr.head.ref,
            "target_branch": pr.base.ref,
            "repo_name": repo.full_name
        }
        for pr in repo.get_pulls(state='open')
        # for pr in repo.get_pulls(state='open')[:limit]
    ]


@store.kubiya_action()
def get_pr_ref(input=None) -> Dict[str, Any]:
    orgname = get_orgname(store)
    repos = [
        repo.name
        for repo in login(store).get_organization(orgname).get_repos()
    ]

    prs_ref = []
    for repo_name in repos:
        orgprefix = get_orgprefix(store)
        repo = login(store).get_repo(orgprefix + repo_name)

        for pr in repo.get_pulls(state='all'):
            prs_ref.append(f"{repo.full_name}/{pr.number}/{pr.title}")

    return prs_ref


@store.kubiya_action()
def pr_details_from_ref(params: Dict) -> Dict[str, Any]:
    orgprefix = get_orgprefix(store)
    ref = params["ref"]
    repo_name = ref.split('/')[1]
    pr_number = int(ref.split('/')[2])
    repo = login(store).get_repo(orgprefix + repo_name)
    data = repo.get_pull(number=pr_number).raw_data

    return {"state": data['state'],
            "id": data['id'],
            "html_url": data['html_url'],
            "title": data['title']}


@store.kubiya_action()
def grant_access_to_repo(params: Dict):
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    named_user = params["named_user"]

    # First, check if the user exists on GitHub using the GitHub API
    response = requests.get(f"https://api.github.com/users/{named_user}")

    # If the status code is 404, the user does not exist
    if response.status_code == 404:
        return f"The user {named_user} does not exist on GitHub."
    else:
        login(store).get_repo(orgprefix + repo_name).add_to_collaborators(named_user)
        return f"The user {named_user} exists on GitHub.An invitation to {repo_name} was sent to the user"


@store.kubiya_action()
def remove_access_from_repo(params: Dict):
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    named_user = params["named_user"]

    # Remove any existing invitations for the user from the repo
    invitations = login(store).get_repo(orgprefix + repo_name).get_pending_invitations()
    for invit in invitations:
        if invit.invitee.login == named_user:
            test = login(store).get_repo(orgprefix + repo_name).remove_invitation(invit.id)
            pass

    # Remove the user as a collaborator in the repo
    login(store).get_repo(orgprefix + repo_name).remove_from_collaborators(named_user)
    return f"The user {named_user} was removed from the {repo_name} repository"

@store.kubiya_action()
def get_repo_collaborators(params:Dict) -> List[str]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    collaborators=login(store).get_repo(orgprefix + repo_name).get_collaborators()

    return [collab.login for collab in collaborators]


@store.kubiya_action()
def list_user_repos(username: str) -> List[str]:
    repos = [
        repo.name
        for repo in login(store).get_user(username).get_repos()
    ]
    return sorted(repos, key=lambda x: x.lower())


@store.kubiya_action()
def repo_details(params: Dict) -> Dict[str, Any]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    repo = login(store).get_repo(orgprefix + repo_name)
    return repo.raw_data


@store.kubiya_action()
def get_last_prs(params: Dict) -> List[Dict[str, Any]]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    limit = params.get("limit", 10)
    repo = login(store).get_repo(orgprefix + repo_name)
    return [
        {
            "user": pr.user.login,
            "title": pr.title,
            "number": pr.number,
            "created_at": pr.created_at.isoformat(),
            "head_branch": pr.head.ref,
            "target_branch": pr.base.ref,
        }
        for pr in repo.get_pulls(state='all')[:limit]
    ]


@store.kubiya_action()
def pr_details(params: Dict) -> Dict[str, Any]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    pr_number = params["pr_number"]
    repo = login(store).get_repo(orgprefix + repo_name)
    return repo.get_pull(number=pr_number).raw_data


@store.kubiya_action()
def merge_pr(params: Dict) -> Dict[str, Any]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    pr_number = params["pr_number"]
    repo = login(store).get_repo(orgprefix + repo_name)
    pr = repo.get_pull(number=pr_number)
    pr.merge()
    return pr.raw_data


@store.kubiya_action()
def approve_pr(params: Dict):
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    pr_number = params["pr_number"]
    repo = login(store).get_repo(orgprefix + repo_name)
    pr = repo.get_pull(number=pr_number)
    pr.approve()
    return pr.raw_data


@store.kubiya_action()
def last_commits(params: Dict) -> List[Dict[str, Any]]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    limit = params.get("limit", 20)
    repo = login(store).get_repo(orgprefix + repo_name)
    return [
        {
            "author": commit.author.login,
            "last_modified": commit.last_modified,
            "sha": commit.sha[:8],
        }
        for commit in repo.get_commits()[:limit]
    ]


@store.kubiya_action()
def commit_details(params: Dict) -> Dict[str, Any]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    sha = params["sha"]
    repo = login(store).get_repo(orgprefix + repo_name)
    return repo.get_commit(sha).raw_data


@store.kubiya_action()
# def list_workflows(params: Dict) -> List[Dict[str, Any]]:
def list_workflows(params: Dict)-> List[str]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    repo = login(store).get_repo(orgprefix + repo_name)
    workflows= [action.name+"/"+str(action.id) for action in repo.get_workflows()]

    return workflows


@store.kubiya_action()
# def list_workflows(params: Dict) -> List[Dict[str, Any]]:
def list_workflows_in_progress(params: Dict)-> List[str]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    repo = login(store).get_repo(orgprefix + repo_name)
    workflows= []

    for workflow in repo.get_workflows():
        check=workflow.name+"/"+str(workflow.id)
        for run in workflow.get_runs():
            if run.status=="in_progress" and check not in workflows:
                workflows.append(workflow.name+"/"+str(workflow.id))

    return workflows


@store.kubiya_action()
def last_workflow_runs(params: Dict) -> List[Dict[str, Any]]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    repo = login(store).get_repo(orgprefix + repo_name)
    workflow_id = int(params["workflow_id"].split('/')[1])
    workflow=repo.get_workflow(workflow_id)
    limit = params.get("limit", 30)
    return [
        {
            "display_title":run.raw_data['display_title'],
            "run_id": run.id,
            "status": run.status,
            "run_number": run.run_number,
            "created_at": run.created_at.isoformat(),
            "head_branch": run.head_branch,
        } for run in workflow.get_runs()[:limit]
    ]


@store.kubiya_action()
def workflow_run_details(params: Dict) -> Dict[str, Any]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    run_id = params["run_id"]
    repo = login(store).get_repo(orgprefix + repo_name)
    return repo.get_workflow_run(run_id).raw_data

@store.kubiya_action()
def re_run_gh_action_workflow_run(params: Dict):
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    run_id = params["run_id"]

    # Get the repository where the workflow is located

    repo=login(store).get_repo(orgprefix + repo_name)
    run=repo.get_workflow_run(int(run_id))
    run.rerun()
    return [f"Running workflow run {run_id}"]

@store.kubiya_action()
def in_progress_workflow_runs(params: Dict) -> List[Dict[str, Any]]:
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    repo = login(store).get_repo(orgprefix + repo_name)
    workflow_id = params["workflow_name"]
    id=workflow_id.split('/')[1]
    workflow=repo.get_workflow(id)

    runs=[]
    for run in workflow.get_runs():
        if run.status=="in_progress":
            runs.append({
            "display_title":run.raw_data['display_title'],
            "run_id": run.id,
            "status": run.status,
            "run_number": run.run_number,
            "created_at": run.created_at.isoformat(),
            "head_branch": run.head_branch})

    return runs

@store.kubiya_action()
def cancel_gh_action_workflow_run(params: Dict):
    orgprefix = get_orgprefix(store)
    repo_name = params["repo_name"]
    run_id = params["run_id"]

    # Get the repository where the workflow is located
    repo=login(store).get_repo(orgprefix + repo_name)
    run=repo.get_workflow_run(int(run_id))
    run.cancel()
    return ["Canceling workflow run"]

@store.kubiya_action()
def get_logs_gh_action_workflow_run(params: Dict):
    org_name = get_orgname(store)
    repo_name = params["repo_name"]
    run_id = params["run_id"]
    token=get_token(store)

    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token {token}'
    }

    query_url = f'https://api.github.com/repos/{org_name}/{repo_name}/actions/runs/{run_id}/logs'

    response = requests.get(query_url, headers=headers, params=params,allow_redirects=True)
    download_url=response.url

    return download_url





class Branch(BaseModel):
    name: str
    base: Optional[str]
    repo_name: str


@store.kubiya_action()
def create_branch(params: Branch):
    orgprefix = get_orgprefix(store)
    gh = login(store)
    repo = gh.get_repo(orgprefix + params.repo_name)
    branchname = params.name
    if params.base:
        basebranchname = params.base
    else:
        basebranchname = repo.default_branch
    basebranch = repo.get_branch(basebranchname)
    shafrom = basebranch.commit.sha
    repo.create_git_ref(ref=f"refs/heads/{branchname}", sha=shafrom)
    return True


@store.kubiya_action()
def add_file_to_repo(params: Dict):
    orgprefix = get_orgprefix(store)
    gh = login(store)
    repo = gh.get_repo(orgprefix + params["repo_name"])
    basebranchname = params.get("branch", repo.default_branch)
    filepath = params["filepath"]
    filecontent = params["file"]
    commit_message = params.get("commit_message", "automated-commit by kubi")
    repo.create_file(path=filepath, message=commit_message, content=filecontent, branch=basebranchname)
    return filepath


class Pr(BaseModel):
    repo_name: str
    branch: str
    title: Optional[str]
    message: Optional[str]
    base: Optional[str]


@store.kubiya_action()
def create_pr(params: Dict):
    orgprefix = get_orgprefix(store)
    gh = login(store)
    repo = gh.get_repo(orgprefix + params["repo_name"])
    title = params.get("title", "AutoPR by kubi")
    branch = params["branch"]
    body = params.get("message", "\n\n```auto pr by kubi```")
    basebranchname = params.get("base", repo.default_branch)
    repo.create_pull(base=basebranchname, title=title, head=branch, body=body)


@store.kubiya_action()
def get_repo_file_names(params: Dict) -> List[str]:
    orgprefix = get_orgprefix(store)
    gh = login(store)
    repo = gh.get_repo(orgprefix + params["repo_name"])
    branch = params.get("branch", repo.default_branch)

    return [
        t.path
        for t in repo.get_git_tree(repo.get_branch(branch).commit.sha, recursive=True).tree
        if t.type == "blob"
    ]


@store.kubiya_action()
def get_repo_file(params: Dict):
    orgprefix = get_orgprefix(store)
    gh = login(store)
    repo = gh.get_repo(orgprefix + params["repo_name"])
    filepath = params["filepath"]
    branch = params.get("branch", repo.default_branch)
    return repo.get_contents(filepath, ref=branch).decoded_content


@store.kubiya_action()
def get_gist_files(params: Dict):
    gh = login(store)
    gist_id = params["id"]
    gist = gh.get_gist(gist_id)
    return {k: v.content for k, v in gist.files.items()}