# Golden Path catalog

このサンプルで承認済みとみなす境界。実組織の承認を取得済みという意味ではない。

| Module | 入力 | 出力 | 守るdefault | 変更時のowner |
|---|---|---|---|---|
| `modules/network` | project / environment / owner / vpc_cidr / AZ | VPC・subnet・SG ID、private CIDR | SG通信なし、public IP自動割当なし、private internet routeなし | network / security |
| `modules/application` | project / environment / owner / bucket_name | bucket名・ARN、read policy ARN | 公開防止、暗号化、versioning、force_destroy=false、bucket限定read権限 | application / IAM owner |

全環境はraw resourceを増やさずmoduleを組み合わせる。S3はVPC所属リソースではないため、
サンプルのapplicationには不自然なnetwork依存を作らない。将来ECSなどを追加するときに
networkのprivate subnet / SG outputを渡す。networkにはIGWと明示的なpublic routeを持たせるが、
NATやcomputeは作らず、単一AZの小さな構成に留める。

moduleのローカルsourceは同じgit commitで固定される。互換性のある入力を追加し、
既存の安全defaultを変更する場合は全環境への影響をレビューする。
private registryへ移すときは `source` とexact `version` を記録し、承認済みpublisherを限定する。
Terraformのprovider lockfileはremote moduleの内容をlockしないため、module版の不変性も管理する。
