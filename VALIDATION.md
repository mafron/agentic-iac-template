# 作成時の検証結果

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

- AWS Providerは6.0.0の固定ベースライン。採用版の再評価と実CLIによる互換性確認が必要。
- lockfileのZIP hashは公式manifest由来だが、実init/providers lockは未実行。
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
