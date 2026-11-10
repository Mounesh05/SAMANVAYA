# SAMANVAYA security detection vs bandit and detect-secrets

Reference tools: -m bandit, detect-secrets 1.5.0. Findings are compared by vulnerability category.

> Both corpora were written for this project, alongside SAMANVAYA's rules, so they favour the constructs SAMANVAYA targets. They show what each tool can detect; an independent benchmark is still needed for unbiased accuracy.

## Code vulnerabilities: labelled corpus (52 samples)

| Tool | TP | FN | FP | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| SAMANVAYA | 33 | 0 | 0 | 19 | 100.0% | 100.0% | 100.0% |
| bandit (all) | 23 | 10 | 2 | 17 | 92.0% | 69.7% | 79.3% |
| bandit (medium+) | 22 | 11 | 1 | 18 | 95.7% | 66.7% | 78.6% |

Recall per category:

| Category | Samples | SAMANVAYA | bandit |
|---|---|---|---|
| bind all interfaces | 1 | 1 | 1 |
| code injection | 1 | 1 | 1 |
| command injection | 5 | 5 | 5 |
| debug mode | 1 | 1 | 0 |
| deserialization | 3 | 3 | 3 |
| insecure temp file | 1 | 1 | 1 |
| jwt verification | 1 | 1 | 0 |
| nosql injection | 2 | 2 | 0 |
| open redirect | 1 | 1 | 0 |
| path traversal | 2 | 2 | 0 |
| regex injection | 1 | 1 | 0 |
| sql injection | 8 | 8 | 8 |
| ssrf | 1 | 1 | 0 |
| template injection | 1 | 1 | 0 |
| tls verification | 2 | 2 | 2 |
| weak hash | 1 | 1 | 1 |
| weak random | 1 | 1 | 1 |

Other bandit findings on the corpus (outside the categories under test, not counted):

- B113 request_without_timeout: 3
- B404 blacklist: 1
- B403 blacklist: 1
- B607 start_process_with_partial_path: 1
- B603 subprocess_without_shell_equals_true: 1

## Hard-coded secrets: labelled corpus (27 samples)

| Tool | TP | FN | FP | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| SAMANVAYA | 14 | 0 | 0 | 13 | 100.0% | 100.0% | 100.0% |
| detect-secrets | 13 | 1 | 5 | 8 | 72.2% | 92.9% | 81.3% |

| Case | Has secret | SAMANVAYA | detect-secrets |
|---|---|---|---|
| aws-key | yes | aws_access_key | AWS Access Key |
| github-token | yes | github_token | Base64 High Entropy String; GitHub Token |
| stripe-live | yes | stripe_secret | Base64 High Entropy String; Stripe Access Key |
| slack-token | yes | slack_token | Base64 High Entropy String; Slack Token |
| private-key | yes | private_key | Private Key |
| db-url | yes | db_conn_string | Basic Auth Credentials |
| hex-token-keyword | yes | api_key_generic | Hex High Entropy String |
| base64-token-kwarg | yes | api_key_generic | - |
| password-literal | yes | password_assignment | Secret Keyword |
| dict-secret | yes | secret_key_generic | Base64 High Entropy String; Secret Keyword |
| entropy-weak-hint | yes | high_entropy_string | Base64 High Entropy String |
| env-file | yes | secret_key_generic | Hex High Entropy String; Secret Keyword |
| yaml-password | yes | password_assignment | Secret Keyword |
| js-api-key | yes | api_key_generic | Base64 High Entropy String; Secret Keyword |
| placeholder-change-me | no | - | Secret Keyword |
| placeholder-your-key | no | - | Secret Keyword |
| env-example | no | - | - |
| env-reference | no | - | - |
| template-reference | no | - | - |
| sentence | no | - | Secret Keyword |
| bcrypt-hash | no | - | - |
| commit-sha | no | - | Hex High Entropy String |
| uuid | no | - | - |
| integrity-hash | no | - | Base64 High Entropy String |
| function-call | no | - | - |
| sort-key | no | - | - |
| url-no-credentials | no | - | - |

## SAMANVAYA backend (168 files)

Code findings in the categories above: SAMANVAYA 1, bandit 1, same file+line+category 1.

| Category | SAMANVAYA | bandit | Both |
|---|---|---|---|
| bind all interfaces | 1 | 1 | 1 |

Secrets in code files: SAMANVAYA 0, detect-secrets 0.

Other bandit findings on the backend (outside the categories under test):

- B105 hardcoded_password_string: 3

