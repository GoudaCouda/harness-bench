import unittest

from src.oidc_trust import authorize_tokens


ROLE = {
    "role_id": "public-role",
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["public.sts"],
    "owner_id": "11",
    "repository_ids": ["22"],
    "subject_mode": "immutable",
    "allowed_refs": ["refs/heads/develop"],
    "allowed_environments": [],
    "required_workflow": None,
}
POLICY = {"allow_pull_request": True, "require_immutable_subject": False}


def token(**changes):
    value = {
        "request_id": "request",
        "role_id": "public-role",
        "iss": ROLE["issuer"],
        "aud": "public.sts",
        "sub": "repo:org@11/repo@22:ref:refs/heads/develop",
        "repository": "org/repo",
        "owner_id": "11",
        "repository_id": "22",
        "ref": "refs/heads/develop",
        "environment": None,
        "job_workflow_ref": None,
        "event_name": "push",
        "id_token_permission": "write",
    }
    value.update(changes)
    return value


class TrustTests(unittest.TestCase):
    def test_matching_immutable_subject_authorizes(self):
        self.assertEqual(
            authorize_tokens([ROLE], [token()], POLICY)["decisions"][0]["status"],
            "authorized",
        )

    def test_wrong_repository_id_denies_before_subject(self):
        self.assertEqual(
            authorize_tokens([ROLE], [token(repository_id="23")], POLICY)["decisions"][
                0
            ]["reason"],
            "repository_id",
        )


if __name__ == "__main__":
    unittest.main()
