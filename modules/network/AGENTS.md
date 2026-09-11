# Network scope

ルートのAGENTS.mdに追加する。

- VPC CIDR、subnet CIDR、AZ、route、internet gateway、security groupを高リスクとして扱う。
- CIDR変更やreplacementを発見したら、影響する全環境をplanで確認し、人間のレビューに回す。
- SGはデフォルトでingress / egressとも空。必要な通信だけを用途とportを示して追加する。
- public subnetでもpublic IPの自動割当を有効にしない。private subnetにinternet default routeを作らない。
- `0.0.0.0/0` / `::/0` からSSHを許可しない。全protocolもSSHを含む。
- 全環境がこのmoduleを共有する。prodの呼出しに差分が出る変更にはprodルールも適用する。
- mock testとpolicyの負例を保ち、CIDRやSGの変更を名前変更だけと判断しない。
