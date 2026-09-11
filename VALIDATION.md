# 検証結果

## network moduleを通常編集scopeへ変更（2026-09-11）

- 利用者の指定により、`modules/network/` 全体の編集拒否を解除。
  root / nested AGENTS、hook説明、CODEOWNERS例を通常の変更フローへ揃えた。
- ローカル `make python-test`: **63件中62件PASS、1件SKIP**（Terraform欠如によるstaged fmt）。
- networkのvariables / main / outputs / testsの編集と、root / nested cwd / 絶対pathでのpatch許可を確認。
- production、AGENTS、version pin / lock、backend / stateを含むpatchや、それらへのmoveは引き続き拒否。
- plan risk / OPA / production gateは維持。実AWS plan / apply / state操作、native Codexセッションは未実行。
- 全体verifyはローカルのTerraform / TFLint / OPA欠如で実行できず、PR CIで固定版toolchainを使って検証する。

## 探索とmake helpの誤拒否修正（2026-09-11）

- 原因: `help` のallowlist登録漏れ、限定しすぎた探索書式、Bash全体に対するroot cwd限定。
- ローカルPython: **60件中59件PASS、1件SKIP**。SKIPはTerraform欠如によるstaged fmt test。
- 実Bashからmake help、ls、find、ripgrepを一時directory内で実行し、glob/正規表現の結果を確認。
- 読み取りの許可に加えて、shell連結・展開、任意実行option、明示したcheckout外path、
  symlink、makeの引数上書き・nested cwdからの実行が拒否されることを確認。
- 実Codex clientセッションはこの修正環境では未実行。導入先で更新後の探索commandも再確認する。
- ローカル全体verifyはTerraform / TFLint / OPA欠如でFAIL。固定版toolchainの全体検証はPR CIで行う。

## Codexへの接続変更（2026-09-11）

| 対象 | ローカル結果 |
|---|---|
| Python regression | **49件中48件PASS、1件SKIP**。Codex payload、複数file patch、move、保護path、source readを追加検証 |
| 設定に記載したhook command | nested cwdから実際に起動し、Git root解決とJSON応答がPASS。patch自体は実行しない |
| 実Terraformのstaged fmt | Terraform欠如により上記1件をSKIP |
| skill形式 / Bash / JSON / TOML / 相対link / diff | PASS |
| `make verify` | **FAIL（依存不足）**。Terraform / TFLint / OPA欠如を列挙して非ゼロ停止 |
| `make codex-check` | **未実行（依存不足を検出して非ゼロ停止）**。実Codex CLIなし |
| native Codex CLI / IDEのhook発火・trust・sandbox | **未実行**。JSON契約testを実セッション検証とは扱わない |
| 実AWS plan / apply / state操作 | 未実行 |

この節はローカル結果です。PRのTerraform Checkが、固定版toolchainを用いた独立検証を行います。
Codex CLIは共通CIの必須依存にしていません。導入先で [Codex接続確認](docs/codex.md) を行ってください。
以下は過去のPR・初期作成時の記録です。

## Hook / skill拡張のローカル検証（2026-09-11）

| 対象 | 結果 |
|---|---|
| Python regression | 37件中36件PASS、実Terraformを使うstaged fmt 1件は依存不足でSKIP |
| 実Git hook | 一時repositoryでpre-commit拒否・pre-push成功を確認 |
| skill形式 | skill-creatorのquick_validateで両SKILL.md PASS |
| Shell / workflow / hook設定 | Bash構文、YAML、JSON、文書相対link PASS |
| `make verify` / `make harness-status` | Terraform / TFLint / OPA欠如でFAIL。古いPASS記録を残さない |
| 実agent clientセッション | 未実行。JSON adapter契約をPythonで検証 |

### Hook / skill拡張のGitHub Actions結果

[PR #4](https://github.com/mafron/agentic-iac-template/pull/4) の
[Terraform Check](https://github.com/mafron/agentic-iac-template/actions/runs/34568890123) で、
commit `d1177766e2e332d813b64296e26de0de17535f60` の全検証が **PASS**。
固定版toolchainは下記初期CIと同じです。

- Terraform fmt、5 rootのbackend無効init / validate / TFLint: PASS。
- Provider Mocking: 12件PASS。
- Python regression: **37件すべてPASS、SKIPなし**。実Terraformのstaged blob検査を含む。
- OPA: 19件PASS、安全/危険fixtureのCLI gateもPASS。
- 全体verifyから記録生成、`make harness-status`、実pre-push入口への接続: PASS。

native agent client、実AWS plan / apply / state操作は未実行です。

## 初期GitHub Actionsでの検証（2026-09-11）

[Terraform Check成功run](https://github.com/mafron/agentic-iac-template/actions/runs/34565676753)
で、commit `22f7fd119a5ee9cc9f6614242ceab68e190b7200` の `make verify` が **PASS**。
Ubuntu 24.04 / Linux amd64、Terraform 1.16.2、AWS Provider 6.0.0、TFLint 0.64.0、OPA 1.20.2。

| 検証 | 結果 |
|---|---|
| Terraform fmt check | PASS |
| backend無効・readonly lockでのinit / validate | 全5 root PASS |
| Terraform Provider Mocking test | 12件 PASS |
| TFLint | 全5 root PASS |
| Python regression test | 10件 PASS |
| OPA strict check / policy test | 19件 PASS |
| safe / unsafe fixtureのCLI gate | 許可は0、拒否は1で終了しPASS |

CIで発見し修正した問題:

- `head` と `pipefail` によるバージョン取得時のSIGPIPE。
- Terraformが要求するpolicy JSON expression内の書式。
- ZIP checksumのみではreadonly init後の展開済みprovider検証に不足するため、
  TerraformがHashiCorp署名を確認して生成した5platform分の正式lockfileへ置換。
- OPAのboolean比較はfalseでも結果が定義されるため、trueとのunificationと`--fail`で拒否を強制。

実AWS plan / apply / state操作は実行していない。5platformのlock生成は、
すべてのplatformでテストを実行したという意味ではない。

## 初回ローカル生成環境の記録（履歴）

実施日: 2026-09-11 UTC。以下はこの作成環境での結果です。CIを実行した結果ではありません。

| 対象 | 状態 | 実行・確認内容 |
|---|---|---|
| Python regression test | **PASS** | `python3 -m unittest discover -s scripts/tests -v`、10件 |
| Shell構文 | **PASS** | 全5本の `.sh` を `bash -n` で検査 |
| YAML構文 | **PASS** | 2 workflowとDependabotをPyYAMLで解析 |
| Workflowの静的整合 | **PASS** | full SHA、reusable workflowの呼出し、認証jobの分離、埋め込みshell構文 |
| Toolchain / file整合 | **PASS** | 5 rootのversion・lockfile・test存在とmodule相対参照を確認 |
| Make入口 | **PASS** | `make -n verify plan policy test` による呼出し先確認 |
| `make verify` | **FAIL（依存不足）** | Terraform / TFLint / OPA欠如を列挙して非ゼロ停止。検証省略によるPASSをしない |
| `terraform fmt -check -recursive` | **未実行** | Terraform未インストール |
| `terraform init -backend=false` | **未実行** | Terraform未インストール |
| `terraform validate` | **未実行** | Terraform未インストール |
| `terraform test` | **未実行** | Terraform未インストール。Mock runは12件用意 |
| TFLint | **未実行** | TFLint未インストール |
| OPA strict check / policy test | **未実行** | OPA未インストール。Rego testは19件用意 |
| Real AWS plan / GitHub Actions | **未実行** | AWS/backend/GitHub remoteの実行設定なし |
| Apply / state操作 | **未実行** | この作業の対象外。applyの入口なし |

Pythonテストは置換両順序の排他的集計、data read/no-op除外、prod・IAM・network・SG、
IPv6・before側の公開、unknown値、state操作、不正planの拒否、安定した表示順序、
属性値の非表示、CLI終了コードを確認しています。

Terraform/Regoの構造は自己レビューし、明らかな参照の不整合、書式の不揃い、
削除時のnull afterの扱い、manifestキーの衝突を修正しました。
**このレビューはTerraform/provider/OPAによるparse・型検査・実行の代替ではありません。**
欠けているツールを独自実装で代替せず、実行結果を未確認のままPASSとは報告していません。

## 既知の制約

- AWS Providerは6.0.0の固定ベースライン。実運用の採用版とAWS API上の動作は別途再評価する。
- 現在のlockfileはCI上の実providers lockで生成済み。実行テストはLinux amd64のみ。
- Mockは実API、実IAM、drift、quota、bucket名の一意性を保証しない。
- policyは対象resourceと代表的な公開経路の例。包括的なAWS security scannerではない。
- GitHub branch protection、CODEOWNERS、Environment reviewer、OIDC/IAM、state bucket、
  アクセス制御付きplan保管、実行承認・apply基盤は導入者が設定する。
- 初回生成時はGitHub repositoryが未作成だったため、ローカルGitとZIPを作成した。
  その後、利用者が作成した [mafron/agentic-iac-template](https://github.com/mafron/agentic-iac-template)
  を反映先とした。上表は初回生成環境の実行記録であり、GitHub Actionsの結果とは区別する。

## 次の実行

固定版ツールを導入して `make verify` を実行する。失敗があれば原因を修正し、
すべてPASSしてからGitHubのrequired checkを有効化する。
その後、隔離したAWS account、S3 backend、OIDC plan role、保護された承認経路を設定し、
devのfresh planから段階的に導入する。
