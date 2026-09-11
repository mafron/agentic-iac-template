# Network scope

ルートのAGENTS.mdに追加する。

- このmoduleのコードは通常の編集・Mock検証・PRフローで変更できる。
  `variables.tf`、`main.tf`、`outputs.tf`、testsを、このディレクトリにあることだけを理由に拒否しない。
- AGENTS、version pin / lock、backend / stateなど、共通ルールで保護するファイル・操作は引き続き別扱い。
- コード変更後は `make verify` と `make harness-status` を実行する。
  実planでCIDR変更、削除・置換、公開範囲の変更等が出た場合は、risk / policyと該当環境の承認手順に従う。
- SGはデフォルトでingress / egressとも空。必要な通信だけを用途とportを示して追加する。
- public subnetでもpublic IPの自動割当を有効にしない。private subnetにinternet default routeを作らない。
- `0.0.0.0/0` / `::/0` からSSHを許可しない。全protocolもSSHを含む。
- 全環境がこのmoduleを共有する。prodの呼出しに差分が出る変更にはprodルールも適用する。
- mock testとpolicyの負例を保ち、CIDRやSGの変更を名前変更だけと判断しない。
