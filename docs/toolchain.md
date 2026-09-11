# 固定版と更新

| 対象 | このサンプルの版 | 固定する場所 |
|---|---|---|
| Terraform | 1.16.2 | `.terraform-version` と全 `versions.tf` |
| AWS Provider | 6.0.0 | 全 `versions.tf` と全 `.terraform.lock.hcl` |
| TFLint | 0.64.0 | `.tflint-version` |
| OPA | 1.20.2 | `.opa-version` とCI installerのSHA256 |
| Python | 3.10以降、標準ライブラリのみ | CIはUbuntu 24.04のPython |
| GitHub Actions | full commit SHA | workflow内 |

AWS Provider 6.0.0は説明用の固定ベースラインであり、最新版という意味ではない。
実環境導入時には採用版のrelease notes / security情報を再評価し、独立PRで更新する。
この生成環境にはTerraform / TFLint / OPAがなく、これらの版での実行互換性は未確認。

5つのrootのlockfileは、以下の公式ZIP checksumからシードした。
`terraform init` を実行して生成したとの主張ではなく、公開checksumを用いたlock形式のファイルである。

- [AWS 6.0.0 SHA256SUMS](https://releases.hashicorp.com/terraform-provider-aws/6.0.0/terraform-provider-aws_6.0.0_SHA256SUMS)
- 対象: Linux / macOSのamd64・arm64、Windows amd64
- OPA Linux amd64 staticのchecksumは [OPA 1.20.2 release asset](https://github.com/open-policy-agent/opa/releases/tag/v1.20.2) のSHA256 digest
- ActionsのSHAは公式GitHub repositoryのtag/refから解決（2026-09-11確認）

`zh:` は配布ZIPのSHA256。初回のreadonly initがローカル用 `h1:` を保存できない旨を警告することがある。
checksum自体の不一致はエラーとして扱う。警告を理由にlockfileを削除しない。
外部ミラーや別platformを使う場合は承認済みの更新として、各rootで例えば
`terraform providers lock -platform=linux_amd64 -platform=linux_arm64 -platform=darwin_arm64`
を実行し、providerの署名・checksum・lockfile差分を確認してコミットする。
更新する版はmoduleとenvironmentで揃え、`make verify` を通す。

初回initにはRegistry / provider downloadへのネットワークが必要。AWS credentialや有料契約は不要。
完全オフラインでは事前配布したproviderミラーと承認済みlockを用意する。
runnerイメージ、OS patch、インストーラー自体まで固定したhermetic buildではない。
このサンプルのdeterministicとは、固定入力・固定依存版に対する機械的な判定の再現性を指す。

インストール手順は公式配布元を使い、取得したバイナリの署名/checksumを検証する。

- [Terraform installation](https://developer.hashicorp.com/terraform/install)
- [TFLint releases](https://github.com/terraform-linters/tflint/releases)
- [OPA installation](https://www.openpolicyagent.org/docs#running-opa)
